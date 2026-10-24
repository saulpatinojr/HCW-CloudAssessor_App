import io
import json
import threading
import zipfile

from fastapi.testclient import TestClient

from cloud_assessor_appliance import __version__
from cloud_assessor_appliance.api import api_routes, create_app
from cloud_assessor_appliance.collectors.resource_graph import CollectorError
from cloud_assessor_appliance.config import TURNSTILE_ACTION
from cloud_assessor_appliance.security.headers import VERIFICATION_ORIGIN

from ..conftest import (
    NO_AZURE_ENV,
    FakeCostCollector,
    FakeResourceGraphClient,
    HangingCollector,
    make_app,
    make_settings,
    run_refresh,
)

RESULTS_ROUTES = (
    "/api/assessments/current",
    "/api/assessments/current/report.md",
    "/api/assessments/current/report.json",
    "/api/assessments/current/bundle.zip",
)


def test_health_is_flat_complete_and_fast_with_a_hanging_collector(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True and body["id"] == "cloud-assessment" and body["version"] == __version__
    assert body["edition"] == "appliance" and body["azureConnectivity"] == "managed-identity"
    assert body["scope"] == {"count": 1, "configured": 1, "observed": 0} and body["publicResults"] is False
    assert body["lastRun"] is None and body["lastError"] is None and body["snapshotAgeSeconds"] is None
    assert body["turnstile"] == {"required": False, "siteKey": None, "action": TURNSTILE_ACTION}
    assert body["siteOrigins"] == ["https://hybridcloudworks.com"] and body["asOf"].endswith("Z")
    assert body["catalog"] == {"version": "1.1.0", "count": 25}
    assert "live-resource-graph" in body["capabilities"] and "upload-arg-json" not in body["capabilities"]
    assert "limits" not in body and "addon" not in body
    assert r.headers["x-addon-id"] == "cloud-assessment" and r.headers["x-addon-version"] == __version__
    assert r.headers["x-content-type-options"] == "nosniff" and r.headers["referrer-policy"] == "no-referrer"
    assert r.headers["cache-control"] == "no-store" and r.headers["x-frame-options"] == "DENY"
    assert "frame-ancestors 'none'" in r.headers["content-security-policy"]
    import time

    app = create_app(
        make_settings(public_results=True),
        resource_collector=HangingCollector(),
        cost_collector=FakeCostCollector(None),
        timer=True,
        env=NO_AZURE_ENV,
    )
    with TestClient(app) as c:
        started = time.monotonic()
        assert c.get("/api/health").status_code == 200
        assert time.monotonic() - started < 1.0
        r = c.get("/api/assessments/current")
        assert r.status_code == 503 and r.json()["error"]["code"] == "no_snapshot"


def test_health_reports_a_timeout_and_keeps_the_previous_snapshot():
    app = make_app(make_settings(public_results=True, collect_timeout_seconds=1))
    with TestClient(app) as c:
        run_refresh(c)
        first = c.get("/api/health").json()["lastRun"]
        app.state.refresher._resources = HangingCollector()
        app.state.refresher._timeout = 0.05
        run_refresh(c)
        health = c.get("/api/health").json()
        assert health["lastError"] == "timeout" and health["lastRun"] == first
        assert not app.state.refresher.running, "the single-flight lock is released after a timeout"
        assert c.get("/api/assessments/current").status_code == 200


def test_health_is_degraded_before_the_first_collection(client):
    r = client.get("/api/health")
    body = r.json()
    assert r.status_code == 200 and body["ok"] is True, "probes and the pane keep reading 200 and ok"
    assert body["status"] == "degraded" and body["degradedReason"] == "no_snapshot"


def test_health_is_ok_after_a_good_collection(client):
    run_refresh(client)
    body = client.get("/api/health").json()
    assert body["status"] == "ok" and body["degradedReason"] is None and body["lastError"] is None


def test_health_is_degraded_when_the_collector_fails_and_recovers():
    class Failing:
        def collect(self):
            raise CollectorError("sub hcw-sample-leak boom /subscriptions/x")

    app = make_app(make_settings(public_results=True))
    with TestClient(app) as c:
        good = app.state.refresher._resources
        app.state.refresher._resources = Failing()
        run_refresh(c)  # failing before any snapshot
        r = c.get("/api/health")
        assert r.status_code == 200 and r.json()["status"] == "degraded"
        assert r.json()["degradedReason"] == "collector_error"
        # no identifier or exception text leaks anywhere in the body
        for fragment in ("hcw-sample-leak", "boom", "/subscriptions/x", "CollectorError"):
            assert fragment not in r.text
        app.state.refresher._resources = good
        run_refresh(c)
        assert c.get("/api/health").json()["status"] == "ok"
        app.state.refresher._resources = Failing()
        run_refresh(c)  # failing with a kept snapshot is still degraded
        body = c.get("/api/health").json()
        assert body["status"] == "degraded" and body["degradedReason"] == "collector_error" and body["lastRun"]


def test_health_degraded_on_timeout_keeps_ok_true():
    app = make_app(make_settings(public_results=True, collect_timeout_seconds=1))
    with TestClient(app) as c:
        app.state.refresher._resources = HangingCollector()
        app.state.refresher._timeout = 0.05
        run_refresh(c)
        body = c.get("/api/health").json()
        assert body["ok"] is True and body["status"] == "degraded" and body["degradedReason"] == "timeout"


def test_post_assessments_is_edition_readonly(client):
    for method in ("POST", "PUT", "PATCH", "DELETE"):
        r = client.request(method, "/api/assessments", content=b"{}", headers={"content-type": "application/json"})
        assert r.status_code == 405, method
        assert r.json() == {
            "error": {"code": "edition_readonly", "message": "This edition reads its own scope; nothing is uploaded."}
        }
    assert client.get("/api/assessments").status_code == 405
    assert client.get("/api/assessments/abc").status_code == 404
    assert client.delete("/api/assessments/abc").status_code == 404
    assert client.get("/api/sample.json").status_code == 404
    table = api_routes(client.app)
    assert table["/api/assessments"] == {"POST", "PUT", "PATCH", "DELETE"} and table["/api/refresh"] == {"POST"}
    assert "/api/assessments/{assessment_id}" not in table and "/api/{rest:path}" not in table


def test_no_snapshot_503_before_the_first_run_whatever_the_gate():
    for public in (False, True):
        with TestClient(make_app(make_settings(public_results=public))) as c:
            for route in RESULTS_ROUTES:
                r = c.get(route)
                assert r.status_code == 503 and r.json()["error"]["code"] == "no_snapshot", route
                assert r.headers["retry-after"] == "30"


def test_results_not_public_403_on_all_four_routes_once_a_snapshot_exists(client):
    run_refresh(client)
    assert client.get("/api/health").json()["lastRun"].endswith("Z")
    for route in RESULTS_ROUTES:
        r = client.get(route)
        assert r.status_code == 403, route
        assert r.json() == {
            "error": {"code": "results_not_public", "message": "Results are not published for this deployment."}
        }


def test_results_200_with_the_gate_open_and_a_snapshot(public_client):
    c = public_client
    health = c.get("/api/health").json()
    assert health["publicResults"] is True and health["lastRun"].endswith("Z")
    assert health["scope"] == {"count": 1, "configured": 1, "observed": 1} and health["lastError"] is None
    assert isinstance(health["snapshotAgeSeconds"], int) and 0 <= health["snapshotAgeSeconds"] < 3600
    r = c.get("/api/assessments/current")
    assert r.status_code == 200
    body = r.json()
    assert set(body) == {"assessment", "files", "asOf", "scope"}
    assert body["scope"] == {"count": 1, "configured": 1, "observed": 1}
    assert sorted(body["files"]) == ["NOT-AN-AUDIT.md", "bundle.zip", "findings.csv", "report.json", "report.md"]
    a = body["assessment"]
    assert a["edition"] == "appliance" and a["source_format"] == "arg-live" and a["model_version"] == 1
    assert a["catalog_version"] == "1.1.0" and a["core_version"] == "0.2.1" and a["summary"]["resourceCount"] == 40
    assert a["scope"]["count"] == 1 and len(a["scope"]["subscriptions"][0]) == 64
    cost = [f for f in a["findings"] if f["criterionId"] in ("CA-FIN-002", "CA-FIN-003", "CA-FIN-007")]
    assert cost and all(f["state"] == "observed" for f in cost)
    md = c.get("/api/assessments/current/report.md")
    assert md.status_code == 200 and md.headers["content-type"].startswith("text/markdown")
    assert md.headers["content-disposition"] == 'attachment; filename="assessment-current.md"'
    js = c.get("/api/assessments/current/report.json")
    assert js.status_code == 200 and js.json()["edition"] == "appliance" and js.json()["id"] == a["id"]
    z = c.get("/api/assessments/current/bundle.zip")
    assert z.status_code == 200 and z.headers["content-type"] == "application/zip"
    assert sorted(zipfile.ZipFile(io.BytesIO(z.content)).namelist()) == [
        "NOT-AN-AUDIT.md",
        "findings.csv",
        "report.json",
        "report.md",
    ]
    assert c.get("/api/assessments/current/files/findings.csv").status_code == 404


def test_catalog_route_matches_the_lab_shape(client):
    k = client.get("/api/catalog").json()
    assert k["version"] == "1.1.0" and k["count"] == 25 and k["criteria"][0]["id"] == "CA-FIN-001"
    assert {c["kind"] for cr in k["criteria"] for c in cr["checks"]} >= {"cost-evidence", "tag-present"}
    assert all(c["learnUrl"].startswith("https://") for c in k["criteria"])


def test_cost_disabled_leaves_cost_criteria_unknown():
    app = make_app(make_settings(public_results=True, cost_enabled=False))
    with TestClient(app) as c:
        run_refresh(c)
        findings = c.get("/api/assessments/current").json()["assessment"]["findings"]
        assert next(f for f in findings if f["criterionId"] == "CA-FIN-003")["state"] == "unknown"
    assert app.state.refresher._cost is None


class BlockingClient(FakeResourceGraphClient):
    """Holds the single-flight lock until `gate` is set, so the running state is deterministic in tests."""

    def __init__(self, **kw):
        super().__init__(**kw)
        self.gate = threading.Event()

    def query(self, **kw):
        self.gate.wait(5)
        return super().query(**kw)


def _wait(predicate, tries=500):
    for _ in range(tries):
        if predicate():
            return True
        threading.Event().wait(0.01)
    return predicate()


def test_refresh_inside_the_cooldown_answers_429_even_while_that_run_is_in_progress():
    client = BlockingClient()
    app = make_app(make_settings(refresh_cooldown_minutes=10, rate_limit_posts=100), client=client)
    with TestClient(app) as c:
        r = c.post("/api/refresh")
        assert r.status_code == 202 and r.json() == {"queued": True, "lastRun": None}
        assert _wait(lambda: app.state.refresher.running)
        r = c.post("/api/refresh")  # the run is in progress, and we are inside its cooldown: globally bounded first
        assert r.status_code == 429 and r.json()["error"]["code"] == "rate_limited"
        assert 0 < int(r.headers["retry-after"]) <= 600 and r.json()["error"]["details"]["retryAfter"] <= 600
        client.gate.set()
        assert _wait(lambda: not app.state.refresher.running and app.state.refresher.snapshot.ready)
        r = c.post("/api/refresh")  # still inside the cooldown after the run completed
        assert r.status_code == 429 and app.state.refresher._task is None


def test_refresh_during_a_timer_started_run_answers_202_running_and_consumes_no_token():
    client = BlockingClient()
    app = make_app(make_settings(rate_limit_posts=1), client=client)
    with TestClient(app) as c:
        c.portal.start_task_soon(app.state.refresher.run)  # a run the timer would have started: no cooldown
        assert _wait(lambda: app.state.refresher.running)
        r = c.post("/api/refresh")
        assert r.status_code == 202 and r.json() == {"queued": False, "running": True, "lastRun": None}
        client.gate.set()
        assert _wait(lambda: not app.state.refresher.running and app.state.refresher.snapshot.ready)
        assert c.post("/api/refresh").status_code == 202, "the single-flight answer consumed no bucket token"


def test_refresh_per_client_bucket():
    client = BlockingClient()
    client.gate.set()
    app = make_app(make_settings(rate_limit_posts=2), client=client)
    with TestClient(app) as c:
        assert c.post("/api/refresh").status_code == 202
        assert _wait(lambda: app.state.refresher.runs == 1 and not app.state.refresher.running)
        assert c.post("/api/refresh").status_code == 202
        assert _wait(lambda: app.state.refresher.runs == 2 and not app.state.refresher.running)
        r = c.post("/api/refresh")
        assert r.status_code == 429 and r.json()["error"]["code"] == "rate_limited"
        assert int(r.headers["retry-after"]) >= 1
        r = c.post("/api/refresh", headers={"x-forwarded-for": "203.0.113.9"})
        assert r.status_code == 429, "X-Forwarded-For is ignored unless CA_TRUST_PROXY=1"


def test_global_cooldown_is_shared_across_client_addresses():
    now = [1000.0]
    app = make_app(make_settings(refresh_cooldown_minutes=10, rate_limit_posts=100, trust_proxy=True))
    app.state.refresher._clock = lambda: now[0]
    with TestClient(app) as c:
        assert c.post("/api/refresh", headers={"x-forwarded-for": "203.0.113.1"}).status_code == 202
        r = c.post("/api/refresh", headers={"x-forwarded-for": "203.0.113.2"})
        assert r.status_code == 429 and r.json()["error"]["code"] == "rate_limited"
        assert 0 < int(r.headers["retry-after"]) <= 600 and r.json()["error"]["details"]["retryAfter"] <= 600
        now[0] += 601
        assert _wait(lambda: not app.state.refresher.running)
        assert c.post("/api/refresh", headers={"x-forwarded-for": "203.0.113.3"}).status_code == 202


def test_turnstile_on_refresh_with_mocked_siteverify():
    calls = []

    def opener(request, timeout):
        form = dict(p.split("=") for p in request.data.decode().split("&"))
        calls.append(form)
        if form["response"] == "good":
            return json.dumps({"success": True, "action": TURNSTILE_ACTION}).encode()
        if form["response"] == "wrong-action":
            return json.dumps({"success": True, "action": "cloud-assessment-upload"}).encode()
        return json.dumps({"success": False, "error-codes": ["invalid-input-response"]}).encode()

    app = make_app(
        make_settings(turnstile_secret="secret-value", turnstile_site_key="site-key", rate_limit_posts=10),
        verifier=opener,
    )
    with TestClient(app) as c:
        health = c.get("/api/health").json()
        assert health["turnstile"] == {"required": True, "siteKey": "site-key", "action": TURNSTILE_ACTION}
        directives = [d.split() for d in c.get("/").headers["content-security-policy"].split(";") if d.strip()]
        csp = {d[0]: d[1:] for d in directives}
        assert csp["script-src"] == ["'self'", VERIFICATION_ORIGIN] and csp["frame-src"] == [VERIFICATION_ORIGIN]
        r = c.post("/api/refresh")
        assert r.status_code == 403 and r.json()["error"]["details"] == {"codes": ["missing-input-response"]}
        r = c.post("/api/refresh", headers={"x-turnstile-token": "bad"})
        assert r.status_code == 403 and r.json()["error"]["details"] == {"codes": ["invalid-input-response"]}
        r = c.post("/api/refresh", headers={"x-turnstile-token": "wrong-action"})
        assert r.status_code == 403 and r.json()["error"]["details"] == {"codes": ["action-mismatch"]}
        assert app.state.refresher.cooldown_remaining() == 0, "a failed verification consumes no cooldown"
        r = c.post("/api/refresh", headers={"x-turnstile-token": "good"})
        assert r.status_code == 202 and calls[-1]["secret"] == "secret-value" and calls[-1]["remoteip"] == "testclient"


def test_api_fallthrough_404_and_405(client):
    r = client.get("/api/nope")
    assert r.status_code == 404 and r.json() == {"error": {"code": "not_found", "message": "Not found."}}
    assert client.post("/api/health").status_code == 405
    assert client.post("/api/health").json()["error"]["code"] == "method_not_allowed"
    assert client.get("/api/refresh").status_code == 405
    assert client.get("/api/").status_code == 404 and client.get("/api").status_code == 404


def test_cors_exact_origin_and_closed_by_default(client):
    pre = client.options(
        "/api/refresh", headers={"origin": "https://hybridcloudworks.com", "access-control-request-method": "POST"}
    )
    assert pre.status_code == 403
    app = make_app(make_settings(allowed_origins=("https://hybridcloudworks.com",)))
    with TestClient(app) as c:
        pre = c.options(
            "/api/refresh", headers={"origin": "https://hybridcloudworks.com", "access-control-request-method": "POST"}
        )
        assert pre.status_code == 204 and pre.headers["access-control-allow-origin"] == "https://hybridcloudworks.com"
        assert "x-owner-token" not in pre.headers["access-control-allow-headers"]
        assert "DELETE" not in pre.headers["access-control-allow-methods"]
        bad = c.options(
            "/api/refresh", headers={"origin": "https://evil.example", "access-control-request-method": "POST"}
        )
        assert bad.status_code == 403 and bad.json()["error"]["code"] == "forbidden"
        r = c.get("/api/health", headers={"origin": "https://hybridcloudworks.com"})
        assert r.headers["access-control-allow-origin"] == "https://hybridcloudworks.com"
        assert "access-control-allow-origin" not in c.get("/api/health").headers


def test_frame_ancestors_configurable():
    app = make_app(make_settings(frame_ancestors="https://hybridcloudworks.com https://www.hybridcloudworks.com"))
    with TestClient(app) as c:
        r = c.get("/")
        assert (
            "frame-ancestors https://hybridcloudworks.com https://www.hybridcloudworks.com"
            in r.headers["content-security-policy"]
        )
        assert "x-frame-options" not in r.headers


def test_unhandled_error_is_enveloped(client, monkeypatch):
    from cloud_assessor_appliance import api as api_module

    def boom(app):
        raise RuntimeError("sub /subscriptions/00000000-0000-0000-0000-000000000001/x")

    monkeypatch.setattr(api_module, "health_body", boom)
    c = TestClient(client.app, raise_server_exceptions=False)
    r = c.get("/api/health")
    assert r.status_code == 500 and r.json() == {
        "error": {"code": "internal_error", "message": "Something went wrong on our side."}
    }


def test_create_app_refuses_forbidden_env_and_bad_scopes():
    import pytest

    from cloud_assessor_appliance.collectors.scope import ScopeError
    from cloud_assessor_appliance.identity import IdentityError

    with pytest.raises(IdentityError):
        make_app.__wrapped__ if False else create_app(
            make_settings(), resource_collector=object(), timer=False, env={"AZURE_TENANT_ID": "x"}
        )
    with pytest.raises(ScopeError):
        create_app(make_settings(ca_scopes=""), resource_collector=object(), timer=False, env=NO_AZURE_ENV)
