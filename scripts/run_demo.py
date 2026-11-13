"""Start and rehearse an isolated, loopback-only fake-provider demonstration."""

import argparse
import json
import os
import runpy
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import ProxyHandler, Request, build_opener
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
PROJECT = "agenteval-demo"


def verify_local_engine(endpoint):
    if not endpoint.startswith("unix://"):
        raise RuntimeError(
            "Demo requires a local Unix-socket Docker engine; remote contexts are refused"
        )


def verify_configuration(config, port):
    services = config["services"]
    if services["db"].get("ports"):
        raise RuntimeError("Demo refuses a published database port")
    for name in ("api", "worker"):
        if services[name]["environment"].get("AGENTEVAL_PROVIDER") != "fake":
            raise RuntimeError("Demo requires fake API and worker providers")
    ports = services["api"].get("ports", [])
    if (
        len(ports) != 1
        or ports[0].get("host_ip") != "127.0.0.1"
        or str(ports[0].get("published")) != str(port)
    ):
        raise RuntimeError("Demo requires exactly the selected loopback API port")


def verify_existing(containers, root):
    for container in containers:
        labels = container["Config"].get("Labels", {})
        if (
            labels.get("com.docker.compose.project") != PROJECT
            or not labels.get("com.docker.compose.project.working_dir")
            or Path(labels.get("com.docker.compose.project.working_dir", "")).resolve()
            != root.resolve()
        ):
            raise RuntimeError(
                "Existing demo project belongs to another checkout; inspect it manually"
            )
        if labels.get("com.docker.compose.service") not in {"api", "worker", "db", "migrate"}:
            raise RuntimeError(
                "Existing demo project uses an unexpected service profile; no services were changed"
            )
        if labels.get("com.docker.compose.service") in {"api", "worker"}:
            environment = dict(
                entry.split("=", 1) for entry in container["Config"].get("Env", []) if "=" in entry
            )
            if environment.get("AGENTEVAL_PROVIDER") != "fake":
                raise RuntimeError(
                    "Existing demo project has a non-fake provider; no services were changed"
                )
            if environment.get("AGENTEVAL_PRIVATE_SERVER") or environment.get(
                "AGENTEVAL_ACCESS_TOKEN"
            ):
                raise RuntimeError(
                    "Existing demo project uses a protected profile; no services were changed"
                )


def start(port):
    folder = ROOT / "artifacts" / ("demo-" + uuid4().hex)
    folder.mkdir(parents=True, mode=0o700)
    report = {
        "status": "PREPARING",
        "stage": "local engine preflight",
        "simulated": True,
        "provider_calls": 0,
        "human_labels_generated": 0,
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    env = {
        k: v
        for k, v in os.environ.items()
        if k not in {"GEMINI_API_KEY", "GOOGLE_API_KEY", "AGENTEVAL_ACCESS_TOKEN"}
    }
    env.update(API_PORT=str(port), AGENTEVAL_PROVIDER="fake", AGENTEVAL_WORKER_CONCURRENCY="4")
    compose = [
        "docker",
        "compose",
        "-p",
        PROJECT,
        "--env-file",
        ".local/compose.env",
        "-f",
        "compose.yaml",
    ]

    def checkpoint():
        with open(folder / "report.json", "w", opener=lambda p, f: os.open(p, f, 0o600)) as file:
            file.write(json.dumps(report, indent=2) + "\n")

    def run(command, label, *, log=True):
        report["stage"] = label
        checkpoint()
        result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True)
        if log:
            with open(
                folder / (label + ".log"), "xb", opener=lambda p, f: os.open(p, f, 0o600)
            ) as file:
                file.write(result.stdout + result.stderr)
        if result.returncode:
            raise RuntimeError(f"Demo stopped at {label}; protected evidence: {folder}")
        return result.stdout

    checkpoint()
    try:
        if env.get("DOCKER_HOST"):
            verify_local_engine(env["DOCKER_HOST"])
        endpoint = json.loads(
            run(
                ["docker", "context", "inspect", "--format", "{{json .Endpoints.docker.Host}}"],
                "engine-context",
                log=False,
            )
        )
        verify_local_engine(endpoint)
        run([sys.executable, "scripts/compose_env.py"], "local-configuration")
        config = json.loads(
            run(compose + ["config", "--format", "json"], "compose-preflight", log=False)
        )
        verify_configuration(config, port)
        identifiers = (
            run(compose + ["ps", "-a", "-q"], "existing-project", log=False).decode().split()
        )
        if identifiers:
            containers = json.loads(
                run(["docker", "inspect", *identifiers], "project-ownership", log=False)
            )
            verify_existing(containers, ROOT)
            run(compose + ["stop", "api", "worker"], "stop-own-demo-services")
        run(compose + ["build", "api"], "build-demo")
        run(compose + ["up", "-d", "--wait", "api", "worker"], "start-demo")
        module = runpy.run_path(str(ROOT / "scripts/portfolio_demo.py"))
        opener = build_opener(ProxyHandler({}), module["NoRedirect"]())
        base = f"http://127.0.0.1:{port}"

        def request(path, body=None, key=None):
            headers = {"Content-Type": "application/json"}
            if key:
                headers["Idempotency-Key"] = key
            with opener.open(
                Request(
                    base + path,
                    data=None if body is None else json.dumps(body).encode(),
                    headers=headers,
                ),
                timeout=5,
            ) as response:
                return json.load(response)

        report["stage"] = "queued-workflow"
        checkpoint()
        report["portfolio"] = module["demonstrate"](request)
        checkpoint()
        identity = uuid4().hex
        output = run(
            compose
            + [
                "exec",
                "-T",
                "api",
                "python",
                "-m",
                "agenteval.regression",
                "--demo-scenarios",
                "--output",
                f"/tmp/demo-policy-{identity}.json",
            ],
            "policy-scenarios",
        )
        report["policy_scenarios"] = json.loads(output)
        if report["policy_scenarios"]["status"] != "PASS":
            raise RuntimeError("Policy scenarios did not match expected decisions")
        with opener.open(base + "/dashboard/", timeout=5) as response:
            if response.status != 200:
                raise RuntimeError("Packaged dashboard is unavailable")
        report.update(
            status="DEMO_READY",
            stage="complete",
            dashboard=base + "/dashboard/",
            limits=[
                "Four queued fake results and synthetic policy scenarios demonstrate mechanics only.",
                "The fifty-pair live study is recorded evidence; this rehearsal makes no live calls.",
                "RAG answer/citation human review and the historical lock-timeout cause remain separate.",
            ],
        )
        checkpoint()
    except Exception as exc:
        report.update(status="STOPPED", error_category=type(exc).__name__)
        checkpoint()
        raise RuntimeError(f"Demo stopped at {report['stage']}. Evidence: {folder}") from None
    print(f"DEMO READY: {report['dashboard']}")
    for row in report["portfolio"]["runs"]:
        print(f"{row['label']}: {row['run_id']}")
    print("Policy scenarios: PASS / FAIL / INCONCLUSIVE (explicitly synthetic).")
    print(f"Evidence: {folder / 'report.json'}")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8013)
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("Port must be between 1 and 65535")
    try:
        start(args.port)
    except RuntimeError as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
