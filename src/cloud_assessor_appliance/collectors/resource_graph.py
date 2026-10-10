"""Azure Resource Graph collector: one paged query per refresh, throttling-aware, normalised into `Resource` (T-025).

The query is built from the constructor's ScopeAllowlist only: `collect()` takes no scope argument, so no caller can
widen the scope. The SDK is touched only by `SdkResourceGraphClient`; the collector itself is SDK-free and is tested
with a fake client.
"""

from __future__ import annotations

import random
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol

from cloud_assessor_core.ingestion.normalize import ParsedRows, normalize
from cloud_assessor_core.model import Resource
from cloud_assessor_core.redaction import scrub

from cloud_assessor_appliance.collectors.scope import ScopeAllowlist, ScopeError

PROJECTION = "id,name,type,location,resourceGroup,subscriptionId,tags,properties,sku,identity,kind,zones"
KQL = "resources | where {filter} | project {projection} | order by id asc"

ATTEMPTS = 5
BASE_DELAY_SECONDS = 2.0
MAX_DELAY_SECONDS = 60.0


class CollectorError(RuntimeError):
    """A collection failed after its retries; the previous snapshot stays current. Messages are scrubbed."""


class ThrottledError(Exception):
    """The service answered 429; `retry_after` is the header value in seconds when it was present."""

    def __init__(self, retry_after: float | None = None) -> None:
        super().__init__("throttled")
        self.retry_after = retry_after


@dataclass(frozen=True)
class Page:
    rows: list[dict[str, Any]]
    skip_token: str | None = None
    total_records: int | None = None
    truncated: bool = False


@dataclass(frozen=True)
class Collected:
    resources: list[Resource]
    warnings: list[str] = field(default_factory=list)
    rows: int = 0


class ResourceGraphClient(Protocol):
    def query(self, *, subscriptions: list[str], query: str, top: int, skip_token: str | None) -> Page: ...


class ResourceGraphCollector:
    def __init__(
        self,
        client: ResourceGraphClient,
        allowlist: ScopeAllowlist,
        *,
        page_size: int = 1000,
        max_rows: int = 50_000,
        sleep: Callable[[float], None] = time.sleep,
        rng: Callable[[], float] = random.random,
    ) -> None:
        self._client = client
        self._allowlist = allowlist
        self._page_size = max(1, min(page_size, 1000))
        self._max_rows = max(1, max_rows)
        self._sleep = sleep
        self._rng = rng

    @property
    def query_text(self) -> str:
        return KQL.format(filter=self._allowlist.kql_filter(), projection=PROJECTION)

    def collect(self) -> Collected:
        """Pages through the query, enforces the allow-list on every returned id, normalises to Resource."""
        rows: list[dict[str, Any]] = []
        warnings: list[str] = []
        token: str | None = None
        total: int | None = None
        while True:
            page = self._query(token)
            rows.extend(r for r in page.rows if isinstance(r, dict))
            total = page.total_records if page.total_records is not None else total
            if page.truncated:
                warnings.append("the service truncated the result set; the inventory may be incomplete")
            if len(rows) >= self._max_rows:
                if len(rows) > self._max_rows or page.skip_token:
                    warnings.append(
                        f"collection capped at {self._max_rows} rows"
                        + (f" of {total}" if total is not None else "")
                        + "; the remainder was not assessed"
                    )
                rows = rows[: self._max_rows]
                break
            token = page.skip_token
            if not token:
                break
        for row in rows:
            try:
                self._allowlist.assert_contains(str(row.get("id") or ""))
            except ScopeError as exc:
                raise CollectorError(str(exc)) from None
        if not rows:
            return Collected([], ["the scope returned no resources"], 0)
        resources, norm_warnings = normalize(ParsedRows(rows=rows, warnings=warnings), "arg-live")
        return Collected(resources, norm_warnings, len(rows))

    def _query(self, token: str | None) -> Page:
        subscriptions = self._allowlist.subscriptions()
        for attempt in range(ATTEMPTS):
            try:
                return self._client.query(
                    subscriptions=subscriptions, query=self.query_text, top=self._page_size, skip_token=token
                )
            except ThrottledError as exc:
                if attempt == ATTEMPTS - 1:
                    raise CollectorError("throttled by the service after five attempts") from None
                self._sleep(self._delay(attempt, exc.retry_after))
            except CollectorError:
                raise
            except Exception as exc:  # noqa: BLE001 - adapter leaks are wrapped and scrubbed
                raise CollectorError(scrub(f"{type(exc).__name__}: {exc}")) from None
        raise CollectorError("unreachable")  # pragma: no cover

    def _delay(self, attempt: int, retry_after: float | None) -> float:
        if retry_after is not None and retry_after > 0:
            return min(MAX_DELAY_SECONDS, float(retry_after))
        base = BASE_DELAY_SECONDS * (2**attempt)
        jitter = self._rng() * BASE_DELAY_SECONDS
        return min(MAX_DELAY_SECONDS, base + jitter)


def _retry_after(response: Any) -> float | None:
    headers = getattr(response, "headers", None)
    value = headers.get("Retry-After") if headers else None
    try:
        return float(value) if value is not None else None
    except TypeError, ValueError:
        return None


class SdkResourceGraphClient:
    """The only Resource Graph SDK touch point. Built lazily so the module imports without the `azure` extra."""

    def __init__(self, credential: Any) -> None:
        from azure.mgmt.resourcegraph import ResourceGraphClient as _Client

        self._client = _Client(credential)

    def query(self, *, subscriptions: list[str], query: str, top: int, skip_token: str | None) -> Page:
        from azure.core.exceptions import HttpResponseError
        from azure.mgmt.resourcegraph.models import QueryRequest, QueryRequestOptions

        request = QueryRequest(
            subscriptions=list(subscriptions),
            query=query,
            options=QueryRequestOptions(top=top, skip_token=skip_token, result_format="objectArray"),
        )
        try:
            response = self._client.resources(request)
        except HttpResponseError as exc:
            if exc.status_code == 429:
                raise ThrottledError(_retry_after(exc.response)) from None
            raise CollectorError(f"resource graph query failed: HTTP {exc.status_code}") from None
        data = response.data if isinstance(response.data, list) else []
        truncated = str(getattr(response, "result_truncated", "false")).lower() == "true"
        return Page(
            rows=data, skip_token=response.skip_token, total_records=response.total_records, truncated=truncated
        )
