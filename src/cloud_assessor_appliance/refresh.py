"""The in-memory snapshot and the refresh orchestrator: single-flight, global cooldown, timer (REFACTOR_APP.md 7.8).

A refresh collects the inventory (thread), the cost evidence (hourly cache), evaluates, builds the bundle and swaps
the snapshot atomically. A failed collection keeps the previous snapshot current and logs a code, never content.
"""

from __future__ import annotations

import asyncio
import hashlib
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime

from cloud_assessor_core.assess import assess
from cloud_assessor_core.model import Assessment, AssessmentScope, Catalog
from cloud_assessor_core.report import make_bundle, zip_bytes

from cloud_assessor_appliance.collectors.resource_graph import CollectorError, ResourceGraphCollector
from cloud_assessor_appliance.collectors.scope import ScopeAllowlist, ScopeError
from cloud_assessor_appliance.security.logging import log_event, log_exception

EDITION = "appliance"


@dataclass
class Snapshot:
    assessment: Assessment | None = None
    files: dict[str, bytes] = field(default_factory=dict)
    as_of: datetime | None = None
    resources: int = 0
    last_error: str | None = None  # an error code, never a message

    @property
    def ready(self) -> bool:
        return self.assessment is not None

    @property
    def as_of_iso(self) -> str | None:
        return self.as_of.isoformat().replace("+00:00", "Z") if self.as_of else None


def hashed_scope(allowlist: ScopeAllowlist) -> AssessmentScope:
    subs = [hashlib.sha256(s.encode("utf-8")).hexdigest() for s in allowlist.subscriptions()]
    return AssessmentScope(count=len(allowlist.subscriptions()), subscriptions=subs)


class Refresher:
    def __init__(
        self,
        *,
        catalog: Catalog,
        scoring,
        allowlist: ScopeAllowlist,
        resource_collector: ResourceGraphCollector,
        cost_collector=None,
        cooldown_seconds: int = 600,
        clock: Callable[[], float] = time.monotonic,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._catalog = catalog
        self._scoring = scoring
        self._allowlist = allowlist
        self._resources = resource_collector
        self._cost = cost_collector
        self._cooldown = cooldown_seconds
        self._clock = clock
        self._now = now
        self._lock = asyncio.Lock()
        self._last_requested: float | None = None
        self.snapshot = Snapshot()
        self.runs = 0

    @property
    def running(self) -> bool:
        return self._lock.locked()

    def cooldown_remaining(self) -> int:
        if self._last_requested is None:
            return 0
        return max(0, int(self._cooldown - (self._clock() - self._last_requested) + 0.999))

    def request(self) -> str:
        """'running' (single-flight, nothing started), 'cooldown' (inside the global window) or 'queued'."""
        if self.running:
            return "running"
        if self.cooldown_remaining() > 0:
            return "cooldown"
        self._last_requested = self._clock()
        asyncio.get_running_loop().create_task(self.run())
        return "queued"

    async def run(self) -> bool:
        """One collection and evaluation. False when another run held the lock (nothing was started)."""
        if self._lock.locked():
            return False
        async with self._lock:
            started = time.monotonic()
            log_event("refresh_started", scopes=len(self._allowlist.scopes))
            try:
                collected = await asyncio.to_thread(self._resources.collect)
                evidence = await self._cost.collect() if self._cost is not None else None
                if self._cost is None:
                    log_event("cost_skipped")
                assessment = await asyncio.to_thread(
                    assess,
                    collected.resources,
                    self._catalog,
                    self._scoring,
                    source_format="arg-live",
                    ingestion_warnings=collected.warnings,
                    now=self._now(),
                    evidence=evidence,
                    edition=EDITION,
                    scope=hashed_scope(self._allowlist),
                )
                files = make_bundle(assessment, self._catalog)
                files["bundle.zip"] = zip_bytes(files)
            except (CollectorError, ScopeError) as exc:
                self.snapshot.last_error = "collector_error"
                log_exception("refresh_failed", exc, code="collector_error", kept=self.snapshot.ready)
                return True
            except Exception as exc:  # noqa: BLE001 - the timer must survive; the previous snapshot stays current
                self.snapshot.last_error = "internal_error"
                log_exception("refresh_failed", exc, code="internal_error", kept=self.snapshot.ready)
                return True
            self.snapshot = Snapshot(assessment, files, assessment.created_at, collected.rows, None)
            self.runs += 1
            log_event(
                "refresh_completed",
                resources=collected.rows,
                findings=len(assessment.findings),
                warnings=len(collected.warnings),
                costEvidence=evidence is not None,
                durationMs=int((time.monotonic() - started) * 1000),
            )
            return True

    async def timer(self, interval_seconds: float) -> None:
        """Collect at startup, then every interval. Cancelled at shutdown."""
        while True:
            await self.run()
            await asyncio.sleep(interval_seconds)
