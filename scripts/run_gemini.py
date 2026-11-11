"""Start the local Compose stack with a user-supplied Gemini key."""

import argparse
import getpass
import os
import subprocess
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True, help="Gemini generation and judge model ID")
    parser.add_argument("--judge-prompt", choices=("v1", "candidate-v2"), default="candidate-v2")
    parser.add_argument("--port", type=int, default=8012, help="Loopback port (default 8012)")
    args = parser.parse_args()
    if not args.model.strip():
        parser.error("--model must contain a model ID")
    if not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535")

    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        if not sys.stdin.isatty():
            parser.error("Set GEMINI_API_KEY in the environment or run in an interactive terminal")
        # Treat failure to disable echo as an error instead of reading an echoed key.
        import warnings

        with warnings.catch_warnings():
            warnings.simplefilter("error", getpass.GetPassWarning)
            try:
                key = getpass.getpass("Gemini API key: ").strip()
            except (getpass.GetPassWarning, EOFError):
                parser.error(
                    "Could not read a hidden API key. Set GEMINI_API_KEY in the environment."
                )
        if not key:
            parser.error("A Gemini API key is required")

    root = Path(__file__).resolve().parents[1]
    subprocess.run([sys.executable, "scripts/compose_env.py"], cwd=root, check=True)
    subprocess.run(
        [
            "docker",
            "compose",
            "-p",
            "agenteval-gemini",
            "--env-file",
            ".local/compose.env",
            "-f",
            "compose.yaml",
            "-f",
            "compose.gemini.yaml",
            "up",
            "--build",
            "-d",
            "--wait",
            "api",
            "worker",
        ],
        cwd=root,
        env={
            **os.environ,
            "GEMINI_API_KEY": key,
            "AGENTEVAL_MODEL": args.model.strip(),
            "AGENTEVAL_JUDGE_PROMPT": args.judge_prompt,
            "API_PORT": str(args.port),
            "AGENTEVAL_BUILD_CA": ".local/build-ca.crt",
        },
        check=True,
    )
    print(f"AgentEval dashboard: http://127.0.0.1:{args.port}/dashboard/")


if __name__ == "__main__":
    main()
