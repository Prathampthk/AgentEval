import json
import runpy
from pathlib import Path
from types import SimpleNamespace

import pytest

capture = runpy.run_path(
    str(Path(__file__).resolve().parents[1] / "scripts/capture_lock_reproduction.py")
)["capture"]


def test_capture_preserves_failure_and_stops_before_benchmark(tmp_path, monkeypatch):
    monkeypatch.setenv(
        "AGENTEVAL_TEST_DATABASE_URL", "postgresql+asyncpg://user:synthetic@localhost/demo_test"
    )
    monkeypatch.setenv(
        "AGENTEVAL_BENCHMARK_DATABASE_URL",
        "postgresql+asyncpg://user:synthetic@localhost/demo_benchmark",
    )
    monkeypatch.setenv("GEMINI_API_KEY", "synthetic-key")
    calls = []

    def failed(command, **kwargs):
        calls.append(command)
        assert (
            "GEMINI_API_KEY" not in kwargs["env"] and kwargs["env"]["AGENTEVAL_PROVIDER"] == "fake"
        )
        return SimpleNamespace(returncode=1, stdout=b"synthetic failure", stderr=b"")

    folder = tmp_path / "capture"
    result = capture(folder, run=failed)
    assert result["status"] == "INCOMPLETE" and len(calls) == 1
    assert (folder / "step-1.log").read_bytes() == b"synthetic failure"
    assert "synthetic-key" not in json.dumps(result) and "localhost" not in json.dumps(result)
    with pytest.raises(FileExistsError):
        capture(folder, run=failed)
    assert len(calls) == 1


def test_capture_refuses_application_database_before_writing(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTEVAL_TEST_DATABASE_URL", "postgresql+asyncpg://localhost/application")
    with pytest.raises(ValueError, match="Dedicated"):
        capture(tmp_path / "refused")
    assert not (tmp_path / "refused").exists()
