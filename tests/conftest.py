from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from cloud_assessor_core.model import BudgetEvidence, CostEvidence
from fastapi.testclient import TestClient

from cloud_assessor_appliance.api import create_app
from cloud_assessor_appliance.collectors.resource_graph import Collected, Page, ResourceGraphCollector
from cloud_assessor_appliance.collectors.scope import ScopeAllowlist
from cloud_assessor_appliance.config import Settings

ROOT = Path(__file__).resolve().parents[1]
SAMPLE_JSON = ROOT / "samples" / "sample-resource-graph.json"
FICTIONAL_SUBSCRIPTION = "00000000-0000-0000-0000-000000000001"
SCOPE = f"/subscriptions/{FICTIONAL_SUBSCRIPTION}"
NO_AZURE_ENV: dict[str, str] = {}


def sample_rows() -> list[dict]:
    return json.loads(SAMPLE_JSON.read_text(encoding="utf-8"))["data"]


class FakeResourceGraphClient:
    """Serves the sample rows in pages; records every query; can throttle a configurable number of times."""

    def __init__(self, rows: list[dict] | None = None, *, page_rows: int = 1000, throttle: int = 0) -> None:
        self.rows = sample_rows() if rows is None else rows
        self.page_rows = page_rows
        self.throttle = throttle
        self.calls: list[dict] = []

    def query(self, *, subscriptions, query, top, skip_token) -> Page:
        from cloud_assessor_appliance.collectors.resource_graph import ThrottledError

        self.calls.append({"subscriptions": list(subscriptions), "query": query, "top": top, "skip_token": skip_token})
        if self.throttle > 0:
            self.throttle -= 1
            raise ThrottledError(retry_after=1)
        start = int(skip_token or 0)
        size = min(top, self.page_rows)
        chunk = self.rows[start : start + size]
        next_token = str(start + size) if start + size < len(self.rows) else None
        return Page(rows=chunk, skip_token=next_token, total_records=len(self.rows))


class FakeCostCollector:
    def __init__(self, evidence: CostEvidence | None = None) -> None:
        self.evidence = evidence
        self.calls = 0

    async def collect(self) -> CostEvidence | None:
        self.calls += 1
        return self.evidence


class HangingCollector:
    """A resource collector that never returns; proves /api/health does not wait on a collection."""

    def collect(self) -> Collected:
        import threading

        threading.Event().wait(5)
        return Collected([], [], 0)


def make_evidence(**overrides) -> CostEvidence:
    base = {
        "scope": SCOPE,
        "period_start": date(2026, 10, 1),
        "period_end": date(2026, 10, 10),
        "currency": "USD",
        "total": 1000.0,
        "by_resource_group": {"rg-a": 1000.0},
        "by_cost_center_tag": {"cc-1": 900.0, "": 100.0},
        "untagged_share": 10.0,
        "budgets": [BudgetEvidence(name="hcw-sample-budget", amount=2000.0, time_grain="Monthly", notifications=2)],
        "anomaly_alerts": ["hcw-sample-anomaly"],
        "as_of": datetime(2026, 10, 10, 12, tzinfo=UTC),
    }
    base.update(overrides)
    return CostEvidence(**base)


def make_settings(**overrides) -> Settings:
    base = {
        "ca_scopes": SCOPE,
        "log_silent": True,
        "site_origins": ("https://hybridcloudworks.com",),
        "refresh_cooldown_minutes": 0,
    }
    base.update(overrides)
    return Settings(**base)


def make_collector(settings: Settings | None = None, client: FakeResourceGraphClient | None = None, **kw):
    settings = settings or make_settings()
    allowlist = ScopeAllowlist.parse(settings.ca_scopes)
    return ResourceGraphCollector(client or FakeResourceGraphClient(), allowlist, sleep=lambda s: None, **kw)


def make_app(
    settings: Settings | None = None, *, cost=None, client=None, verifier=None, token_verifier=None, timer=False
):
    settings = settings or make_settings()
    return create_app(
        settings,
        resource_collector=make_collector(settings, client),
        cost_collector=cost if cost is not None else FakeCostCollector(make_evidence()),
        verifier=verifier,
        token_verifier=token_verifier,
        timer=timer,
        env=NO_AZURE_ENV,
    )


def run_refresh(client: TestClient) -> None:
    """Runs one collection in the application's event loop and waits for it."""
    assert client.portal.call(client.app.state.refresher.run)


@pytest.fixture
def settings() -> Settings:
    return make_settings()


@pytest.fixture
def client(settings):
    app = make_app(settings)
    with TestClient(app) as c:
        yield c


@pytest.fixture
def public_client():
    app = make_app(make_settings(public_results=True))
    with TestClient(app) as c:
        run_refresh(c)
        yield c


@pytest.fixture
def anyio_backend():
    return "asyncio"
