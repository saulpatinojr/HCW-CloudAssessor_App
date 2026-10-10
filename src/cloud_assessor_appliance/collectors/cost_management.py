"""Cost Management collector: asynchronous, hourly-cached cost evidence for the scope (T-026).

Cost Management lags by up to a day and throttles aggressively, so the evidence is collected beside the resource
inventory, cached for `cache_minutes`, and absent (`None`) rather than wrong on throttling or a missing role; the cost
criteria then stay `unknown` exactly as in the lab edition. The SDK is touched only by `SdkCostClient`.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from datetime import UTC, date, datetime
from typing import Any, Protocol

from cloud_assessor_core.model import BudgetEvidence, CostEvidence
from cloud_assessor_core.redaction import scrub

from cloud_assessor_appliance.collectors.resource_graph import (
    CONNECTION_TIMEOUT_SECONDS,
    READ_TIMEOUT_SECONDS,
    RETRY_TOTAL,
    CollectorError,
    ThrottledError,
    http_status,
)
from cloud_assessor_appliance.collectors.scope import ScopeAllowlist
from cloud_assessor_appliance.security.logging import log_event

COST_CENTER_TAG = "costCenter"


class CostAccessError(Exception):
    """The identity lacks Cost Management Reader on the scope (403); evidence is reported absent, not failed."""


class CostClient(Protocol):
    def actual_cost(self, scope: str, *, group_by: tuple[str, str]) -> tuple[list[str], list[list[Any]]]:
        """Month-to-date ActualCost grouped by ("Dimension", "ResourceGroup") or ("TagKey", "costCenter")."""
        ...

    def budgets(self, scope: str) -> list[BudgetEvidence]: ...

    def anomaly_alerts(self, scope: str) -> list[str]: ...


def _column(columns: list[str], *names: str) -> int | None:
    lowered = [c.lower() for c in columns]
    for name in names:
        if name.lower() in lowered:
            return lowered.index(name.lower())
    return None


def _number(value: Any) -> float:
    try:
        return float(value)
    except TypeError, ValueError:
        return 0.0


class CostManagementCollector:
    def __init__(
        self,
        client: CostClient,
        allowlist: ScopeAllowlist,
        *,
        cache_minutes: int = 60,
        clock: Callable[[], float] = time.monotonic,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._client = client
        self._allowlist = allowlist
        self._cache_seconds = max(0, cache_minutes) * 60
        self._clock = clock
        self._now = now
        self._cached: CostEvidence | None = None
        self._cached_at: float | None = None

    @property
    def cached(self) -> CostEvidence | None:
        return self._cached

    def _fresh(self) -> bool:
        return (
            self._cached is not None
            and self._cached_at is not None
            and (self._clock() - self._cached_at) < self._cache_seconds
        )

    async def collect(self) -> CostEvidence | None:
        """The cached evidence within the window; otherwise a new collection; None when it cannot be read."""
        if self._fresh():
            return self._cached
        try:
            evidence = await asyncio.to_thread(self.collect_sync)
        except ThrottledError:
            log_event("cost_unavailable", code="throttled")
            return self._cached
        except CostAccessError:
            log_event("cost_unavailable", code="forbidden")
            return self._cached
        except CollectorError:
            log_event("cost_unavailable", code="collector_error")
            return self._cached
        self._cached, self._cached_at = evidence, self._clock()
        return evidence

    def collect_sync(self) -> CostEvidence:
        now = self._now()
        by_rg: dict[str, float] = {}
        by_tag: dict[str, float] = {}
        currency = ""
        total = 0.0
        untagged = 0.0
        budgets: list[BudgetEvidence] = []
        alerts: list[str] = []
        try:
            for scope in self._allowlist.scopes:
                columns, rows = self._client.actual_cost(scope.id, group_by=("Dimension", "ResourceGroup"))
                cost_i, rg_i, cur_i = (
                    _column(columns, "Cost", "PreTaxCost"),
                    _column(columns, "ResourceGroup", "ResourceGroupName"),
                    _column(columns, "Currency"),
                )
                for row in rows:
                    amount = _number(row[cost_i]) if cost_i is not None and cost_i < len(row) else 0.0
                    group = str(row[rg_i]).lower() if rg_i is not None and rg_i < len(row) else ""
                    by_rg[group] = by_rg.get(group, 0.0) + amount
                    total += amount
                    if not currency and cur_i is not None and cur_i < len(row) and row[cur_i]:
                        currency = str(row[cur_i])
                columns, rows = self._client.actual_cost(scope.id, group_by=("TagKey", COST_CENTER_TAG))
                cost_i, val_i = _column(columns, "Cost", "PreTaxCost"), _column(columns, "TagValue")
                for row in rows:
                    amount = _number(row[cost_i]) if cost_i is not None and cost_i < len(row) else 0.0
                    value = str(row[val_i] or "") if val_i is not None and val_i < len(row) else ""
                    by_tag[value] = by_tag.get(value, 0.0) + amount
                    if not value:
                        untagged += amount
                budgets.extend(self._client.budgets(scope.id))
                alerts.extend(self._client.anomaly_alerts(scope.id))
        except ThrottledError, CostAccessError, CollectorError:
            raise
        except Exception as exc:  # noqa: BLE001 - adapter leaks are wrapped and scrubbed
            raise CollectorError(scrub(f"{type(exc).__name__}: {exc}")) from None
        share = round(100.0 * untagged / total, 2) if total > 0 else 0.0
        return CostEvidence(
            scope=",".join(s.id for s in self._allowlist.scopes),
            period_start=date(now.year, now.month, 1),
            period_end=now.date(),
            currency=currency or "unknown",
            total=round(total, 2),
            by_resource_group={k: round(v, 2) for k, v in by_rg.items()},
            by_cost_center_tag={k: round(v, 2) for k, v in by_tag.items()},
            untagged_share=min(100.0, max(0.0, share)),
            budgets=budgets,
            anomaly_alerts=sorted(dict.fromkeys(alerts)),
            as_of=now,
        )


def _retry_after(response: Any) -> float | None:
    headers = getattr(response, "headers", None)
    value = headers.get("Retry-After") if headers else None
    try:
        return float(value) if value is not None else None
    except TypeError, ValueError:
        return None


class SdkCostClient:
    """The only Cost Management SDK touch point (`azure-mgmt-costmanagement`, which also carries budgets and the
    scheduled actions that anomaly alerts are). [VERIFY] field names against a live scope at R-002 validation."""

    def __init__(self, credential: Any) -> None:
        from azure.mgmt.costmanagement import CostManagementClient as _Client

        self._client = _Client(
            credential,
            connection_timeout=CONNECTION_TIMEOUT_SECONDS,
            read_timeout=READ_TIMEOUT_SECONDS,
            retry_total=RETRY_TOTAL,
        )

    def _guard(self, call: Callable[[], Any]) -> Any:
        from azure.core.exceptions import ClientAuthenticationError, HttpResponseError

        try:
            return call()
        except ClientAuthenticationError:
            raise CostAccessError() from None
        except HttpResponseError as exc:
            if exc.status_code == 429:
                raise ThrottledError(_retry_after(exc.response)) from None
            if exc.status_code in (401, 403):
                raise CostAccessError() from None
            raise CollectorError(f"cost management call failed: HTTP {http_status(exc)}") from None

    def actual_cost(self, scope: str, *, group_by: tuple[str, str]) -> tuple[list[str], list[list[Any]]]:
        from azure.mgmt.costmanagement import models as cm

        definition = cm.QueryDefinition(
            type="ActualCost",
            timeframe="MonthToDate",
            dataset=cm.QueryDataset(
                granularity="None",
                aggregation={"totalCost": cm.QueryAggregation(name="Cost", function="Sum")},
                grouping=[cm.QueryGrouping(type=group_by[0], name=group_by[1])],
            ),
        )
        result = self._guard(lambda: self._client.query.usage(scope, definition))
        properties = getattr(result, "properties", None)
        columns = [str(c.name) for c in (getattr(properties, "columns", None) or [])]
        rows = [list(r) for r in (getattr(properties, "rows", None) or [])]
        return columns, rows

    def budgets(self, scope: str) -> list[BudgetEvidence]:
        items = self._guard(lambda: list(self._client.budgets.list(scope)))
        out = []
        for item in items:
            props = getattr(item, "properties", None)
            if props is None:
                continue
            out.append(
                BudgetEvidence(
                    name=str(getattr(item, "name", "") or ""),
                    amount=_number(getattr(props, "amount", 0)),
                    time_grain=str(getattr(props, "time_grain", "") or ""),
                    notifications=len(getattr(props, "notifications", None) or {}),
                )
            )
        return out

    def anomaly_alerts(self, scope: str) -> list[str]:
        """Cost anomaly alerts are scheduled actions of kind InsightAlert on the scope. [VERIFY]"""
        items = self._guard(lambda: list(self._client.scheduled_actions.list_by_scope(scope)))
        return [
            str(getattr(i, "id", "") or getattr(i, "name", ""))
            for i in items
            if getattr(i, "kind", "") == "InsightAlert"
        ]
