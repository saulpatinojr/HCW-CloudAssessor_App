import pytest

from cloud_assessor_appliance.config import MAX_SETTING, Settings

from ..conftest import SCOPE


def test_defaults_and_env_parsing():
    s = Settings.from_env({"CA_SCOPES": SCOPE})
    assert s.port == 8080 and s.refresh_minutes == 60 and s.cost_enabled and not s.public_results
    assert s.rate_limit_posts == 1 and s.rate_limit_window_minutes == 10 and s.refresh_cooldown_minutes == 10
    assert s.page_size == 1000 and s.max_rows == 50_000 and s.frame_ancestors == "'none'" and not s.turnstile_required
    assert s.collect_timeout_seconds == 900
    assert Settings.from_env({"CA_SCOPES": SCOPE, "CA_COLLECT_TIMEOUT_SECONDS": "30"}).collect_timeout_seconds == 30
    s = Settings.from_env(
        {
            "CA_SCOPES": SCOPE,
            "PORT": "9000",
            "CA_REFRESH_MINUTES": "5",
            "CA_COST_ENABLED": "0",
            "CA_PUBLIC_RESULTS": "true",
            "CA_FRAME_ANCESTORS": "https://hybridcloudworks.com",
            "CA_SITE_ORIGINS": "https://hybridcloudworks.com, https://www.hybridcloudworks.com/",
            "CA_ALLOWED_ORIGINS": "https://hybridcloudworks.com",
            "CA_TRUST_PROXY": "1",
            "TURNSTILE_SECRET": "s",
            "CA_TURNSTILE_SITE_KEY": "k",
            "CA_REFRESH_COOLDOWN_MINUTES": "0",
            "CA_PAGE_SIZE": "500",
            "CA_MAX_ROWS": "10",
            "CA_LOG_SILENT": "1",
        }
    )
    assert s.port == 9000 and s.refresh_minutes == 5 and not s.cost_enabled and s.public_results
    assert s.site_origins == ("https://hybridcloudworks.com", "https://www.hybridcloudworks.com")
    assert s.allowed_origins == ("https://hybridcloudworks.com",) and s.trust_proxy and s.log_silent
    assert s.turnstile_required and s.turnstile_site_key == "k" and "turnstile_secret" not in repr(s)
    assert s.refresh_cooldown_minutes == 0 and s.page_size == 500 and s.max_rows == 10


@pytest.mark.parametrize(
    "env",
    [
        {"PORT": "0"},
        {"PORT": "abc"},
        {"CA_REFRESH_MINUTES": str(MAX_SETTING + 1)},
        {"CA_MAX_ROWS": "12345678901"},
        {"CA_COLLECT_TIMEOUT_SECONDS": "0"},
        {"CA_FRAME_ANCESTORS": "'none'; script-src *"},
        {"CA_SITE_ORIGINS": "hybridcloudworks.com"},
    ],
)
def test_invalid_values_raise(env):
    with pytest.raises(ValueError):
        Settings.from_env({"CA_SCOPES": SCOPE, **env})
