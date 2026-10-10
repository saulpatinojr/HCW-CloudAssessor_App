import pytest

from cloud_assessor_appliance.collectors.scope import Scope, ScopeAllowlist, ScopeError

from ..conftest import FICTIONAL_SUBSCRIPTION, SCOPE

SUB2 = "00000000-0000-0000-0000-000000000002"


def test_parse_both_shapes_dedupes_and_lowercases():
    a = ScopeAllowlist.parse(f"{SCOPE}, /Subscriptions/{SUB2.upper()}/resourceGroups/rg-App {SCOPE}/")
    assert a.scopes == (Scope(FICTIONAL_SUBSCRIPTION), Scope(SUB2, "rg-App"))
    assert a.subscriptions() == [FICTIONAL_SUBSCRIPTION, SUB2]
    assert a.scopes[1].id == f"/subscriptions/{SUB2}/resourceGroups/rg-App"
    assert ScopeAllowlist.from_env({"CA_SCOPES": SCOPE}).subscriptions() == [FICTIONAL_SUBSCRIPTION]


@pytest.mark.parametrize(
    "value",
    [
        "",
        "   ",
        "/subscriptions/not-a-guid",
        "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/",
        "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/bad'name",
        "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/ends.",
        "/subscriptions/00000000-0000-0000-0000-000000000001/providers/x",
        "/providers/Microsoft.Management/managementGroups/mg",
        "00000000-0000-0000-0000-000000000001",
    ],
)
def test_reject_malformed(value):
    with pytest.raises(ScopeError):
        ScopeAllowlist.parse(value)
    with pytest.raises(ScopeError):
        ScopeAllowlist.from_env({"CA_SCOPES": value})
    with pytest.raises(ScopeError):
        ScopeAllowlist.from_env({})


def test_kql_filter_is_pinned():
    assert ScopeAllowlist.parse(SCOPE).kql_filter() == f"subscriptionId in~ ('{FICTIONAL_SUBSCRIPTION}')"
    mixed = ScopeAllowlist.parse(f"{SCOPE} /subscriptions/{SUB2}/resourceGroups/rg-app")
    assert mixed.kql_filter() == (
        f"subscriptionId in~ ('{FICTIONAL_SUBSCRIPTION}', '{SUB2}') and "
        f"(subscriptionId =~ '{FICTIONAL_SUBSCRIPTION}' or (subscriptionId =~ '{SUB2}' and resourceGroup =~ 'rg-app'))"
    )


def test_assert_contains_rejects_foreign_subscription_and_group():
    a = ScopeAllowlist.parse(f"{SCOPE} /subscriptions/{SUB2}/resourceGroups/rg-app")
    a.assert_contains(f"{SCOPE}/resourceGroups/any/providers/microsoft.compute/disks/d")
    a.assert_contains(f"/SUBSCRIPTIONS/{FICTIONAL_SUBSCRIPTION.upper()}/resourcegroups/x/providers/a/b/c")
    a.assert_contains(f"/subscriptions/{SUB2}/resourceGroups/RG-APP/providers/a/b/c")
    for bad in (
        "/subscriptions/00000000-0000-0000-0000-000000000009/resourceGroups/rg-app/providers/a/b/c",
        f"/subscriptions/{SUB2}/resourceGroups/rg-other/providers/a/b/c",
        f"/subscriptions/{SUB2}",
        "",
        "/providers/Microsoft.Management/managementGroups/mg",
    ):
        assert not a.contains(bad)
        with pytest.raises(ScopeError):
            a.assert_contains(bad)
