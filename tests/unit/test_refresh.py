import asyncio

import pytest
from cloud_assessor_core.catalog import load_catalog, load_scoring

from cloud_assessor_appliance.collectors.scope import ScopeAllowlist
from cloud_assessor_appliance.refresh import Refresher, hashed_scope

from ..conftest import SCOPE, FakeCostCollector, FakeResourceGraphClient, make_collector, make_evidence


def _refresher(**kw):
    allowlist = ScopeAllowlist.parse(SCOPE)
    return Refresher(
        catalog=load_catalog(),
        scoring=load_scoring(),
        allowlist=allowlist,
        resource_collector=kw.pop("resource_collector", make_collector()),
        cost_collector=kw.pop("cost_collector", FakeCostCollector(make_evidence())),
        **kw,
    )


@pytest.mark.anyio
async def test_run_builds_a_snapshot_with_edition_scope_and_evidence():
    r = _refresher()
    assert not r.snapshot.ready and r.cooldown_remaining() == 0
    assert await r.run()
    s = r.snapshot
    assert s.ready and s.resources == 40 and s.as_of_iso.endswith("Z") and s.last_error is None
    assert s.subscriptions_observed == 1
    assert set(s.files) == {"report.md", "report.json", "findings.csv", "NOT-AN-AUDIT.md", "bundle.zip"}
    a = s.assessment
    assert a.edition == "appliance" and a.source_format == "arg-live" and a.scope == hashed_scope(r._allowlist)
    assert a.scope.count == 1 and len(a.scope.subscriptions[0]) == 64 and "00000000" not in a.scope.subscriptions[0]
    cost = {f.criterionId: f for f in a.findings if f.criterionId in ("CA-FIN-003", "CA-FIN-007")}
    assert all(f.state == "observed" for f in cost.values())


@pytest.mark.anyio
async def test_failed_collection_keeps_the_previous_snapshot():
    r = _refresher()
    await r.run()
    first = r.snapshot
    r._resources = make_collector(client=FakeResourceGraphClient(throttle=99))
    assert await r.run()
    assert r.snapshot is first and r.snapshot.last_error == "collector_error" and r.runs == 1

    class Boom:
        def collect(self):
            raise ValueError("unexpected")

    r._resources = Boom()
    assert await r.run()
    assert r.snapshot is first and r.snapshot.last_error == "internal_error"


@pytest.mark.anyio
async def test_timeout_releases_the_lock_and_keeps_the_previous_snapshot():
    import threading

    class Slow:
        def collect(self):
            threading.Event().wait(0.3)
            raise AssertionError("the abandoned thread's result must be dropped, never raised into the loop")

    r = _refresher()
    await r.run()
    first = r.snapshot
    r._resources = Slow()
    r._timeout = 0.05
    assert await r.run()
    assert r.snapshot is first and r.snapshot.last_error == "timeout" and not r.running and r.runs == 1
    assert first.age_seconds(first.as_of) == 0
    r._resources = make_collector()
    r._timeout = 5.0
    assert await r.run() and r.runs == 2 and r.snapshot.last_error is None


@pytest.mark.anyio
async def test_single_flight_and_cooldown():
    now = [100.0]
    r = _refresher(cooldown_seconds=600, clock=lambda: now[0])
    assert r.request() == "queued" and r.cooldown_remaining() == 600
    assert r._task is not None and not r._task.done(), "the queued task is held, not left to the garbage collector"
    await asyncio.sleep(0)
    assert r.request() == "cooldown", "the cooldown is checked before the single-flight lock"
    while r.running:
        await asyncio.sleep(0.01)
    assert r.snapshot.ready
    await asyncio.sleep(0)
    assert r._task is None, "the done callback drops the reference"
    assert r.request() == "cooldown"
    now[0] += 599.5
    assert r.cooldown_remaining() == 1 and r.request() == "cooldown"
    now[0] += 1
    assert r.request() == "queued"
    for _ in range(500):
        if r.runs == 2:
            break
        await asyncio.sleep(0.01)
    assert r.runs == 2


@pytest.mark.anyio
async def test_run_returns_false_while_another_run_holds_the_lock_and_request_reports_running():
    r = _refresher()
    async with r._lock:
        assert r.running and not await r.run()
        assert r.request() == "running"


@pytest.mark.anyio
async def test_timer_runs_then_sleeps_and_cost_disabled_logs_skip():
    r = _refresher(cost_collector=None)
    task = asyncio.create_task(r.timer(1000))
    for _ in range(200):
        if r.snapshot.ready:
            break
        await asyncio.sleep(0.01)
    task.cancel()
    assert r.snapshot.ready and r.snapshot.assessment.findings
    unknown = {f.criterionId for f in r.snapshot.assessment.findings if f.state == "unknown"}
    assert "CA-FIN-003" in unknown
