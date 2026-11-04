"""The portfolio script must refuse live or unready APIs before creating work."""

import runpy
from pathlib import Path

import pytest

demonstrate = runpy.run_path(
    str(Path(__file__).resolve().parents[1] / "scripts/portfolio_demo.py")
)["demonstrate"]


@pytest.mark.parametrize(
    "ready",
    [
        {"provider": "gemini", "simulated": False, "database": "ready"},
        {"provider": "fake", "simulated": False, "database": "ready"},
        {"provider": "fake", "simulated": True, "database": "disabled"},
        {},
    ],
)
def test_demo_refuses_before_any_mutation(ready):
    calls = []

    def request(path, *args):
        calls.append((path, args))
        return ready

    with pytest.raises(RuntimeError, match="explicitly simulated"):
        demonstrate(request)
    assert calls == [("/health/ready", ())]
