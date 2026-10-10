"""The application factory for the appliance edition: the section 8 routes, the standard headers, no upload path.

Results are public for the scope by owner decision, behind the CA_PUBLIC_RESULTS release gate (403 results_not_public
until the owner flips it; REVIEW.md R-006 and R-009). There are no owner tokens and no `{id}` paths: one scope, one
current assessment.
"""

from __future__ import annotations

import asyncio
import json
import os
from collections.abc import Mapping
from contextlib import asynccontextmanager
from datetime import UTC, datetime

from cloud_assessor_core.catalog import load_catalog, load_scoring
from fastapi import FastAPI, Request, Response
from fastapi.exceptions import HTTPException, RequestValidationError
from fastapi.responses import FileResponse, JSONResponse

from cloud_assessor_appliance import ADDON_ID, __version__
from cloud_assessor_appliance.collectors.scope import ScopeAllowlist
from cloud_assessor_appliance.config import TURNSTILE_ACTION, Settings
from cloud_assessor_appliance.edition import AZURE_CONNECTIVITY, CAPABILITIES, EDITION
from cloud_assessor_appliance.errors import DEFAULT_CODES, DEFAULT_MESSAGES, ApiError
from cloud_assessor_appliance.identity import refuse_forbidden_env
from cloud_assessor_appliance.refresh import Refresher
from cloud_assessor_appliance.security import logging as logs
from cloud_assessor_appliance.security.cors import ExactOriginCorsMiddleware
from cloud_assessor_appliance.security.headers import SecurityHeadersMiddleware
from cloud_assessor_appliance.security.limits import client_address
from cloud_assessor_appliance.security.ratelimit import TokenBucketLimiter
from cloud_assessor_appliance.security.turnstile import verify

MEDIA_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".ico": "image/x-icon",
    ".txt": "text/plain; charset=utf-8",
}
READONLY_MESSAGE = "This edition reads its own scope; nothing is uploaded."


def _envelope(status: int, code: str, message: str, details=None, headers=None) -> JSONResponse:
    error = {"code": code, "message": message}
    if details is not None:
        error["details"] = details
    return JSONResponse({"error": error}, status_code=status, headers=headers or {})


def _now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _live_collectors(settings: Settings, allowlist: ScopeAllowlist, env: Mapping[str, str]):
    """Built only when nothing was injected: needs the `azure` extra and a managed identity or `az login` session."""
    from cloud_assessor_appliance.collectors.cost_management import CostManagementCollector, SdkCostClient
    from cloud_assessor_appliance.collectors.resource_graph import ResourceGraphCollector, SdkResourceGraphClient
    from cloud_assessor_appliance.edition import assert_appliance_ready
    from cloud_assessor_appliance.identity import build_credential

    assert_appliance_ready(env)
    credential = build_credential(env)
    resources = ResourceGraphCollector(
        SdkResourceGraphClient(credential), allowlist, page_size=settings.page_size, max_rows=settings.max_rows
    )
    cost = CostManagementCollector(SdkCostClient(credential), allowlist) if settings.cost_enabled else None
    return resources, cost


def create_app(
    settings: Settings | None = None,
    *,
    resource_collector=None,
    cost_collector=None,
    verifier=None,
    timer: bool = True,
    env: Mapping[str, str] | None = None,
) -> FastAPI:
    settings = settings or Settings.from_env()
    env = os.environ if env is None else env
    refuse_forbidden_env(env)
    logs.configure(silent=settings.log_silent)
    catalog_doc = load_catalog()
    scoring = load_scoring()
    allowlist = ScopeAllowlist.parse(settings.ca_scopes)  # equivalent to ScopeAllowlist.from_env(os.environ)
    if resource_collector is None:
        resource_collector, live_cost = _live_collectors(settings, allowlist, env)
        cost_collector = cost_collector or live_cost
    elif not settings.cost_enabled:
        cost_collector = None
    refresher = Refresher(
        catalog=catalog_doc,
        scoring=scoring,
        allowlist=allowlist,
        resource_collector=resource_collector,
        cost_collector=cost_collector,
        cooldown_seconds=settings.refresh_cooldown_minutes * 60,
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        logs.log_event(
            "startup",
            catalogCriteria=len(catalog_doc.criteria),
            scopes=len(allowlist.scopes),
            turnstileRequired=settings.turnstile_required,
            publicResults=settings.public_results,
            costEnabled=cost_collector is not None,
        )
        task = asyncio.create_task(refresher.timer(settings.refresh_minutes * 60)) if timer else None
        try:
            yield
        finally:
            if task:
                task.cancel()
            logs.log_event("shutdown", runs=refresher.runs)

    app = FastAPI(
        title="Cloud Assessment (appliance edition)",
        version=__version__,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.catalog = catalog_doc
    app.state.scoring = scoring
    app.state.allowlist = allowlist
    app.state.refresher = refresher
    app.state.limiter = TokenBucketLimiter(settings.rate_limit_posts, settings.rate_limit_window_minutes * 60)
    app.state.verifier = verifier

    @app.exception_handler(ApiError)
    async def _api_error(request: Request, exc: ApiError):
        return _envelope(exc.status, exc.code, exc.message, exc.details, exc.headers)

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError):
        return _envelope(400, "invalid_request", DEFAULT_MESSAGES[400])

    @app.exception_handler(HTTPException)
    async def _http(request: Request, exc: HTTPException):
        status = exc.status_code
        return _envelope(
            status,
            DEFAULT_CODES.get(status, "error"),
            DEFAULT_MESSAGES.get(status, "The request failed."),
            headers=exc.headers,
        )

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception):
        logs.log_exception("unhandled_error", exc)
        return _envelope(500, "internal_error", DEFAULT_MESSAGES[500])

    # ----- health and catalog -----

    @app.get("/api/health")
    async def health() -> dict:
        return health_body(app)

    @app.get("/api/catalog")
    async def catalog() -> dict:
        cat = app.state.catalog
        return {
            "version": cat.version,
            "retrievedOn": cat.retrievedOn,
            "count": len(cat.criteria),
            "attribution": list(cat.attribution),
            "criteria": [
                {
                    "id": c.id,
                    "framework": c.framework,
                    "pillar": c.pillar,
                    "severity": c.severity,
                    "resourceTypes": list(c.resourceTypes),
                    "title": c.title,
                    "text": c.text,
                    "remediation": c.remediation,
                    "learnUrl": c.learnUrl,
                    "verify": c.verify,
                    "retrievedOn": c.retrievedOn,
                    "checks": [{"kind": k.kind} for k in c.checks],
                    "anyPass": c.anyPass,
                }
                for c in cat.criteria
            ],
        }

    # ----- the current assessment (gated) -----

    def _current():
        """503 before the first successful run whatever the gate; 403 while the gate is closed; else the snapshot."""
        snapshot = refresher.snapshot
        if not snapshot.ready:
            raise ApiError(
                503,
                "no_snapshot",
                "No assessment has completed yet; the first collection is running.",
                {"lastError": snapshot.last_error} if snapshot.last_error else None,
                headers={"Retry-After": "30"},
            )
        if not settings.public_results:
            raise ApiError(403, "results_not_public", "Results are not published for this deployment.")
        return snapshot

    @app.get("/api/assessments/current")
    async def current() -> Response:
        snapshot = _current()
        logs.log_event("results_read")
        body = {
            "assessment": snapshot.assessment.model_dump(mode="json", by_alias=True),
            "files": sorted(snapshot.files),
            "asOf": snapshot.as_of_iso,
            "scope": {"count": len(allowlist.subscriptions())},
        }
        return Response(json.dumps(body), media_type="application/json")

    @app.get("/api/assessments/current/report.md")
    async def current_report_md() -> Response:
        snapshot = _current()
        return Response(
            snapshot.files["report.md"],
            media_type="text/markdown; charset=utf-8",
            headers={"Content-Disposition": 'attachment; filename="assessment-current.md"'},
        )

    @app.get("/api/assessments/current/report.json")
    async def current_report_json() -> Response:
        snapshot = _current()
        return Response(snapshot.files["report.json"], media_type="application/json")

    @app.get("/api/assessments/current/bundle.zip")
    async def current_bundle() -> Response:
        snapshot = _current()
        return Response(
            snapshot.files["bundle.zip"],
            media_type="application/zip",
            headers={"Content-Disposition": 'attachment; filename="assessment-current.zip"'},
        )

    # ----- refresh: single-flight, global cooldown, per-client bucket, optional human verification -----

    @app.post("/api/refresh", status_code=202)
    async def refresh(request: Request) -> Response:
        if refresher.running:
            logs.log_event("refresh_running")
            return JSONResponse({"queued": False, "running": True, "lastRun": refresher.snapshot.as_of_iso}, 202)
        remaining = refresher.cooldown_remaining()
        if remaining > 0:
            logs.log_event("refresh_cooldown", retryAfter=remaining)
            raise ApiError(
                429,
                "rate_limited",
                "A refresh ran recently; try again later.",
                {"retryAfter": remaining},
                headers={"Retry-After": str(remaining)},
            )
        allowed, retry_after = app.state.limiter.acquire(client_address(request, settings.trust_proxy))
        if not allowed:
            logs.log_event("rate_limited", retryAfter=retry_after)
            raise ApiError(
                429,
                "rate_limited",
                "Too many refresh requests from this client; try again later.",
                headers={"Retry-After": str(retry_after)},
            )
        if settings.turnstile_required:
            verdict = verify(
                settings.turnstile_secret or "",
                request.headers.get("x-turnstile-token"),
                client_address(request, settings.trust_proxy),
                opener=app.state.verifier,
            )
            if not verdict.ok:
                logs.log_event("turnstile_rejected", codes=len(verdict.codes))
                raise ApiError(403, "turnstile_failed", "Human verification did not succeed.", {"codes": verdict.codes})
            logs.log_event("turnstile_verified")
        outcome = refresher.request()
        logs.log_event("refresh_requested")
        if outcome == "running":
            return JSONResponse({"queued": False, "running": True, "lastRun": refresher.snapshot.as_of_iso}, 202)
        return JSONResponse({"queued": True, "lastRun": refresher.snapshot.as_of_iso}, 202)

    # ----- no upload surface in this edition -----

    @app.api_route("/api/assessments", methods=["POST", "PUT", "PATCH", "DELETE"], include_in_schema=False)
    async def _readonly() -> Response:
        raise ApiError(405, "edition_readonly", READONLY_MESSAGE)

    @app.api_route(
        "/api/{rest:path}",
        methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"],
        include_in_schema=False,
    )
    async def _api_fallthrough(request: Request, rest: str):
        for route in iter_routes(app):
            if route.path.startswith("/api/{rest") or route.path == "/{path:path}":
                continue
            if route.path_regex.match(request.url.path):
                raise ApiError(405, "method_not_allowed", DEFAULT_MESSAGES[405])
        raise ApiError(404, "not_found", "Not found.")

    # ----- the pane -----

    @app.get("/{path:path}", include_in_schema=False)
    async def static_file(path: str) -> Response:
        if path.startswith("api/") or path == "api":
            raise ApiError(404, "not_found", "Not found.")
        file = safe_file(settings.static_dir, path or "index.html")
        if file is None:
            raise ApiError(404, "not_found", "Not found.")
        return FileResponse(file, media_type=MEDIA_TYPES.get(file.suffix, "application/octet-stream"))

    app.add_middleware(ExactOriginCorsMiddleware, allowed_origins=settings.allowed_origins)
    app.add_middleware(SecurityHeadersMiddleware, settings=settings)
    return app


def health_body(app: FastAPI) -> dict:
    settings: Settings = app.state.settings
    refresher: Refresher = app.state.refresher
    return {
        "ok": True,
        "id": ADDON_ID,
        "version": __version__,
        "edition": EDITION,
        "capabilities": list(CAPABILITIES),
        "asOf": _now_iso(),
        "siteOrigins": list(settings.site_origins),
        "turnstile": {
            "required": settings.turnstile_required,
            "siteKey": settings.turnstile_site_key,
            "action": TURNSTILE_ACTION,
        },
        "azureConnectivity": AZURE_CONNECTIVITY,
        "scope": {"count": len(app.state.allowlist.subscriptions())},
        "catalog": {"version": app.state.catalog.version, "count": len(app.state.catalog.criteria)},
        "lastRun": refresher.snapshot.as_of_iso,
        "publicResults": settings.public_results,
    }


def safe_file(base, relative: str):
    root = base.resolve()
    try:
        candidate = (root / relative).resolve()
    except OSError:
        return None
    if candidate == root or root not in candidate.parents or not candidate.is_file():
        return None
    return candidate


def iter_routes(app_or_router):
    """Every concrete route, descending through included routers."""
    for route in getattr(app_or_router, "routes", []):
        if getattr(route, "path_regex", None) is not None and getattr(route, "methods", None):
            yield route
        else:
            yield from iter_routes(getattr(route, "original_router", route))


def api_routes(app: FastAPI) -> dict[str, set[str]]:
    """{path: methods} for the documented /api surface (the catch-all and the pane route excluded)."""
    table: dict[str, set[str]] = {}
    for route in iter_routes(app):
        if not route.path.startswith("/api/") or route.path.startswith("/api/{rest"):
            continue
        table.setdefault(route.path, set()).update(m for m in route.methods if m not in ("HEAD", "OPTIONS"))
    return table
