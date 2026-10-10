"""No azure-*/msal* package is reachable from the default dependency set; only from the `azure` extra."""

import re
import tomllib

from ..conftest import ROOT


def _packages(text: str) -> set[str]:
    return set(re.findall(r"^([A-Za-z0-9_.-]+)==", text, re.MULTILINE))


def test_default_lock_is_sdk_free_and_azure_lock_is_a_superset():
    default = _packages((ROOT / "requirements.lock.txt").read_text(encoding="utf-8"))
    azure = _packages((ROOT / "requirements-azure.lock.txt").read_text(encoding="utf-8"))
    assert default and default < azure
    assert not {p for p in default if p.startswith(("azure", "msal", "msrest"))}
    assert {"azure-identity", "azure-mgmt-resourcegraph", "azure-mgmt-costmanagement"} <= azure
    assert {"fastapi", "uvicorn", "pydantic"} <= default


def test_uv_lock_reaches_azure_only_through_the_extra():
    lock = tomllib.loads((ROOT / "uv.lock").read_text(encoding="utf-8"))
    packages = {p["name"]: p for p in lock["package"]}
    app = packages["cloud-assessor-appliance"]
    assert all("azure" not in d["name"] for d in app.get("dependencies", []))
    extra = {d["name"] for d in app.get("optional-dependencies", {}).get("azure", [])}
    assert extra == {"azure-identity", "azure-mgmt-resourcegraph", "azure-mgmt-costmanagement"}
    core = packages["cloud-assessor-core"]
    assert [d["name"] for d in core.get("dependencies", [])] == ["pydantic"]
    assert "optional-dependencies" not in core


def test_both_lockfiles_are_hash_pinned():
    for name in ("requirements.lock.txt", "requirements-azure.lock.txt"):
        text = (ROOT / name).read_text(encoding="utf-8")
        pins = _packages(text)
        assert text.count("--hash=sha256:") >= len(pins)
        assert all(re.fullmatch(r"\d+(\.\d+)*([a-z]+\d+)?", v) for v in re.findall(r"==([^ \\\n;]+)", text)), name
