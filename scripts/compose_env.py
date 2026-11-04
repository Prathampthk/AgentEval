"""Create protected local Compose credentials, without printing their values."""

import os
import secrets
from pathlib import Path

root = Path(__file__).resolve().parents[1]
folder = root / ".local"
folder.mkdir(exist_ok=True, mode=0o700)
path = folder / "compose.env"
if not path.exists():
    with open(path, "x", opener=lambda name, flags: os.open(name, flags, 0o600)) as file:
        file.write(
            f"POSTGRES_PASSWORD={secrets.token_hex(24)}\nAPP_DB_PASSWORD={secrets.token_hex(24)}\nLOCAL_UID={os.getuid()}\nLOCAL_GID={os.getgid()}\n"
        )
print("Protected .local/compose.env is ready; existing values preserved")
