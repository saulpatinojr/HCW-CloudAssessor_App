"""Logs carry counts, durations, flags and allowed words only; never ids, names, tokens or resource content."""

import io
import json
import sys

from cloud_assessor_core.redaction import ALLOWED_WORDS
from fastapi.testclient import TestClient

from cloud_assessor_appliance.security import logging as logs

from ..conftest import FakeResourceGraphClient, make_app, make_settings, run_refresh


def test_lifecycle_logs_are_content_free(monkeypatch):
    buf = io.StringIO()
    monkeypatch.setattr(sys, "stderr", buf)
    app = make_app(make_settings(log_silent=False, public_results=True, rate_limit_posts=5))
    with TestClient(app) as c:
        run_refresh(c)
        c.get("/api/assessments/current")
        c.post("/api/refresh")
        while app.state.refresher.running:
            pass
        app.state.refresher._resources = app.state.refresher._resources.__class__(
            FakeResourceGraphClient(throttle=99), app.state.allowlist, sleep=lambda s: None
        )
        run_refresh(c)
    lines = [json.loads(line) for line in buf.getvalue().splitlines()]
    events = [line["event"] for line in lines]
    assert events[0] == "startup" and events[-1] == "shutdown"
    for wanted in ("refresh_started", "refresh_completed", "results_read", "refresh_requested", "refresh_failed"):
        assert wanted in events, wanted
    text = buf.getvalue()
    assert "hcw-sample" not in text and "00000000-0000" not in text and "eastus2" not in text
    for line in lines:
        for key, value in line.items():
            if key == "ts" or (key == "scrubbed" and "<redacted>" in value or key == "scrubbed"):
                assert "00000000-0000" not in str(value) and "hcw-sample" not in str(value)
                continue
            assert value is None or isinstance(value, bool | int | float) or value in ALLOWED_WORDS, (key, value)
    logs.configure(silent=True)
