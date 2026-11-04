"""Export the installed runtime dependency closure from the reviewed dev lock."""

import tomllib
from importlib.metadata import distribution
from pathlib import Path

from packaging.requirements import Requirement

root = Path(__file__).resolve().parents[1]
pending = [
    Requirement(value)
    for value in tomllib.loads((root / "pyproject.toml").read_text())["project"]["dependencies"]
]
seen = {}
while pending:
    req = pending.pop()
    dist = distribution(req.name)
    name = dist.metadata["Name"]
    key = name.lower().replace("_", "-")
    extras = set(req.extras) | {""}
    if key in seen and extras.issubset(seen[key][1]):
        continue
    extras |= seen.get(key, (None, set()))[1]
    seen[key] = (dist, extras)
    for raw in dist.requires or []:
        child = Requirement(raw)
        if child.marker is None or any(child.marker.evaluate({"extra": extra}) for extra in extras):
            pending.append(child)
# Build backend is pinned too; editable/development installs retain the full lock.
seen["setuptools"] = (distribution("setuptools"), set())
(root / "requirements-runtime.lock").write_text(
    "\n".join(sorted(f"{dist.metadata['Name']}=={dist.version}" for dist, _ in seen.values()))
    + "\n"
)
