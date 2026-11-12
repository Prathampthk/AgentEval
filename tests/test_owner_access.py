import base64
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from agenteval.api import create_app
from agenteval.providers import FakeProvider

TOKEN = "synthetic-test-token-" + "x" * 32


@pytest.mark.parametrize(
    "path",
    [
        "/health/ready",
        "/docs",
        "/openapi.json",
        "/datasets/00000000-0000-0000-0000-000000000000",
        "/dashboard/",
    ],
)
def test_protected_routes_require_authentication(path):
    with TestClient(create_app(FakeProvider(), access_token=TOKEN)) as client:
        response = client.get(path)
        assert response.status_code == 401
        assert response.headers["www-authenticate"].startswith("Basic ")
        assert TOKEN not in response.text
        assert client.get("/health/live").status_code == 200
        authenticated = client.get("/health/ready", auth=("owner", TOKEN))
        assert authenticated.status_code == 200
        assert authenticated.headers["cache-control"] == "no-store"


@pytest.mark.parametrize(
    "header",
    [
        "Bearer wrong",
        "Basic !!!",
        "Basic /w==",
        "Basic " + base64.b64encode(b"other:password").decode(),
    ],
)
def test_malformed_auth_is_denied_before_provider_work(header):
    provider = FakeProvider()
    provider.generate = AsyncMock()
    with TestClient(create_app(provider, access_token=TOKEN)) as client:
        assert (
            client.post(
                "/evaluations", content="invalid JSON", headers={"Authorization": header}
            ).status_code
            == 401
        )
        assert client.get("/health/ready", auth=("owner", "wrong")).status_code == 401
    provider.generate.assert_not_awaited()


def test_duplicate_auth_headers_are_rejected():
    encoded = base64.b64encode(("owner:" + TOKEN).encode()).decode()
    with TestClient(create_app(FakeProvider(), access_token=TOKEN)) as client:
        assert (
            client.get(
                "/health/ready", headers=[("Authorization", "Basic " + encoded)] * 2
            ).status_code
            == 401
        )


@pytest.mark.parametrize("token", ["short", "x" * 300, "x" * 31 + " ", "x" * 31 + "\n"])
def test_invalid_access_configuration_fails_before_startup(token):
    with pytest.raises(ValueError, match="Access token"):
        create_app(FakeProvider(), access_token=token)


def test_default_loopback_demo_remains_usable(monkeypatch):
    monkeypatch.delenv("AGENTEVAL_ACCESS_TOKEN", raising=False)
    with TestClient(create_app(FakeProvider())) as client:
        assert client.get("/health/ready").status_code == 200
