import importlib.util

import pytest
from cloud_assessor_core.model import BudgetEvidence

from cloud_assessor_appliance.collectors.cost_management import (
    COST_CENTER_TAG,
    CostAccessError,
    CostManagementCollector,
)
from cloud_assessor_appliance.collectors.resource_graph import CollectorError, ThrottledError
from cloud_assessor_appliance.collectors.scope import ScopeAllowlist

from ..conftest import SCOPE


class FakeCostClient:
    def __init__(self, *, raise_exc=None) -> None:
        self.raise_exc = raise_exc
        self.calls: list[tuple] = []

    def actual_cost(self, scope, *, group_by):
        self.calls.append(("actual_cost", scope, group_by))
        if self.raise_exc:
            raise self.raise_exc
        if group_by == ("Dimension", "ResourceGroup"):
            return ["Cost", "ResourceGroup", "Currency"], [[600.0, "RG-A", "USD"], ["400", "rg-b", "USD"]]
        assert group_by == ("TagKey", COST_CENTER_TAG)
        return ["Cost", "TagKey", "TagValue", "Currency"], [
            [750.0, "costCenter", "cc-1", "USD"],
            [250.0, "", "", "USD"],
        ]

    def budgets(self, scope):
        self.calls.append(("budgets", scope))
        return [BudgetEvidence(name="hcw-sample-budget", amount=1000.0, time_grain="Monthly", notifications=2)]

    def anomaly_alerts(self, scope):
        self.calls.append(("anomaly_alerts", scope))
        return ["hcw-sample-anomaly", "hcw-sample-anomaly"]


@pytest.mark.anyio
async def test_query_shape_pinned_and_evidence_derived():
    client = FakeCostClient()
    collector = CostManagementCollector(client, ScopeAllowlist.parse(SCOPE))
    e = await collector.collect()
    assert [c[0] for c in client.calls] == ["actual_cost", "actual_cost", "budgets", "anomaly_alerts"]
    assert client.calls[0] == ("actual_cost", SCOPE, ("Dimension", "ResourceGroup"))
    assert client.calls[1] == ("actual_cost", SCOPE, ("TagKey", "costCenter"))
    assert e is not None and e.scope == SCOPE and e.currency == "USD" and e.total == 1000.0
    assert e.by_resource_group == {"rg-a": 600.0, "rg-b": 400.0}
    assert e.by_cost_center_tag == {"cc-1": 750.0, "": 250.0} and e.untagged_share == 25.0
    assert [b.name for b in e.budgets] == ["hcw-sample-budget"] and e.anomaly_alerts == ["hcw-sample-anomaly"]
    assert e.period_start.day == 1 and e.period_end >= e.period_start


@pytest.mark.anyio
async def test_cache_hit_within_the_window_and_refresh_after():
    now = [0.0]
    client = FakeCostClient()
    collector = CostManagementCollector(client, ScopeAllowlist.parse(SCOPE), cache_minutes=60, clock=lambda: now[0])
    first = await collector.collect()
    second = await collector.collect()
    assert first is second and len(client.calls) == 4 and collector.cached is first
    now[0] += 3601
    third = await collector.collect()
    assert third is not first and len(client.calls) == 8


@pytest.mark.anyio
@pytest.mark.parametrize("exc", [ThrottledError(5), CostAccessError(), CollectorError("x")])
async def test_none_on_throttle_or_missing_role_keeps_stale_cache(exc):
    collector = CostManagementCollector(FakeCostClient(raise_exc=exc), ScopeAllowlist.parse(SCOPE))
    assert await collector.collect() is None
    good = CostManagementCollector(FakeCostClient(), ScopeAllowlist.parse(SCOPE), cache_minutes=0)
    evidence = await good.collect()
    good._client = FakeCostClient(raise_exc=exc)
    assert await good.collect() is evidence


@pytest.mark.anyio
async def test_adapter_leaks_are_wrapped_and_scrubbed():
    class Leaky(FakeCostClient):
        def budgets(self, scope):
            raise RuntimeError("sub /subscriptions/00000000-0000-0000-0000-000000000001/x")

    collector = CostManagementCollector(Leaky(), ScopeAllowlist.parse(SCOPE))
    with pytest.raises(CollectorError) as exc:
        collector.collect_sync()
    assert "00000000-0000" not in str(exc.value)
    assert await collector.collect() is None


def test_zero_spend_and_odd_columns():
    class Zero(FakeCostClient):
        def actual_cost(self, scope, *, group_by):
            return ["Other"], [["x"], []]

    e = CostManagementCollector(Zero(), ScopeAllowlist.parse(SCOPE)).collect_sync()
    assert e.total == 0.0 and e.untagged_share == 0.0 and e.currency == "unknown"


@pytest.mark.skipif(importlib.util.find_spec("azure") is None, reason="azure extra not installed")
def test_sdk_adapters_build_without_network():
    from cloud_assessor_appliance.collectors.cost_management import SdkCostClient
    from cloud_assessor_appliance.collectors.resource_graph import SdkResourceGraphClient

    class Cred:
        def get_token(self, *a, **k):
            raise RuntimeError("no network in tests")

        def get_token_info(self, *a, **k):
            raise RuntimeError("no network in tests")

    assert SdkCostClient(Cred())._client is not None and SdkResourceGraphClient(Cred())._client is not None
    from azure.core.exceptions import ClientAuthenticationError, HttpResponseError

    client = SdkCostClient(Cred())

    def raise_auth():
        raise ClientAuthenticationError("no token")

    with pytest.raises(CostAccessError):
        client._guard(raise_auth)

    def raise_500():
        raise HttpResponseError(message="boom")

    with pytest.raises(CollectorError, match="HTTP HttpResponseError"):
        client._guard(raise_500)
