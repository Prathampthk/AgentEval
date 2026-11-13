"""The launcher must not reconfigure another checkout or a live/remote stack."""

import copy
import runpy
from pathlib import Path

import pytest

module = runpy.run_path(str(Path(__file__).resolve().parents[1] / "scripts/run_demo.py"))


@pytest.mark.parametrize(
    "endpoint", ["ssh://synthetic.invalid", "tcp://127.0.0.1:2375", "tcp://synthetic.invalid:2376"]
)
def test_demo_refuses_remote_or_tcp_engine(endpoint):
    with pytest.raises(RuntimeError, match="local Unix-socket"):
        module["verify_local_engine"](endpoint)


@pytest.mark.parametrize("change", ["api", "worker", "database-port", "api-bind"])
def test_demo_refuses_live_or_exposed_configuration(change):
    config = {
        "services": {
            "db": {},
            "api": {
                "environment": {"AGENTEVAL_PROVIDER": "fake"},
                "ports": [{"host_ip": "127.0.0.1", "published": "8013"}],
            },
            "worker": {"environment": {"AGENTEVAL_PROVIDER": "fake"}},
        }
    }
    module["verify_configuration"](config, 8013)
    if change in {"api", "worker"}:
        config["services"][change]["environment"]["AGENTEVAL_PROVIDER"] = "gemini"
    elif change == "database-port":
        config["services"]["db"]["ports"] = [{"published": "5432"}]
    else:
        config["services"]["api"]["ports"][0]["host_ip"] = "0.0.0.0"
    with pytest.raises(RuntimeError):
        module["verify_configuration"](config, 8013)


def test_demo_preserves_foreign_checkout_and_nonfake_containers(tmp_path):
    container = {
        "Config": {
            "Labels": {
                "com.docker.compose.project": "agenteval-demo",
                "com.docker.compose.project.working_dir": str(tmp_path),
                "com.docker.compose.service": "api",
            },
            "Env": ["AGENTEVAL_PROVIDER=fake"],
        }
    }
    module["verify_existing"]([container], tmp_path)
    missing = copy.deepcopy(container)
    missing["Config"]["Labels"].pop("com.docker.compose.project.working_dir")
    with pytest.raises(RuntimeError, match="another checkout"):
        module["verify_existing"]([missing], tmp_path)
    with pytest.raises(RuntimeError, match="another checkout"):
        module["verify_existing"]([container], tmp_path / "other")
    live = copy.deepcopy(container)
    live["Config"]["Env"] = ["AGENTEVAL_PROVIDER=gemini", "GEMINI_API_KEY=SYNTHETIC_SECRET"]
    with pytest.raises(RuntimeError) as error:
        module["verify_existing"]([live], tmp_path)
    assert "SYNTHETIC_SECRET" not in str(error.value)


@pytest.mark.parametrize("profile", ["private-flag", "owner-token", "proxy-service"])
def test_demo_refuses_to_strip_existing_private_configuration(tmp_path, profile):
    container = {
        "Config": {
            "Labels": {
                "com.docker.compose.project": "agenteval-demo",
                "com.docker.compose.project.working_dir": str(tmp_path),
                "com.docker.compose.service": "api",
            },
            "Env": ["AGENTEVAL_PROVIDER=fake"],
        }
    }
    if profile == "proxy-service":
        container["Config"]["Labels"]["com.docker.compose.service"] = "proxy"
    else:
        container["Config"]["Env"].append(
            "AGENTEVAL_PRIVATE_SERVER=1"
            if profile == "private-flag"
            else "AGENTEVAL_ACCESS_TOKEN=SYNTHETIC_SECRET"
        )
    with pytest.raises(RuntimeError) as error:
        module["verify_existing"]([container], tmp_path)
    assert "SYNTHETIC_SECRET" not in str(error.value)
