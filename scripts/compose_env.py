"""Create protected local Compose credentials, without printing their values."""

import os
import secrets
import shutil
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
# Buildx Bake may forbid reading secrets outside its workspace. This public
# trust bundle is copied into ignored local state and mounted only at build time.
ca_source = Path(os.getenv("AGENTEVAL_BUILD_CA", "/etc/ssl/certs/ca-certificates.crt"))
ca_target = folder / "build-ca.crt"
if ca_source.resolve() != ca_target.resolve():
    shutil.copyfile(ca_source, ca_target)
print(
    "Protected Compose credentials and local build trust bundle are ready; existing credentials preserved"
)
