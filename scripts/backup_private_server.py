"""Encrypted private-server snapshot with isolated restore verification; never restore over app data."""

import argparse
import fcntl
import hashlib
import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from cryptography.fernet import Fernet

ROOT = Path(__file__).resolve().parents[1]
COUNT_SQL = "SELECT json_build_object('datasets',(SELECT count(*) FROM datasets),'runs',(SELECT count(*) FROM evaluation_runs),'jobs',(SELECT count(*) FROM evaluation_jobs),'results',(SELECT count(*) FROM evaluation_results),'documents',(SELECT count(*) FROM documents),'chunks',(SELECT count(*) FROM document_chunks),'migration',(SELECT version_num FROM alembic_version))"


def encrypt_snapshot(raw, key, output):
    encrypted = Fernet(key).encrypt(raw)
    with open(output, "xb", opener=lambda p, f: os.open(p, f, 0o600)) as file:
        file.write(encrypted)
    return encrypted


def _backup(project, output, key_path):
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", project):
        raise ValueError("Invalid Compose project")
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

    def run(arguments, **kwargs):
        return subprocess.run(
            command + arguments,
            cwd=ROOT,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            **kwargs,
        ).stdout

    # Resolved credentials stay in memory. Never print or persist resolved configuration.
    config = json.loads(run(["config", "--format", "json"]))
    if config["services"]["api"].get("ports") or config["services"]["db"].get("ports"):
        raise ValueError("Private profile must not publish API or database ports")
    environment = config["services"]["api"]["environment"]
    if (
        environment.get("AGENTEVAL_PRIVATE_SERVER") != "1"
        or environment.get("AGENTEVAL_PROVIDER") != "fake"
    ):
        raise ValueError("Backup requires the private simulated server profile")
    actual = json.loads(
        run(
            [
                "exec",
                "-T",
                "api",
                "python",
                "-c",
                "import os,json; print(json.dumps({'private':os.getenv('AGENTEVAL_PRIVATE_SERVER'),'provider':os.getenv('AGENTEVAL_PROVIDER')}))",
            ]
        )
    )
    if actual != {"private": "1", "provider": "fake"}:
        raise ValueError("Running API does not match private simulated profile")
    output.mkdir(parents=True, exist_ok=False, mode=0o700)
    if not key_path.exists():
        key_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with open(key_path, "xb", opener=lambda p, f: os.open(p, f, 0o600)) as file:
            file.write(Fernet.generate_key())
    key = key_path.read_bytes()
    if key_path.stat().st_mode & 0o077:
        raise ValueError("Backup key permissions must exclude group and other users")
    Fernet(key)  # Validate before stopping services.
    report = {
        "status": "INCOMPLETE",
        "project": project,
        "provider_calls": 0,
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "Quiesced PostgreSQL dump, encrypted locally, restored into a new temporary database for count/schema checks. No offsite or host-loss claim.",
    }

    def checkpoint():
        (output / "manifest.json").write_text(json.dumps(report, indent=2) + "\n")

    checkpoint()
    restore_name = "agenteval_restore_" + uuid4().hex + "_test"
    created = False
    try:
        try:
            run(["stop", "api", "worker"])
            report["snapshot_counts"] = json.loads(
                run(
                    [
                        "exec",
                        "-T",
                        "db",
                        "psql",
                        "-U",
                        "postgres",
                        "-d",
                        "agenteval",
                        "-At",
                        "-c",
                        COUNT_SQL,
                    ]
                )
            )
            raw = run(["exec", "-T", "db", "pg_dump", "-U", "postgres", "-d", "agenteval", "-Fc"])
            encrypted = encrypt_snapshot(raw, key, output / "database.dump.fernet")
            report.update(
                plaintext_sha256=hashlib.sha256(raw).hexdigest(),
                encrypted_sha256=hashlib.sha256(encrypted).hexdigest(),
                encrypted_bytes=len(encrypted),
            )
            checkpoint()
        finally:
            # Restart existing containers only; never rebuild/recreate while restoring availability.
            run(["start", "api", "worker"])
        recovered = Fernet(key).decrypt(encrypted)
        if hashlib.sha256(recovered).hexdigest() != report["plaintext_sha256"]:
            raise ValueError("Decrypted snapshot fingerprint mismatch")
        run(["exec", "-T", "db", "createdb", "-U", "postgres", restore_name])
        created = True
        run(
            [
                "exec",
                "-T",
                "db",
                "pg_restore",
                "-U",
                "postgres",
                "-d",
                restore_name,
                "--exit-on-error",
            ],
            input=recovered,
        )
        restored = json.loads(
            run(
                [
                    "exec",
                    "-T",
                    "db",
                    "psql",
                    "-U",
                    "postgres",
                    "-d",
                    restore_name,
                    "-At",
                    "-c",
                    COUNT_SQL,
                ]
            )
        )
        if restored != report["snapshot_counts"]:
            raise ValueError("Restore count/schema checks differ from snapshot")
        report.update(status="VERIFIED_LOCAL_RESTORE", restored_counts=restored)
    except Exception as exc:
        report["error_category"] = type(exc).__name__
        raise
    finally:
        if created:
            try:
                run(["exec", "-T", "db", "dropdb", "-U", "postgres", restore_name])
            except subprocess.SubprocessError:
                report.update(status="CLEANUP_REQUIRED", temporary_restore_database=restore_name)
        report["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
        checkpoint()
    return report


def backup(project, output, key_path):
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", project):
        raise ValueError("Invalid Compose project")
    with open(ROOT / ".local" / ("backup-" + project + ".lock"), "a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return _backup(project, output, key_path)


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", default="agenteval-private")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--key-file", type=Path, default=ROOT / ".local/backup.key")
    args = parser.parse_args()
    output = args.output_dir or ROOT / ".local/backups" / (
        datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:8]
    )
    try:
        report = backup(args.project, output, args.key_file)
    except Exception:
        parser.error(
            "Backup stopped; preserve protected manifest/dump, check service readiness, and diagnose locally. Credentials were not printed."
        )
    print(f"{report['status']}: encrypted snapshot and manifest at {output}. Key remains separate.")
    raise SystemExit(0 if report["status"] == "VERIFIED_LOCAL_RESTORE" else 1)


if __name__ == "__main__":
    main()
