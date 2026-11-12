"""Verify local private TLS/authentication; optional fake workflow, with no live calls."""

import argparse
import base64
import json
import re
import runpy
import ssl
import subprocess
import tempfile
from http.client import HTTPSConnection
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def check(project, port, *, read_only=False):
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", project) or not 1 <= port <= 65535:
        raise ValueError("Invalid project or loopback port")
    command = [
        "docker",
        "compose",
        "-p",
        project,
        "--env-file",
        ".local/compose.env",
        "--env-file",
        ".local/access.env",
        "-f",
        "compose.yaml",
        "-f",
        "compose.private.yaml",
        "-f",
        "compose.server.yaml",
    ]
    token = dict(
        line.split("=", 1)
        for line in (ROOT / ".local/access.env").read_text().splitlines()
        if "=" in line
    )["AGENTEVAL_ACCESS_TOKEN"]
    authorization = "Basic " + base64.b64encode(("owner:" + token).encode()).decode()
    result = {"status": "PASS", "TLS_verification_enabled": True, "provider_calls": 0, "checks": []}
    with tempfile.TemporaryDirectory(prefix="private-ca-", dir=ROOT / ".local") as folder:
        certificate = Path(folder) / "root.crt"
        subprocess.run(
            command + ["cp", "proxy:/data/caddy/pki/authorities/local/root.crt", str(certificate)],
            cwd=ROOT,
            check=True,
            capture_output=True,
        )
        context = ssl.create_default_context(cafile=str(certificate))

        def request(path, body=None, key=None, *, authenticated=True, expected=None):
            headers = {"Content-Type": "application/json"}
            if authenticated:
                headers["Authorization"] = authorization
            if key:
                headers["Idempotency-Key"] = key
            connection = HTTPSConnection("localhost", port, context=context, timeout=5)
            try:
                connection.request(
                    "GET" if body is None else "POST",
                    path,
                    body=None
                    if body is None
                    else (body if isinstance(body, bytes) else json.dumps(body).encode()),
                    headers=headers,
                )
                response = connection.getresponse()
                raw = response.read()
                if (
                    token.encode() in raw
                    or (expected is not None and response.status != expected)
                    or (expected is None and not 200 <= response.status < 300)
                ):
                    raise ValueError("Private TLS response check failed")
                return (
                    json.loads(raw)
                    if response.getheader("Content-Type", "").startswith("application/json")
                    else None
                )
            finally:
                connection.close()

        request("/health/live", authenticated=False, expected=200)
        request("/health/ready", authenticated=False, expected=401)
        ready = request("/health/ready", expected=200)
        if ready["database"] != "ready" or (
            not read_only and (ready["provider"] != "fake" or ready["simulated"] is not True)
        ):
            raise ValueError("Private preview must use a ready simulated provider")
        request("/dashboard/", authenticated=False, expected=401)
        request("/dashboard/", expected=200)
        request("/evaluations", b"x" * 40000, expected=413)
        result["checks"] = [
            "trusted TLS",
            "owner gate",
            "dashboard",
            "32-KiB body bound",
            "simulated provider",
        ]
        connection = HTTPSConnection("localhost", port, timeout=5)
        try:
            connection.request("GET", "/health/live")
            connection.getresponse()
        except ssl.SSLCertVerificationError:
            result["checks"].append("untrusted CA rejected")
        else:
            raise ValueError("Untrusted certificate unexpectedly accepted")
        finally:
            connection.close()
        if not read_only:
            result["portfolio"] = runpy.run_path(str(ROOT / "scripts/portfolio_demo.py"))[
                "demonstrate"
            ](request)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", default="agenteval-private")
    parser.add_argument("--port", type=int, default=8443)
    parser.add_argument(
        "--read-only", action="store_true", help="Do not create a dataset or queued runs"
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.output and args.output.exists():
        parser.error("Choose a fresh output path to preserve evidence")
    try:
        result = check(args.project, args.port, read_only=args.read_only)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            with args.output.open("x") as file:
                file.write(json.dumps(result, indent=2) + "\n")
    except Exception:
        parser.error(
            "Private server check failed; inspect trusted local configuration and service state. Credentials were not printed."
        )
    print(
        "PASS: private TLS, owner authentication, readiness and body limits; zero provider calls."
    )


if __name__ == "__main__":
    main()
