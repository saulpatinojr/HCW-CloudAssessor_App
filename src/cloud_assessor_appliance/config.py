"""Settings from the environment (prefix CA_). No secret is ever logged or echoed; TURNSTILE_SECRET is read once.

The appliance reads only the keys listed in .env.example. No AZURE_* variable other than AZURE_CLIENT_ID is read here;
identity.py refuses the client-secret shaped ones at startup.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
TURNSTILE_ACTION = "cloud-assessment-refresh"

# Upper bound for every numeric setting: large enough for any real deployment, small enough that every derived value
# (minutes * 60, seconds into asyncio/datetime arithmetic) stays representable.
MAX_SETTING = 1_000_000_000


def _int(env: Mapping[str, str], key: str, default: int, *, minimum: int = 0) -> int:
    raw = env.get(key, "").strip()
    if not raw:
        return default
    if not raw.isdigit() or len(raw) > 10:
        raise ValueError(f"{key} must be an integer between {minimum} and {MAX_SETTING}")
    value = int(raw)
    if value < minimum or value > MAX_SETTING:
        raise ValueError(f"{key} must be between {minimum} and {MAX_SETTING}")
    return value


def _flag(env: Mapping[str, str], key: str, default: bool = False) -> bool:
    raw = env.get(key, "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


def _origins(env: Mapping[str, str], key: str) -> tuple[str, ...]:
    raw = env.get(key, "").replace(",", " ")
    origins = []
    for item in raw.split():
        item = item.strip().rstrip("/")
        if not item.startswith(("https://", "http://")) or " " in item:
            raise ValueError(f"{key} entries must be origins (scheme://host[:port])")
        origins.append(item)
    return tuple(dict.fromkeys(origins))


@dataclass(frozen=True)
class Settings:
    port: int = 8080
    allowed_origins: tuple[str, ...] = ()
    frame_ancestors: str = "'none'"
    site_origins: tuple[str, ...] = ()
    turnstile_secret: str | None = field(default=None, repr=False)
    turnstile_site_key: str | None = None
    trust_proxy: bool = False
    log_silent: bool = False
    static_dir: Path = PACKAGE_DIR / "web"
    # appliance
    ca_scopes: str = ""
    refresh_minutes: int = 60
    cost_enabled: bool = True
    public_results: bool = False
    rate_limit_posts: int = 1
    rate_limit_window_minutes: int = 10
    refresh_cooldown_minutes: int = 10
    page_size: int = 1000
    max_rows: int = 50_000
    collect_timeout_seconds: int = 900

    @property
    def turnstile_required(self) -> bool:
        """Verification on POST /api/refresh is enabled exactly when a secret is configured (optional here)."""
        return self.turnstile_secret is not None and self.turnstile_secret != ""

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> Settings:
        env = os.environ if env is None else env
        secret = env.get("TURNSTILE_SECRET", "").strip() or None
        frame_ancestors = env.get("CA_FRAME_ANCESTORS", "").strip() or "'none'"
        if any(ch in frame_ancestors for ch in ";\n\r"):
            raise ValueError("CA_FRAME_ANCESTORS must be a single CSP source list")
        static_dir = Path(env.get("CA_STATIC_DIR", "").strip() or cls.static_dir)
        return cls(
            port=_int(env, "PORT", 8080, minimum=1),
            allowed_origins=_origins(env, "CA_ALLOWED_ORIGINS"),
            frame_ancestors=frame_ancestors,
            site_origins=_origins(env, "CA_SITE_ORIGINS"),
            turnstile_secret=secret,
            turnstile_site_key=env.get("CA_TURNSTILE_SITE_KEY", "").strip() or None,
            trust_proxy=_flag(env, "CA_TRUST_PROXY"),
            log_silent=_flag(env, "CA_LOG_SILENT"),
            static_dir=static_dir,
            ca_scopes=env.get("CA_SCOPES", "").strip(),
            refresh_minutes=_int(env, "CA_REFRESH_MINUTES", 60, minimum=1),
            cost_enabled=_flag(env, "CA_COST_ENABLED", default=True),
            public_results=_flag(env, "CA_PUBLIC_RESULTS"),
            rate_limit_posts=_int(env, "CA_RATE_LIMIT_POSTS", 1, minimum=1),
            rate_limit_window_minutes=_int(env, "CA_RATE_LIMIT_WINDOW_MINUTES", 10, minimum=1),
            refresh_cooldown_minutes=_int(env, "CA_REFRESH_COOLDOWN_MINUTES", 10, minimum=0),
            page_size=_int(env, "CA_PAGE_SIZE", 1000, minimum=1),
            max_rows=_int(env, "CA_MAX_ROWS", 50_000, minimum=1),
            collect_timeout_seconds=_int(env, "CA_COLLECT_TIMEOUT_SECONDS", 900, minimum=1),
        )
