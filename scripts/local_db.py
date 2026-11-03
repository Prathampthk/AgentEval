"""Manage only AgentEval's local Docker database; never print generated secrets.

Usage: python scripts/local_db.py start
       python scripts/local_db.py run COMMAND [ARG...]
       python scripts/local_db.py admin COMMAND [ARG...]

The run command uses configured remote URLs when present; otherwise it injects
local URLs from the protected ignored configuration file. It never prints them.
"""

import json
import os
import secrets
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCAL = ROOT / ".local"
NAME = "agenteval-postgres"
IMAGE = "pgvector/pgvector:pg17-bookworm@sha256:7d0a41464797aeb9862dfdc0bbf1526b82cfd324cdd8036df19e3545f4a9ccb8"
DOCKER = ["docker", "--host=unix:///var/run/docker.sock"]


def docker(*args, **kwargs):
    env = os.environ.copy()
    for key in (
        "DOCKER_HOST",
        "DOCKER_CONTEXT",
        "DOCKER_TLS",
        "DOCKER_TLS_VERIFY",
        "DOCKER_CERT_PATH",
    ):
        env.pop(key, None)
    return subprocess.run([*DOCKER, *args], env=env, check=True, **kwargs)


def start():
    LOCAL.mkdir(mode=0o700, exist_ok=True)
    settings_path = LOCAL / "database.json"
    if not settings_path.exists():
        # Never invent or replace credentials for an existing container.
        existing = docker(
            "ps",
            "-a",
            "--filter",
            f"name=^/{NAME}$",
            "--format",
            "{{.Names}}",
            capture_output=True,
            text=True,
        ).stdout.strip()
        if existing:
            raise RuntimeError(
                "Existing container found without local configuration; inspect it first"
            )
        password = secrets.token_hex(24)
        admin_password = secrets.token_hex(24)
        settings = {
            "AGENTEVAL_DATABASE_URL": f"postgresql+asyncpg://agenteval:{password}@127.0.0.1:5432/agenteval",
            "AGENTEVAL_TEST_DATABASE_URL": f"postgresql+asyncpg://postgres:{admin_password}@127.0.0.1:5432/agenteval_test",
            "AGENTEVAL_MIGRATION_DATABASE_URL": f"postgresql+asyncpg://postgres:{admin_password}@127.0.0.1:5432/agenteval",
        }
        with open(
            settings_path, "x", opener=lambda path, flags: os.open(path, flags, 0o600)
        ) as file:
            json.dump(settings, file)
        with open(
            LOCAL / "postgres.env", "x", opener=lambda path, flags: os.open(path, flags, 0o600)
        ) as file:
            file.write(
                f"POSTGRES_USER=postgres\nPOSTGRES_DB=agenteval\nPOSTGRES_PASSWORD={admin_password}\n"
            )
    existing = docker(
        "ps",
        "-a",
        "--filter",
        f"name=^/{NAME}$",
        "--format",
        "{{.Names}}",
        capture_output=True,
        text=True,
    ).stdout.strip()
    if not existing:
        docker(
            "run",
            "-d",
            "--name",
            NAME,
            "--label",
            "app=agenteval-local",
            "--env-file",
            str(LOCAL / "postgres.env"),
            "-p",
            "127.0.0.1:5432:5432",
            "-v",
            f"{LOCAL / 'postgres-data'}:/var/lib/postgresql/data",
            IMAGE,
            stdout=subprocess.DEVNULL,
        )
    else:
        label = docker(
            "inspect",
            "--format",
            '{{index .Config.Labels "app"}}',
            NAME,
            capture_output=True,
            text=True,
        ).stdout.strip()
        if label != "agenteval-local":
            raise RuntimeError("Container name belongs to another application")
        docker("start", NAME, stdout=subprocess.DEVNULL)
    for _ in range(30):
        try:
            docker(
                "exec",
                NAME,
                "pg_isready",
                "-U",
                "postgres",
                "-d",
                "agenteval",
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            break
        except subprocess.CalledProcessError:
            time.sleep(1)
    else:
        raise RuntimeError("PostgreSQL did not become ready")
    exists = docker(
        "exec",
        NAME,
        "psql",
        "-U",
        "postgres",
        "-d",
        "agenteval",
        "-Atc",
        "SELECT 1 FROM pg_database WHERE datname='agenteval_test'",
        capture_output=True,
        text=True,
    ).stdout.strip()
    if not exists:
        docker("exec", NAME, "createdb", "-U", "postgres", "agenteval_test")
    bench_exists = docker(
        "exec",
        NAME,
        "psql",
        "-U",
        "postgres",
        "-d",
        "agenteval",
        "-Atc",
        "SELECT 1 FROM pg_database WHERE datname='agenteval_benchmark'",
        capture_output=True,
        text=True,
    ).stdout.strip()
    if not bench_exists:
        docker("exec", NAME, "createdb", "-U", "postgres", "agenteval_benchmark")
    from sqlalchemy.engine import make_url

    settings = json.loads(settings_path.read_text())
    if "AGENTEVAL_BENCHMARK_DATABASE_URL" not in settings:
        settings["AGENTEVAL_BENCHMARK_DATABASE_URL"] = (
            make_url(settings["AGENTEVAL_MIGRATION_DATABASE_URL"])
            .set(database="agenteval_benchmark")
            .render_as_string(hide_password=False)
        )
        settings_path.write_text(json.dumps(settings))
    role_exists = docker(
        "exec",
        NAME,
        "psql",
        "-U",
        "postgres",
        "-d",
        "agenteval",
        "-Atc",
        "SELECT 1 FROM pg_roles WHERE rolname='agenteval'",
        capture_output=True,
        text=True,
    ).stdout.strip()
    if not role_exists:
        from sqlalchemy.engine import make_url

        password = make_url(
            json.loads(settings_path.read_text())["AGENTEVAL_DATABASE_URL"]
        ).password
        if not password or any(c not in "0123456789abcdef" for c in password):
            raise RuntimeError("Unexpected local password format")
        docker(
            "exec",
            "-i",
            NAME,
            "psql",
            "-v",
            "ON_ERROR_STOP=1",
            "-U",
            "postgres",
            "-d",
            "agenteval",
            input=f"CREATE ROLE agenteval LOGIN PASSWORD '{password}' NOSUPERUSER NOCREATEDB NOCREATEROLE;",
            text=True,
            stdout=subprocess.DEVNULL,
        )
    docker(
        "exec",
        NAME,
        "psql",
        "-v",
        "ON_ERROR_STOP=1",
        "-U",
        "postgres",
        "-d",
        "agenteval",
        "-c",
        "GRANT USAGE ON SCHEMA public TO agenteval; "
        "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO agenteval; "
        "ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public "
        "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO agenteval;",
        stdout=subprocess.DEVNULL,
    )
    print("Local PostgreSQL is ready; development and test databases are separate")


def run(command, administrative=False, local_only=False):
    env = os.environ.copy()
    settings_path = LOCAL / "database.json"
    settings = json.loads(settings_path.read_text()) if settings_path.exists() else {}
    if local_only:
        if not settings.get("AGENTEVAL_DATABASE_URL"):
            raise RuntimeError("Start the local demonstration database before browser tests")
        env["AGENTEVAL_DATABASE_URL"] = settings["AGENTEVAL_DATABASE_URL"]
    external_database = bool(
        env.get("AGENTEVAL_DATABASE_URL") or env.get("AGENTEVAL_MIGRATION_DATABASE_URL")
    )
    runtime_url = settings.get("AGENTEVAL_DATABASE_URL")
    if runtime_url:
        env.setdefault("AGENTEVAL_DATABASE_URL", runtime_url)
    if administrative:
        if not external_database and settings.get("AGENTEVAL_MIGRATION_DATABASE_URL"):
            env.setdefault(
                "AGENTEVAL_MIGRATION_DATABASE_URL", settings["AGENTEVAL_MIGRATION_DATABASE_URL"]
            )
        if settings.get("AGENTEVAL_TEST_DATABASE_URL"):
            env.setdefault("AGENTEVAL_TEST_DATABASE_URL", settings["AGENTEVAL_TEST_DATABASE_URL"])
        if settings.get("AGENTEVAL_BENCHMARK_DATABASE_URL"):
            env.setdefault(
                "AGENTEVAL_BENCHMARK_DATABASE_URL", settings["AGENTEVAL_BENCHMARK_DATABASE_URL"]
            )
    os.chdir(ROOT)
    os.execvpe(command[0], command, env)


if __name__ == "__main__":
    if sys.argv[1:] == ["start"]:
        start()
    elif len(sys.argv) > 2 and sys.argv[1] in ("run", "admin", "demo"):
        run(sys.argv[2:], administrative=sys.argv[1] == "admin", local_only=sys.argv[1] == "demo")
    else:
        raise SystemExit("Usage: local_db.py start | run COMMAND [ARG...] | admin COMMAND [ARG...]")
