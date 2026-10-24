"""No credential-shaped strings in the tree; .env.example has no values; samples use only the fictional subscription."""

import json
import re
import subprocess
from pathlib import Path

from ..conftest import FICTIONAL_SUBSCRIPTION, ROOT

PATTERNS = [
    (re.compile(r"AccountKey=[A-Za-z0-9+/=]{40,}"), "storage account key"),
    (re.compile(r"-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----"), "private key"),
    (re.compile(r"eyJ[a-zA-Z0-9_-]{20,}\.[a-zA-Z0-9_-]{20,}\.[a-zA-Z0-9_-]{20,}"), "JWT"),
    (re.compile(r"ghp_[A-Za-z0-9]{36}"), "GitHub token"),
    (re.compile(r"sk-[A-Za-z0-9]{32,}"), "API key"),
    (
        re.compile(r"(client_secret|clientSecret|CLIENT_SECRET)\s*[:=]\s*[\"'][A-Za-z0-9~._-]{20,}[\"']"),
        "client secret literal",
    ),
    (re.compile(r"0x4AAAAAAA[A-Za-z0-9_-]{10,}"), "verification site key"),
    (re.compile(r"TURNSTILE_SECRET[ \t]*=[ \t]*[A-Za-z0-9_][^\s#]{7,}"), "verification secret"),
    (re.compile(r"dckr_pat_[A-Za-z0-9_-]{20,}"), "registry token"),
    (re.compile(r"pypi-AgEIcHlwaS5vcmc[A-Za-z0-9_-]{20,}"), "PyPI token"),
]
GUID = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")
SKIP_SUFFIXES = {".png", ".jpg", ".zip", ".ico", ".lock", ".woff", ".woff2"}
ENV_KEYS = (
    "CA_SCOPES",
    "AZURE_CLIENT_ID",
    "PORT",
    "CA_REFRESH_MINUTES",
    "CA_COST_ENABLED",
    "CA_PUBLIC_RESULTS",
    "CA_FRAME_ANCESTORS",
    "CA_SITE_ORIGINS",
    "CA_ALLOWED_ORIGINS",
    "CA_TRUST_PROXY",
    "CA_TURNSTILE_SITE_KEY",
    "TURNSTILE_SECRET",
    "CA_RATE_LIMIT_POSTS",
    "CA_RATE_LIMIT_WINDOW_MINUTES",
    "CA_REFRESH_COOLDOWN_MINUTES",
    "CA_PAGE_SIZE",
    "CA_MAX_ROWS",
    "CA_COLLECT_TIMEOUT_SECONDS",
    "CA_LOG_SILENT",
    "CA_STATIC_DIR",
    "CA_AUTH_ENABLED",
    "CA_AUTH_TENANT_ID",
    "CA_AUTH_AUDIENCE",
    "CA_AUTH_AUTHORITY_HOST",
    "CA_AUTH_JWKS_URL",
    "CA_AUTH_CLOCK_SKEW_SECONDS",
    "CA_AUTH_REQUIRED_ROLES",
    "CA_AUTH_REQUIRED_SCOPES",
)


def _tracked_files() -> list[Path]:
    out = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    files = [ROOT / line for line in out.splitlines() if line]
    return [f for f in files if f.is_file() and f.suffix not in SKIP_SUFFIXES and ".venv" not in f.parts]


def test_no_credential_shaped_strings():
    hits = []
    for path in _tracked_files():
        text = path.read_text(encoding="utf-8", errors="ignore")
        for rx, what in PATTERNS:
            if rx.search(text):
                hits.append(f"{path.relative_to(ROOT)}: {what}")
    assert hits == []


def test_env_example_lists_every_key_with_no_value():
    env = (ROOT / ".env.example").read_text(encoding="utf-8")
    for key in ENV_KEYS:
        assert re.search(rf"^{key}=", env, re.MULTILINE), key
    for line in env.splitlines():
        if line.startswith(
            ("TURNSTILE_SECRET", "AZURE_CLIENT_ID", "CA_SCOPES", "CA_AUTH_TENANT_ID", "CA_AUTH_AUDIENCE")
        ):
            assert line.strip().endswith("="), line
    assert not re.search(r"SECRET\s*=[ \t]*\S", env)
    for forbidden in ("AZURE_CLIENT_SECRET=", "AZURE_TENANT_ID=", "AZURE_USERNAME=", "AZURE_PASSWORD="):
        assert not re.search(rf"^{forbidden}", env, re.MULTILINE), forbidden
    # every CA_* key the code reads is documented, and nothing undocumented is read
    read = set()
    for path in (ROOT / "src" / "cloud_assessor_appliance").rglob("*.py"):
        read.update(re.findall(r'"(CA_[A-Z_]+|TURNSTILE_SECRET|AZURE_CLIENT_ID|PORT)"', path.read_text("utf-8")))
    assert read <= set(ENV_KEYS), read - set(ENV_KEYS)


def test_gitignore_excludes_secrets_and_runtime_data():
    gi = (ROOT / ".gitignore").read_text(encoding="utf-8")
    for must in (
        ".env",
        "*.tfstate",
        "*.tfvars",
        "!terraform.tfvars.example",
        "*.pem",
        "*.pfx",
        ".azure/",
        "assessment-output/",
    ):
        assert must in gi, must


def test_samples_and_fixtures_are_fictional():
    for path in (ROOT / "samples").glob("*"):
        text = path.read_text(encoding="utf-8")
        guids = set(GUID.findall(text))
        assert guids <= {FICTIONAL_SUBSCRIPTION}, f"{path.name}: {guids - {FICTIONAL_SUBSCRIPTION}}"
        assert "hcw-sample" in text or "hcwsample" in text
    rows = json.loads((ROOT / "samples" / "sample-resource-graph.json").read_text(encoding="utf-8"))["data"]
    assert all(r["subscriptionId"] == FICTIONAL_SUBSCRIPTION for r in rows)
    allowed = {
        FICTIONAL_SUBSCRIPTION,
        "00000000-0000-0000-0000-000000000002",
        "00000000-0000-0000-0000-000000000009",
        "00000000-0000-4000-8000-000000000001",
        "11111111-2222-3333-4444-555555555555",
    }
    for path in list((ROOT / "tests").rglob("*.py")) + [
        ROOT / "infrastructure/terraform/appliance-azure/terraform.tfvars.example"
    ]:
        guids = set(GUID.findall(path.read_text(encoding="utf-8")))
        assert guids <= allowed, f"{path.relative_to(ROOT)}: {guids - allowed}"
