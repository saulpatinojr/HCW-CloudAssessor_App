"""Microsoft Entra ID access-token validation for the appliance (TODO.md T-032, REVIEW.md R-009 option b).

Sign-in is an additional lock: the CA_PUBLIC_RESULTS gate still answers 403 results_not_public with a valid token.

A request must carry `Authorization: Bearer <access token>` on every route except GET /api/health. The token is
checked with the tenant's PUBLIC signing keys only (a JWKS document); no secret, certificate or token is held here.
What is checked, in order, and each failure is the same `401 unauthorized` with `WWW-Authenticate: Bearer`:

  1. header shape, token size, `alg` is exactly RS256 (never none, HS*, ES*, PS*), a `kid` is present;
  2. the signature, against the key whose `kid` the tenant's JWKS publishes (unknown kid: refused);
  3. `exp` and `nbf` (both required) with a declared clock skew (CA_AUTH_CLOCK_SKEW_SECONDS, default 60, at most 300);
  4. `iss` equals the v2.0 or the v1.0 issuer form of the configured tenant; `aud` is one of the configured audiences;
  5. `tid` equals the configured tenant;
  6. the token carries a required app role (`roles`) or delegated scope (`scp`), default `Assessment.Read`.

Nothing from the token is ever logged or returned: the rejection log line carries the status and a numeric reason code
(Reason below). Spec: https://learn.microsoft.com/en-us/entra/identity-platform/access-tokens and
https://learn.microsoft.com/en-us/entra/identity-platform/claims-validation
"""

from __future__ import annotations

import asyncio
import enum
import ipaddress
import json
import re
import threading
import time
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from urllib.parse import urlsplit

from fastapi.responses import JSONResponse

from cloud_assessor_appliance.config import Settings
from cloud_assessor_appliance.security import logging as logs

HEALTH_PATH = "/api/health"
ALGORITHM = "RS256"
MAX_TOKEN_BYTES = 16 * 1024
MAX_JWKS_BYTES = 256 * 1024
JWKS_FETCH_TIMEOUT_SECONDS = 5.0
JWKS_CACHE_SECONDS = 300.0
JWKS_REFRESH_COOLDOWN_SECONDS = 60.0  # an unknown kid may force a re-fetch at most this often
V1_ISSUER = "https://sts.windows.net/{tenant}/"
V2_ISSUER = "https://{host}/{tenant}/v2.0"
JWKS_URL = "https://{host}/{tenant}/discovery/v2.0/keys"
GUID = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
HOST = re.compile(r"^(?=.{1,253}$)([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$")
TOKEN = re.compile(r"^[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]*$")  # an empty signature is refused by alg

Fetcher = Callable[[str], bytes]


class AuthConfigError(ValueError):
    """Sign-in is enabled but its settings are missing or malformed; the appliance refuses to start."""


class Reason(enum.IntEnum):
    """Numeric reason codes written to the log (a log value must be a count, flag or allowed word)."""

    MISSING = 1
    MALFORMED = 2
    ALGORITHM = 3
    KEY_ID = 4
    SIGNATURE = 5
    EXPIRED = 6
    NOT_YET_VALID = 7
    AUDIENCE = 8
    ISSUER = 9
    TENANT = 10
    PERMISSION = 11
    CLAIMS = 12
    KEYS_UNAVAILABLE = 13


class TokenError(Exception):
    def __init__(self, reason: Reason) -> None:
        super().__init__(reason.name)
        self.reason = reason


@dataclass(frozen=True)
class AuthConfig:
    tenant_id: str
    audiences: tuple[str, ...]
    authority_host: str
    jwks_url: str
    clock_skew_seconds: int
    required_roles: tuple[str, ...]
    required_scopes: tuple[str, ...]

    @property
    def issuers(self) -> tuple[str, ...]:
        return (
            V2_ISSUER.format(host=self.authority_host, tenant=self.tenant_id),
            V1_ISSUER.format(tenant=self.tenant_id),
        )

    @classmethod
    def from_settings(cls, settings: Settings) -> AuthConfig:
        tenant = (settings.auth_tenant_id or "").strip()
        if not GUID.match(tenant):
            raise AuthConfigError("CA_AUTH_TENANT_ID must be set to the tenant (directory) id, a GUID")
        audiences = tuple(a for a in settings.auth_audiences if a)
        if not audiences or any(re.search(r"\s", a) for a in audiences):
            raise AuthConfigError("CA_AUTH_AUDIENCE must list at least one audience (application id or api:// URI)")
        host = (settings.auth_authority_host or "").strip().lower()
        if not HOST.match(host) or _is_ip(host):
            raise AuthConfigError("CA_AUTH_AUTHORITY_HOST must be a host name only (no scheme, path or port)")
        jwks_url = (settings.auth_jwks_url or "").strip() or JWKS_URL.format(host=host, tenant=tenant)
        parts = urlsplit(jwks_url)
        if parts.scheme != "https" or not parts.hostname or parts.username or parts.password:
            raise AuthConfigError("CA_AUTH_JWKS_URL must be an https URL")
        if not 0 <= settings.auth_clock_skew_seconds <= 300:
            raise AuthConfigError("CA_AUTH_CLOCK_SKEW_SECONDS must be between 0 and 300")
        if not (settings.auth_required_roles or settings.auth_required_scopes):
            raise AuthConfigError("a required app role or scope must be configured")
        return cls(
            tenant_id=tenant.lower(),
            audiences=audiences,
            authority_host=host,
            jwks_url=jwks_url,
            clock_skew_seconds=settings.auth_clock_skew_seconds,
            required_roles=settings.auth_required_roles,
            required_scopes=settings.auth_required_scopes,
        )


def _is_ip(host: str) -> bool:
    try:
        ipaddress.ip_address(host)
    except ValueError:
        return False
    return True


def https_fetch(url: str) -> bytes:
    """The default JWKS fetcher: https only, short timeout, bounded size. Tests inject their own."""
    if urlsplit(url).scheme != "https":
        raise OSError("https only")
    request = urllib.request.Request(url, headers={"Accept": "application/json"})  # noqa: S310 - https checked above
    with urllib.request.urlopen(request, timeout=JWKS_FETCH_TIMEOUT_SECONDS) as response:  # noqa: S310
        body = response.read(MAX_JWKS_BYTES + 1)
    if len(body) > MAX_JWKS_BYTES:
        raise OSError("JWKS too large")
    return body


class JwksCache:
    """The tenant's signing keys by `kid`: cached for 5 minutes, re-fetched at most once a minute for an unknown kid
    (so a stream of forged kids cannot turn into a stream of outbound requests), last good set kept if a fetch fails."""

    def __init__(
        self,
        url: str,
        fetch: Fetcher = https_fetch,
        *,
        ttl: float = JWKS_CACHE_SECONDS,
        cooldown: float = JWKS_REFRESH_COOLDOWN_SECONDS,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._url = url
        self._fetch = fetch
        self._ttl = ttl
        self._cooldown = cooldown
        self._clock = clock
        self._lock = threading.Lock()
        self._keys: dict[str, object] = {}
        self._loaded_at: float | None = None
        self.fetches = 0

    def key_for(self, kid: str):
        with self._lock:
            now = self._clock()
            stale = self._loaded_at is None or now - self._loaded_at >= self._ttl
            unknown = kid not in self._keys
            may_retry = self._loaded_at is None or now - self._loaded_at >= self._cooldown
            if stale or (unknown and may_retry):
                self._load(now)
            return self._keys.get(kid)

    def _load(self, now: float) -> None:
        import jwt

        self.fetches += 1
        self._loaded_at = now  # a failed fetch also waits out the cooldown, so an outage is not hammered
        try:
            document = json.loads(self._fetch(self._url))
            entries = document["keys"]
            keys: dict[str, object] = {}
            for entry in entries:
                if not isinstance(entry, dict) or entry.get("kty") != "RSA" or entry.get("use", "sig") != "sig":
                    continue
                kid = entry.get("kid")
                if isinstance(kid, str) and kid:
                    keys[kid] = jwt.PyJWK(entry, algorithm=ALGORITHM)
        except Exception:  # noqa: BLE001 - any fetch or parse failure keeps the last good set; nothing is logged from it
            if not self._keys:
                raise TokenError(Reason.KEYS_UNAVAILABLE) from None
            return
        if not keys and not self._keys:
            raise TokenError(Reason.KEYS_UNAVAILABLE)
        if keys:
            self._keys = keys


class EntraTokenVerifier:
    def __init__(
        self,
        config: AuthConfig,
        *,
        fetch: Fetcher = https_fetch,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        try:
            import jwt  # noqa: F401  (PyJWT with the crypto extra; part of the `azure` extra)
        except ImportError:
            raise AuthConfigError("PyJWT is not installed (install with `uv sync --extra azure`)") from None
        self.config = config
        self.jwks = JwksCache(config.jwks_url, fetch, clock=clock)

    def verify(self, token: str) -> None:
        """Returns None for a good token; raises TokenError(reason) otherwise. Never returns or logs claims."""
        import jwt

        if len(token) > MAX_TOKEN_BYTES or not TOKEN.match(token):
            raise TokenError(Reason.MALFORMED)
        try:
            header = jwt.get_unverified_header(token)
        except jwt.PyJWTError:
            raise TokenError(Reason.MALFORMED) from None
        if header.get("alg") != ALGORITHM:
            raise TokenError(Reason.ALGORITHM)
        kid = header.get("kid")
        if not isinstance(kid, str) or not kid:
            raise TokenError(Reason.KEY_ID)
        key = self.jwks.key_for(kid)
        if key is None:
            raise TokenError(Reason.KEY_ID)
        cfg = self.config
        try:
            claims = jwt.decode(
                token,
                key.key,
                algorithms=[ALGORITHM],
                audience=list(cfg.audiences),
                issuer=list(cfg.issuers),
                leeway=cfg.clock_skew_seconds,
                options={"require": ["exp", "nbf", "iss", "aud"]},
            )
        except jwt.ExpiredSignatureError:
            raise TokenError(Reason.EXPIRED) from None
        except jwt.ImmatureSignatureError:
            raise TokenError(Reason.NOT_YET_VALID) from None
        except jwt.InvalidAudienceError:
            raise TokenError(Reason.AUDIENCE) from None
        except jwt.InvalidIssuerError:
            raise TokenError(Reason.ISSUER) from None
        except jwt.MissingRequiredClaimError:
            raise TokenError(Reason.CLAIMS) from None
        except jwt.InvalidSignatureError:
            raise TokenError(Reason.SIGNATURE) from None
        except jwt.PyJWTError:
            raise TokenError(Reason.MALFORMED) from None
        tid = claims.get("tid")
        if not isinstance(tid, str) or tid.lower() != cfg.tenant_id:
            raise TokenError(Reason.TENANT)
        roles = claims.get("roles")
        scopes = claims.get("scp")
        have_roles = {r for r in roles if isinstance(r, str)} if isinstance(roles, list) else set()
        have_scopes = set(scopes.split()) if isinstance(scopes, str) else set()
        if not (have_roles & set(cfg.required_roles) or have_scopes & set(cfg.required_scopes)):
            raise TokenError(Reason.PERMISSION)


def _unauthorized() -> JSONResponse:
    return JSONResponse(
        {"error": {"code": "unauthorized", "message": "A valid sign-in is required."}},
        status_code=401,
        headers={"WWW-Authenticate": "Bearer"},
    )


class EntraAuthMiddleware:
    """Pure ASGI, innermost: the CORS and security-header middleware wrap its 401 like any other response."""

    def __init__(self, app, verifier: EntraTokenVerifier) -> None:
        self.app = app
        self.verifier = verifier

    async def __call__(self, scope, receive, send):
        if scope["type"] == "websocket":
            await send({"type": "websocket.close", "code": 1008})
            return
        if scope["type"] != "http" or (scope["path"] == HEALTH_PATH and scope["method"] == "GET"):
            await self.app(scope, receive, send)
            return
        values = [v for k, v in scope.get("headers", []) if k == b"authorization"]
        token = _bearer(values[0]) if len(values) == 1 else None
        if token is None:
            await self._reject(scope, receive, send, Reason.MISSING)
            return
        try:
            await asyncio.to_thread(self.verifier.verify, token)
        except TokenError as exc:
            await self._reject(scope, receive, send, exc.reason)
            return
        except Exception:  # noqa: BLE001 - fail closed on anything unexpected; the class is not even logged
            await self._reject(scope, receive, send, Reason.MALFORMED)
            return
        await self.app(scope, receive, send)

    @staticmethod
    async def _reject(scope, receive, send, reason: Reason) -> None:
        logs.log_event("request_error", status=401, reason=int(reason))
        await _unauthorized()(scope, receive, send)


def _bearer(raw: bytes) -> str | None:
    try:
        text = raw.decode("ascii")
    except UnicodeDecodeError:
        return None
    scheme, _, token = text.partition(" ")
    if scheme.lower() != "bearer" or not token or " " in token:
        return None
    return token
