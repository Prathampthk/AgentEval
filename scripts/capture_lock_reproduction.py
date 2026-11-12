"""Capture a controlled lock positive control and unmodified simulated sweep in fresh files."""

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

from sqlalchemy.engine import make_url


def capture(output, *, jobs=1000, repetitions=2, run=subprocess.run):
    for variable, suffix in (
        ("AGENTEVAL_TEST_DATABASE_URL", "_test"),
        ("AGENTEVAL_BENCHMARK_DATABASE_URL", "_benchmark"),
    ):
        parsed = make_url(os.environ.get(variable, ""))
        if parsed.drivername != "postgresql+asyncpg" or not (parsed.database or "").endswith(
            suffix
        ):
            raise ValueError("Dedicated test and benchmark databases are required")
    if not 1 <= jobs <= 1000 or not 1 <= repetitions <= 5:
        raise ValueError("Invalid bounded workload")
    output.mkdir(parents=True, exist_ok=False, mode=0o700)
    output = output.resolve()
    env = {
        key: value
        for key, value in os.environ.items()
        if key not in {"GEMINI_API_KEY", "GOOGLE_API_KEY"}
    }
    env["AGENTEVAL_PROVIDER"] = "fake"
    env["AGENTEVAL_LOCK_CONTROL_OUTPUT"] = str(output / "positive-control.json")
    commands = [
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "-p",
            "no:cacheprovider",
            "tests/integration/test_lock_diagnostics.py",
            "--junitxml=" + str(output / "positive-control.xml"),
        ],
        [
            sys.executable,
            "-m",
            "agenteval.platform_benchmark",
            "--jobs",
            str(jobs),
            "--repetitions",
            str(repetitions),
            "--workers",
            "4",
            "16",
            "--diagnostics",
            "--skip-recovery",
            "--output",
            str(output / "raw.json"),
        ],
        [
            sys.executable,
            "scripts/summarize_lock_diagnostics.py",
            "--input",
            str(output / "raw.json"),
            "--archive",
            str(output / "raw.json.gz"),
            "--output",
            str(output / "summary.json"),
        ],
    ]
    root = Path(__file__).resolve().parents[1]
    manifest = {
        "status": "INCOMPLETE",
        "simulated": True,
        "provider_calls": 0,
        "positive_control": "Deliberate 1.5-second lock timeout; not a spontaneous recurrence.",
        "uninjected_sweep": {
            "jobs_per_variant": jobs,
            "repetitions": repetitions,
            "workers": [4, 16],
        },
        "steps": [],
        "source_sha256": {
            p: hashlib.sha256((root / p).read_bytes()).hexdigest()
            for p in [
                "scripts/capture_lock_reproduction.py",
                "tests/integration/test_lock_diagnostics.py",
                "src/agenteval/diagnostics.py",
                "src/agenteval/platform_benchmark.py",
            ]
        },
        "limitations": [
            "No recurrence leaves the historical root cause unresolved.",
            "Run on comparable controlled hardware with WAL I/O timing enabled and no concurrent workload.",
            "Cluster-wide WAL counters and sampled wait graphs cannot attribute one transaction's storage delay.",
        ],
    }

    def checkpoint():
        (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")

    checkpoint()
    for index, command in enumerate(commands):
        result = run(command, cwd=root, env=env, capture_output=True, timeout=1800)
        with open(
            output / f"step-{index + 1}.log", "xb", opener=lambda p, f: os.open(p, f, 0o600)
        ) as file:
            file.write(result.stdout + result.stderr)
        manifest["steps"].append(
            {
                "name": ["controlled-lock-attribution", "uninjected-sweep", "summary"][index],
                "returncode": result.returncode,
            }
        )
        checkpoint()
        if result.returncode:
            return manifest
    manifest["status"] = "CAPTURED"
    checkpoint()
    return manifest


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--jobs", type=int, default=1000)
    parser.add_argument("--repetitions", type=int, default=2)
    args = parser.parse_args()
    try:
        result = capture(args.output_dir, jobs=args.jobs, repetitions=args.repetitions)
    except (OSError, ValueError, subprocess.SubprocessError):
        parser.error(
            "Capture stopped; use dedicated databases and a fresh directory. Preserve available evidence."
        )
    print(f"{result['status']}: evidence at {args.output_dir}; zero provider calls.")
    raise SystemExit(0 if result["status"] == "CAPTURED" else 1)


if __name__ == "__main__":
    main()
