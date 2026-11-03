"""Unit tests never inherit an accidentally configured development database."""

import pytest


@pytest.fixture(autouse=True)
def isolated_api_configuration(monkeypatch):
    monkeypatch.delenv("AGENTEVAL_DATABASE_URL", raising=False)
