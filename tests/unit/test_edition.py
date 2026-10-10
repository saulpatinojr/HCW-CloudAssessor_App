import subprocess
import sys

import pytest

from cloud_assessor_appliance.edition import (
    AZURE_CONNECTIVITY,
    CAPABILITIES,
    EDITION,
    REQUIRED_MODULES,
    EditionError,
    assert_appliance_ready,
)

from ..conftest import SCOPE

PRESENT = {m: object() for m in REQUIRED_MODULES}


def test_constants():
    assert EDITION == "appliance" and AZURE_CONNECTIVITY == "managed-identity"
    assert set(CAPABILITIES) >= {"scorecard", "findings", "bundle-zip", "live-resource-graph", "live-cost"}
    assert "upload-arg-json" not in CAPABILITIES and "sample-data" not in CAPABILITIES


def test_ready_returns_the_allowlist():
    allowlist = assert_appliance_ready({"CA_SCOPES": SCOPE}, find_spec=PRESENT.get)
    assert allowlist.subscriptions() == ["00000000-0000-0000-0000-000000000001"]


def test_refuses_without_the_extra():
    with pytest.raises(EditionError, match="azure extra not installed"):
        assert_appliance_ready({"CA_SCOPES": SCOPE}, find_spec=lambda m: None)
    partial = {"azure.identity": object()}
    with pytest.raises(EditionError, match="azure.mgmt.resourcegraph"):
        assert_appliance_ready({"CA_SCOPES": SCOPE}, find_spec=partial.get)


@pytest.mark.parametrize("env", [{}, {"CA_SCOPES": ""}, {"CA_SCOPES": "/subscriptions/nope"}])
def test_refuses_bad_scopes(env):
    with pytest.raises(EditionError, match="CA_SCOPES"):
        assert_appliance_ready(env, find_spec=PRESENT.get)


def test_refuses_forbidden_credential_variables():
    with pytest.raises(EditionError, match="AZURE_CLIENT_SECRET"):
        assert_appliance_ready({"CA_SCOPES": SCOPE, "AZURE_CLIENT_SECRET": "x"}, find_spec=PRESENT.get)


def test_main_refuses_with_exit_code_3_and_scrubs():
    proc = subprocess.run(
        [sys.executable, "-m", "cloud_assessor_appliance"],
        env={
            "PATH": "/usr/bin:/bin",
            "CA_SCOPES": SCOPE,
            "AZURE_CLIENT_SECRET": "not-a-real-secret-value",
            "PYTHONPATH": ":".join(sys.path),
        },
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 3 and "startup_refused" in proc.stderr and "not-a-real" not in proc.stderr
    proc = subprocess.run(
        [sys.executable, "-m", "cloud_assessor_appliance"],
        env={"PATH": "/usr/bin:/bin", "PYTHONPATH": ":".join(sys.path)},
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 3 and "startup_refused" in proc.stderr
