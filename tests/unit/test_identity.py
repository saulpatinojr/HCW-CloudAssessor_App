import importlib.util

import pytest

from cloud_assessor_appliance.identity import FORBIDDEN_ENV, IdentityError, build_credential, refuse_forbidden_env

CLIENT_ID = "00000000-0000-4000-8000-000000000001"


class Fake:
    def __init__(self, **kwargs) -> None:
        self.kwargs = kwargs


@pytest.mark.parametrize("name", FORBIDDEN_ENV)
def test_forbidden_variables_refuse_startup(name):
    with pytest.raises(IdentityError, match=name):
        refuse_forbidden_env({name: "x"})
    with pytest.raises(IdentityError, match=name):
        build_credential({name: "x", "AZURE_CLIENT_ID": CLIENT_ID}, managed_identity=Fake, default=Fake)
    refuse_forbidden_env({name: "   "})  # blank is absent


def test_client_id_selects_managed_identity_without_network():
    cred = build_credential({"AZURE_CLIENT_ID": CLIENT_ID}, managed_identity=Fake, default=Fake)
    assert cred.kwargs == {"client_id": CLIENT_ID}
    cred = build_credential({}, managed_identity=Fake, default=Fake)
    assert cred.kwargs == {"exclude_interactive_browser_credential": True, "exclude_environment_credential": True}
    with pytest.raises(IdentityError, match="GUID"):
        build_credential({"AZURE_CLIENT_ID": "not-a-guid"}, managed_identity=Fake, default=Fake)


def test_factory_failures_are_scrubbed():
    def boom(**kwargs):
        raise RuntimeError("tenant 11111111-2222-3333-4444-555555555555 at /subscriptions/x")

    with pytest.raises(IdentityError) as exc:
        build_credential({"AZURE_CLIENT_ID": CLIENT_ID}, managed_identity=boom, default=Fake)
    assert "11111111" not in str(exc.value) and "<redacted>" in str(exc.value)


@pytest.mark.skipif(importlib.util.find_spec("azure") is None, reason="azure extra not installed")
def test_real_sdk_classes_are_selected():
    from azure.identity import DefaultAzureCredential, ManagedIdentityCredential

    assert isinstance(build_credential({"AZURE_CLIENT_ID": CLIENT_ID}), ManagedIdentityCredential)
    assert isinstance(build_credential({}), DefaultAzureCredential)


@pytest.mark.skipif(importlib.util.find_spec("azure") is not None, reason="azure extra installed")
def test_without_extra_the_factory_refuses():
    with pytest.raises(IdentityError, match="azure extra"):
        build_credential({"AZURE_CLIENT_ID": CLIENT_ID})
