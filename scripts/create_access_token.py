"""Generate a protected owner token file without printing or replacing its contents."""

import os
import secrets
from pathlib import Path


def main():
    root = Path(__file__).resolve().parents[1]
    folder = root / ".local"
    folder.mkdir(mode=0o700, exist_ok=True)
    path = folder / "access.env"
    if path.exists():
        print("Preserved existing .local/access.env; no credential changes.")
        return
    with open(path, "x", opener=lambda p, f: os.open(p, f, 0o600)) as file:
        file.write("AGENTEVAL_ACCESS_TOKEN=" + secrets.token_hex(32) + "\n")
    print("Created protected .local/access.env. Token values were not printed.")


if __name__ == "__main__":
    main()
