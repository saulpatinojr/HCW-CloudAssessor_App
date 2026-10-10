import io
import json
import sys
import urllib.error

import pytest
from cloud_assessor_core.redaction import VisitorDataError

from cloud_assessor_appliance.config import Settings
from cloud_assessor_appliance.security import logging as logs
from cloud_assessor_appliance.security.headers import cache_control_for, content_security_policy, security_headers
from cloud_assessor_appliance.security.ratelimit import MAX_TRACKED_CLIENTS, TokenBucketLimiter
from cloud_assessor_appliance.security.turnstile import SITEVERIFY_URL, Verdict, verify


def _opener(payload, *, raise_exc=None, capture=None):
    def opener(request, timeout):
        assert request.full_url == SITEVERIFY_URL and timeout == 5.0
        if capture is not None:
            capture.append(request.data.decode())
        if raise_exc:
            raise raise_exc
        return json.dumps(payload).encode() if not isinstance(payload, bytes) else payload

    return opener


def test_turnstile_verdicts_require_the_refresh_action():
    assert verify("s", None, "1.2.3.4") == Verdict(False, ["missing-input-response"])
    assert verify("s", "x" * 3000, None).codes == ["missing-input-response"]
    sent = []
    assert verify(
        "s", "tok", "1.2.3.4", opener=_opener({"success": True, "action": "cloud-assessment-refresh"}, capture=sent)
    ).ok
    assert "remoteip=1.2.3.4" in sent[0] and "secret=s" in sent[0]
    assert verify("s", "tok", None, opener=_opener({"success": True, "action": "cloud-assessment-upload"})).codes == [
        "action-mismatch"
    ]
    assert verify("s", "tok", None, opener=_opener({"success": False})).codes == ["invalid-input-response"]
    assert verify("s", "tok", None, opener=_opener(b"not json")).codes == ["verification-unavailable"]
    assert verify("s", "tok", None, opener=_opener([1])).codes == ["verification-unavailable"]
    assert verify("s", "tok", None, opener=_opener({}, raise_exc=urllib.error.URLError("x"))).codes == [
        "verification-unavailable"
    ]
    assert verify(
        "s", "tok", None, opener=_opener({"success": False, "error-codes": ["timeout-or-duplicate", 5]})
    ).codes == ["timeout-or-duplicate"]


def test_csp_and_headers_follow_settings():
    plain = Settings()
    csp = content_security_policy(plain)
    assert "frame-ancestors 'none'" in csp and "challenges.cloudflare.com" not in csp and "base-uri 'none'" in csp
    headers = dict(security_headers(plain))
    assert headers[b"x-frame-options"] == b"DENY" and headers[b"x-addon-id"] == b"cloud-assessment"
    framed = Settings(frame_ancestors="https://hybridcloudworks.com", turnstile_site_key="k")
    assert "frame-ancestors https://hybridcloudworks.com" in content_security_policy(framed)
    assert b"x-frame-options" not in dict(security_headers(framed))
    assert cache_control_for("/api/health") == b"no-store" and cache_control_for("/") == b"no-cache"
    assert cache_control_for("/app.js") == b"public, max-age=300"


def test_client_address_takes_the_last_forwarded_entry_only_when_trusted():
    from cloud_assessor_appliance.security.limits import client_address

    class Req:
        def __init__(self, xff):
            self.headers = {"x-forwarded-for": xff} if xff is not None else {}
            self.client = type("C", (), {"host": "10.0.0.9"})()

    assert client_address(Req("203.0.113.1, 10.0.0.1"), False) == "10.0.0.9"
    assert client_address(Req("203.0.113.1, 10.0.0.1"), True) == "10.0.0.1", "the proxy appends; the last entry is its"
    assert client_address(Req("203.0.113.7"), True) == "203.0.113.7"
    assert client_address(Req(""), True) == "10.0.0.9" and client_address(Req(None), True) == "10.0.0.9"
    assert len(client_address(Req("x" * 200), True)) == 64


def test_token_bucket_refills_and_prunes():
    now = [0.0]
    limiter = TokenBucketLimiter(2, 10.0, clock=lambda: now[0])
    assert limiter.acquire("a") == (True, 0) and limiter.acquire("a") == (True, 0)
    allowed, retry = limiter.acquire("a")
    assert not allowed and retry >= 1
    assert limiter.acquire("b") == (True, 0)
    now[0] += 5.0
    assert limiter.acquire("a") == (True, 0)
    limiter._buckets.clear()
    for i in range(MAX_TRACKED_CLIENTS):
        limiter.acquire(f"c{i}")
    now[0] += 100.0
    assert limiter.acquire("new") == (True, 0) and len(limiter._buckets) < MAX_TRACKED_CLIENTS
    limiter = TokenBucketLimiter(1, 1000.0, clock=lambda: now[0])
    for i in range(MAX_TRACKED_CLIENTS):
        limiter.acquire(f"c{i}")
    assert limiter.acquire("new") == (True, 0) and len(limiter._buckets) == 1


def test_sdk_loggers_are_silenced(monkeypatch):
    import logging

    buf = io.StringIO()
    monkeypatch.setattr(sys, "stderr", buf)
    logs.configure(silent=True)
    for name in ("azure.identity", "azure.core.pipeline.policies.http_logging_policy", "msal", "urllib3"):
        logging.getLogger(name).warning("token for /subscriptions/00000000-0000-0000-0000-000000000001")
        logging.getLogger(name).error("boom")
    assert buf.getvalue() == ""


def test_logging_writer_is_guarded(monkeypatch):
    buf = io.StringIO()
    monkeypatch.setattr(sys, "stderr", buf)
    logs.configure(silent=False)
    logs.log_event("refresh_completed", resources=1, costEvidence=True)
    with pytest.raises(VisitorDataError):
        logs.log_event("startup", name="hcw-sample-aks")
    logs.log_exception("refresh_failed", RuntimeError("sub /subscriptions/00000000-0000-0000-0000-000000000001/x"))
    out = buf.getvalue()
    assert '"event":"refresh_completed"' in out and "00000000-0000" not in out
    assert '"exception":"RuntimeError"' in out and "scrubbed" not in out, "class name only by default"
    logs.log_exception(
        "refresh_failed", RuntimeError("sub /subscriptions/00000000-0000-0000-0000-000000000001/x"), message=True
    )
    out = buf.getvalue()
    assert "<redacted>" in out and "00000000-0000" not in out
    with pytest.raises(VisitorDataError):
        logs._write({"event": "startup", "exception": "not an identifier"})
    logs.configure(silent=True)
    logs.log_event("startup")
    assert out == buf.getvalue()
