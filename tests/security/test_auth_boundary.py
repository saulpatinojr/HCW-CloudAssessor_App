"""Sign-in boundary (T-032): every route but health refuses an anonymous caller, the new dependency stays in the
appliance-only extra, and nothing the engine package or the default (lab-side) dependency set carries has changed.
Runs without PyJWT installed (the default-set boundary job), so it uses a stub verifier."""

import re

from fastapi.testclient import TestClient

from cloud_assessor_appliance.api import api_routes, iter_routes
from cloud_assessor_appliance.security.entra import Reason, TokenError

from ..conftest import ROOT, make_app, make_settings

SRC = ROOT / "src" / "cloud_assessor_appliance"


class RefusingVerifier:
    def verify(self, token: str) -> None:
        raise TokenError(Reason.SIGNATURE)


def _signed_in_app():
    settings = make_settings(
        auth_enabled=True,
        auth_tenant_id="00000000-0000-4000-8000-000000000001",
        auth_audiences=("api://hcw-sample-assessor",),
        auth_authority_host="login.example.test",
    )
    return make_app(settings, token_verifier=RefusingVerifier())


def test_every_registered_route_but_health_answers_401_without_a_token():
    app = _signed_in_app()
    with TestClient(app) as c:
        paths = {r.path for r in iter_routes(app)}
        assert "/api/health" in paths and "/api/assessments/current" in paths
        for route in iter_routes(app):
            path = re.sub(r"\{[^}]+\}", "x", route.path)
            for method in sorted(route.methods - {"HEAD"}):
                r = c.request(method, path)
                if (path, method) == ("/api/health", "GET"):
                    assert r.status_code == 200
                else:
                    assert r.status_code == 401, (method, route.path)
                    assert r.headers["www-authenticate"] == "Bearer"
                    assert r.json()["error"]["code"] == "unauthorized"
        assert c.get("/api/health", headers={"Authorization": "Bearer a.b.c"}).status_code == 200
        assert c.get("/api/catalog", headers={"Authorization": "Bearer a.b.c"}).status_code == 401
    assert set(api_routes(app)) >= {"/api/health", "/api/refresh", "/api/catalog"}


def test_pyjwt_is_declared_only_in_the_appliance_extra_and_the_default_lock_is_unchanged():
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    default_deps = pyproject.split("[project.optional-dependencies]")[0]
    extra = pyproject.split("[project.optional-dependencies]")[1].split("[dependency-groups]")[0]
    assert "jwt" not in default_deps.lower()
    assert re.search(r'"pyjwt\[crypto\]==\d+\.\d+\.\d+"', extra)
    default_lock = (ROOT / "requirements.lock.txt").read_text(encoding="utf-8").lower()
    assert not re.search(r"^(pyjwt|cryptography)==", default_lock, re.MULTILINE)


def test_the_engine_package_imports_no_token_library():
    for path in (ROOT / "packages" / "cloud-assessor-core").rglob("*.py"):
        if ".venv" not in path.parts:
            text = path.read_text(encoding="utf-8", errors="ignore")
            assert not re.search(r"^\s*(import|from)\s+(jwt|cryptography)\b", text, re.MULTILINE), path


def test_sign_in_module_holds_no_secret_endpoint_or_token_logging():
    text = (SRC / "security" / "entra.py").read_text(encoding="utf-8")
    code = "\n".join(line.split("#", 1)[0] for line in text.splitlines())
    assert "login.microsoftonline.com" not in text  # the authority host is a setting, never a literal
    for needle in ("client_secret", "ClientSecret", "verify_signature", 'algorithms=["none"', "HS256"):
        assert needle not in code, needle
    assert "RS256" in code
    # the only log call writes a status and a numeric reason; no token or claim is ever passed to it
    assert code.count("logs.log_event(") == 1
    assert 'logs.log_event("request_error", status=401, reason=int(reason))' in code
