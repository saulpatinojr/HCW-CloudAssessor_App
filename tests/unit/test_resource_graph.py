import pytest

from cloud_assessor_appliance.collectors.resource_graph import (
    ATTEMPTS,
    CollectorError,
    Page,
    ResourceGraphCollector,
    ThrottledError,
)
from cloud_assessor_appliance.collectors.scope import ScopeAllowlist

from ..conftest import FICTIONAL_SUBSCRIPTION, SCOPE, FakeResourceGraphClient, make_collector, sample_rows


def test_two_pages_joined_skip_token_honoured_and_scope_filter_in_query():
    client = FakeResourceGraphClient(page_rows=25)
    collector = make_collector(client=client)
    out = collector.collect()
    assert out.rows == 40 and len(out.resources) == 40 and out.warnings == []
    assert [c["skip_token"] for c in client.calls] == [None, "25"]
    assert all(c["subscriptions"] == [FICTIONAL_SUBSCRIPTION] for c in client.calls)
    allowlist = ScopeAllowlist.parse(SCOPE)
    assert allowlist.kql_filter() in client.calls[0]["query"] and client.calls[0]["query"].startswith("resources |")
    assert all(r.model_version == 1 and r.source.format == "arg-live" for r in out.resources)
    assert out.resources[0].source.row == 1


def test_collect_has_no_scope_parameter():
    collector = make_collector()
    with pytest.raises(TypeError):
        collector.collect(scopes=["/subscriptions/00000000-0000-0000-0000-000000000009"])  # type: ignore[call-arg]


def test_429_then_success_backs_off_with_retry_after_and_jitter():
    slept: list[float] = []
    client = FakeResourceGraphClient(throttle=2)
    allowlist = ScopeAllowlist.parse(SCOPE)
    collector = ResourceGraphCollector(client, allowlist, sleep=slept.append, rng=lambda: 0.5)
    assert collector.collect().rows == 40
    assert slept == [1.0, 1.0] and len(client.calls) == 3

    class NoHeader:
        calls = 0

        def query(self, **kw):
            self.calls += 1
            if self.calls < 3:
                raise ThrottledError(None)
            return Page(rows=sample_rows())

    slept.clear()
    collector = ResourceGraphCollector(NoHeader(), allowlist, sleep=slept.append, rng=lambda: 0.5)
    assert collector.collect().rows == 40
    assert slept == [3.0, 5.0]  # 2*2^0 + 1 jitter, 2*2^1 + 1 jitter


def test_throttled_five_times_raises_collector_error():
    slept: list[float] = []
    client = FakeResourceGraphClient(throttle=ATTEMPTS)
    collector = ResourceGraphCollector(client, ScopeAllowlist.parse(SCOPE), sleep=slept.append)
    with pytest.raises(CollectorError, match=f"throttled by the service after {ATTEMPTS} attempts"):
        collector.collect()
    assert len(client.calls) == ATTEMPTS and len(slept) == ATTEMPTS - 1 and all(s <= 60 for s in slept)


def test_foreign_resource_in_the_response_is_refused():
    rows = sample_rows()
    rows[3] = dict(rows[3], id="/subscriptions/00000000-0000-0000-0000-000000000009/resourceGroups/x/providers/a/b/c")
    with pytest.raises(CollectorError, match="outside"):
        make_collector(client=FakeResourceGraphClient(rows)).collect()


def test_max_rows_caps_with_a_warning_not_a_failure():
    collector = make_collector(client=FakeResourceGraphClient(page_rows=10), max_rows=15)
    out = collector.collect()
    assert out.rows == 15 and len(out.resources) == 15 and any("capped at 15" in w for w in out.warnings)


def test_empty_scope_and_truncated_result_and_adapter_errors():
    class Empty:
        def query(self, **kw):
            return Page(rows=[], truncated=True)

    out = ResourceGraphCollector(Empty(), ScopeAllowlist.parse(SCOPE)).collect()
    assert out.resources == [] and out.rows == 0 and "no resources" in out.warnings[0]

    class Broken:
        def query(self, **kw):
            raise RuntimeError("boom /subscriptions/00000000-0000-0000-0000-000000000001/x")

    with pytest.raises(CollectorError) as exc:
        ResourceGraphCollector(Broken(), ScopeAllowlist.parse(SCOPE)).collect()
    assert "00000000-0000" not in str(exc.value) and "<redacted>" in str(exc.value)


def test_http_status_names_the_class_when_there_is_no_status():
    from cloud_assessor_appliance.collectors.resource_graph import http_status

    class WithStatus(Exception):
        status_code = 403

    class NoStatus(Exception):
        status_code = None

    assert http_status(WithStatus()) == "403" and http_status(NoStatus()) == "NoStatus"
    assert http_status(RuntimeError()) == "RuntimeError"


def test_page_size_is_clamped_to_the_service_maximum():
    client = FakeResourceGraphClient()
    make_collector(client=client, page_size=5000).collect()
    assert client.calls[0]["top"] == 1000
