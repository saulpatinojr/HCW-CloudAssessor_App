"""Entra access-token validation (T-032, R-009 option b). No network: an RSA key pair is made at test time, the JWKS
is served by an injected fetcher and every token is minted here. Identifiers are the fictional ones allowed here."""

import base64
import hashlib
import hmac
import io
import json
import sys
import time

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from cloud_assessor_appliance.config import Settings
from cloud_assessor_appliance.security.entra import (
    AuthConfig,
    AuthConfigError,
    EntraTokenVerifier,
    JwksCache,
    Reason,
    TokenError,
)

from ..conftest import SCOPE, make_app, make_settings, run_refresh

TENANT = "00000000-0000-4000-8000-000000000001"
OTHER_TENANT = "00000000-0000-0000-0000-000000000009"
AUDIENCE = "api://hcw-sample-assessor"
HOST = "login.example.test"
KID = "hcw-sample-key-1"
ROLE = "Assessment.Read"
ROUTES = [
    ("GET", "/"),
    ("GET", "/index.html"),
    ("GET", "/api/catalog"),
    ("POST", "/api/refresh"),
    ("GET", "/api/assessments/current"),
    ("GET", "/api/assessments/current/report.md"),
    ("GET", "/api/assessments/current/report.json"),
    ("GET", "/api/assessments/current/bundle.zip"),
    ("POST", "/api/assessments"),
    ("GET", "/api/nothing-here"),
    ("GET", "/api/health/"),
    ("OPTIONS", "/api/catalog"),
    ("DELETE", "/api/health"),
]


def _rsa():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


SIGNING_KEY = _rsa()
OTHER_KEY = _rsa()


def jwk_of(key, kid: str) -> dict:
    document = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key()))
    document.update({"kid": kid, "use": "sig", "alg": "RS256"})
    return document


class Jwks:
    """A fetcher serving a mutable JWKS document; records how often it was called."""

    def __init__(self, *keys: tuple[object, str]) -> None:
        self.keys = [jwk_of(k, kid) for k, kid in keys]
        self.calls = 0
        self.fail = False

    def __call__(self, url: str) -> bytes:
        self.calls += 1
        if self.fail:
            raise OSError("down")
        return json.dumps({"keys": self.keys}).encode()


def claims(**overrides) -> dict:
    now = int(time.time())
    base = {
        "iss": f"https://{HOST}/{TENANT}/v2.0",
        "aud": AUDIENCE,
        "tid": TENANT,
        "nbf": now - 5,
        "iat": now - 5,
        "exp": now + 600,
        "roles": [ROLE],
    }
    base.update(overrides)
    return {k: v for k, v in base.items() if v is not None}


def mint(payload: dict | None = None, *, key=SIGNING_KEY, kid: str | None = KID, **overrides) -> str:
    payload = claims(**overrides) if payload is None else payload
    headers = {"kid": kid} if kid is not None else {}
    return jwt.encode(payload, key, algorithm="RS256", headers=headers)


def b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def forge(header: dict, payload: dict, signature: bytes = b"") -> str:
    return ".".join([b64(json.dumps(header).encode()), b64(json.dumps(payload).encode()), b64(signature)])


def auth_settings(**overrides) -> Settings:
    base = {
        "auth_enabled": True,
        "auth_tenant_id": TENANT,
        "auth_audiences": (AUDIENCE,),
        "auth_authority_host": HOST,
    }
    base.update(overrides)
    return make_settings(**base)


@pytest.fixture
def jwks():
    return Jwks((SIGNING_KEY, KID))


def build(settings: Settings, jwks: Jwks):
    verifier = EntraTokenVerifier(AuthConfig.from_settings(settings), fetch=jwks)
    return make_app(settings, token_verifier=verifier)


@pytest.fixture
def client(jwks):
    with TestClient(build(auth_settings(), jwks)) as c:
        yield c


def bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def assert_refused(response, token: str | None = None):
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    body = response.json()
    assert body == {"error": {"code": "unauthorized", "message": "A valid sign-in is required."}}
    if token:
        assert token not in response.text and token not in str(response.headers)


# ----- accepted -----


def test_valid_v2_token_is_accepted(client):
    r = client.get("/api/catalog", headers=bearer(mint()))
    assert r.status_code == 200 and r.json()["count"] > 0


def test_valid_v1_issuer_and_delegated_scope_are_accepted(client):
    token = mint(iss=f"https://sts.windows.net/{TENANT}/", roles=None, scp="openid Assessment.Read")
    assert client.get("/api/catalog", headers=bearer(token)).status_code == 200


def test_tenant_id_comparison_ignores_case_and_scheme_is_case_insensitive(client):
    token = mint(tid=TENANT.upper())
    assert client.get("/api/catalog", headers={"Authorization": f"bEaReR {token}"}).status_code == 200


def test_any_configured_audience_is_accepted(jwks):
    app = build(auth_settings(auth_audiences=(AUDIENCE, "00000000-0000-0000-0000-000000000002")), jwks)
    with TestClient(app) as c:
        assert (
            c.get("/api/catalog", headers=bearer(mint(aud="00000000-0000-0000-0000-000000000002"))).status_code == 200
        )


def test_configured_required_role_replaces_the_default(jwks):
    app = build(auth_settings(auth_required_roles=("Hcw.Assess",), auth_required_scopes=()), jwks)
    with TestClient(app) as c:
        assert c.get("/api/catalog", headers=bearer(mint(roles=["Hcw.Assess"]))).status_code == 200
        assert_refused(c.get("/api/catalog", headers=bearer(mint(roles=[ROLE]))))


# ----- refused -----


def _hs256_with_public_key() -> str:
    public_pem = SIGNING_KEY.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    signing_input = ".".join(
        [b64(json.dumps({"alg": "HS256", "kid": KID}).encode()), b64(json.dumps(claims()).encode())]
    )
    signature = hmac.new(public_pem, signing_input.encode(), hashlib.sha256).digest()
    return signing_input + "." + b64(signature)


def _tampered() -> str:
    head, _, sig = mint().split(".")
    return ".".join([head, b64(json.dumps(claims(roles=[ROLE, "Admin"], aud="elsewhere")).encode()), sig])


REFUSED = {
    "garbage": ("not a token", Reason.MALFORMED),
    "two parts": ("abc.def", Reason.MALFORMED),
    "non-base64 header": ("!!!.@@@.###", Reason.MALFORMED),
    "empty parts": ("..", Reason.MALFORMED),
    "expired": (mint(exp=int(time.time()) - 3600, nbf=int(time.time()) - 7200), Reason.EXPIRED),
    "not yet valid": (mint(nbf=int(time.time()) + 3600, exp=int(time.time()) + 7200), Reason.NOT_YET_VALID),
    "wrong audience": (mint(aud="api://someone-else"), Reason.AUDIENCE),
    "wrong issuer": (mint(iss="https://evil.example.test/" + TENANT + "/v2.0"), Reason.ISSUER),
    "issuer of another tenant": (mint(iss=f"https://{HOST}/{OTHER_TENANT}/v2.0"), Reason.ISSUER),
    "wrong tenant claim": (mint(tid=OTHER_TENANT), Reason.TENANT),
    "no tenant claim": (mint(tid=None), Reason.TENANT),
    "token for another tenant": (
        mint(tid=OTHER_TENANT, iss=f"https://{HOST}/{OTHER_TENANT}/v2.0"),
        Reason.ISSUER,
    ),
    "unknown kid": (mint(kid="hcw-sample-key-unknown"), Reason.KEY_ID),
    "no kid": (mint(kid=None), Reason.KEY_ID),
    "signed by another key": (mint(key=OTHER_KEY), Reason.SIGNATURE),
    "tampered payload": (_tampered(), Reason.SIGNATURE),
    "alg none": (forge({"alg": "none", "kid": KID}, claims()), Reason.ALGORITHM),
    "alg none, upper case": (forge({"alg": "NONE", "kid": KID}, claims()), Reason.ALGORITHM),
    "HS256 with the public key as secret": (_hs256_with_public_key(), Reason.ALGORITHM),
    "RS384": (jwt.encode(claims(), SIGNING_KEY, algorithm="RS384", headers={"kid": KID}), Reason.ALGORITHM),
    "no exp": (mint(exp=None), Reason.CLAIMS),
    "no nbf": (mint(nbf=None), Reason.CLAIMS),
    "no audience": (mint(aud=None), Reason.CLAIMS),
    "no role or scope": (mint(roles=None), Reason.PERMISSION),
    "another role": (mint(roles=["Reader"]), Reason.PERMISSION),
    "another scope": (mint(roles=None, scp="User.Read"), Reason.PERMISSION),
    "roles of the wrong type": (mint(roles=ROLE), Reason.PERMISSION),
    "oversized": ("a." * 20_000 + "b", Reason.MALFORMED),
}


@pytest.mark.parametrize("name", sorted(REFUSED))
def test_bad_tokens_are_refused_for_the_right_reason(name, client, jwks):
    token, reason = REFUSED[name]
    response = client.get("/api/catalog", headers=bearer(token))
    assert_refused(response, token)
    verifier = EntraTokenVerifier(AuthConfig.from_settings(auth_settings()), fetch=jwks)
    with pytest.raises(TokenError) as raised:
        verifier.verify(token)
    assert raised.value.reason is reason


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"Authorization": ""},
        {"Authorization": "Bearer"},
        {"Authorization": "Bearer "},
        {"Authorization": "Basic dXNlcjpwYXNz"},
        {"Authorization": "Token abc.def.ghi"},
        {"Authorization": "Bearer a b"},
    ],
)
def test_missing_or_malformed_header_is_refused(headers, client):
    assert_refused(client.get("/api/catalog", headers=headers))


def test_two_authorization_headers_are_refused(client):
    token = mint()
    r = client.get("/api/catalog", headers=[("Authorization", f"Bearer {token}"), ("Authorization", f"Bearer {token}")])
    assert_refused(r)


def test_token_in_the_query_string_is_not_read(client):
    assert_refused(client.get(f"/api/catalog?access_token={mint()}"))


@pytest.mark.parametrize(("method", "path"), ROUTES)
def test_every_route_but_health_needs_a_token(method, path, client):
    assert_refused(client.request(method, path))
    # and a valid token is not refused by the sign-in layer (the route answers whatever it answers)
    assert client.request(method, path, headers=bearer(mint())).status_code != 401


def test_health_stays_open_and_content_free(client):
    r = client.get("/api/health")
    assert r.status_code == 200 and r.json()["id"] and r.json()["edition"] == "appliance"
    assert client.head("/api/health").status_code == 401  # only the GET that the probes and the pane use is open
    text = r.text
    assert TENANT not in text and AUDIENCE not in text and HOST not in text


def test_clock_skew_is_declared_and_enforced(jwks):
    now = int(time.time())
    app = build(auth_settings(auth_clock_skew_seconds=60), jwks)
    with TestClient(app) as c:
        assert c.get("/api/catalog", headers=bearer(mint(nbf=now + 30))).status_code == 200
        assert c.get("/api/catalog", headers=bearer(mint(exp=now - 30, nbf=now - 600))).status_code == 200
        assert_refused(c.get("/api/catalog", headers=bearer(mint(nbf=now + 120, exp=now + 900))))
        assert_refused(c.get("/api/catalog", headers=bearer(mint(exp=now - 120, nbf=now - 600))))
    strict = build(auth_settings(auth_clock_skew_seconds=0), jwks)
    with TestClient(strict) as c:
        assert_refused(c.get("/api/catalog", headers=bearer(mint(nbf=now + 30))))


# ----- the CA_PUBLIC_RESULTS gate is still a separate lock -----


def test_gate_still_answers_403_with_a_valid_token_when_the_switch_is_off(jwks):
    with TestClient(build(auth_settings(public_results=False), jwks)) as c:
        run_refresh(c)
        r = c.get("/api/assessments/current", headers=bearer(mint()))
        assert r.status_code == 403 and r.json()["error"]["code"] == "results_not_public"
        for path in ("report.md", "report.json", "bundle.zip"):
            assert c.get(f"/api/assessments/current/{path}", headers=bearer(mint())).status_code == 403
        assert_refused(c.get("/api/assessments/current"))


def test_results_need_both_the_switch_and_a_token(jwks):
    with TestClient(build(auth_settings(public_results=True), jwks)) as c:
        run_refresh(c)
        assert_refused(c.get("/api/assessments/current"))
        r = c.get("/api/assessments/current", headers=bearer(mint()))
        assert r.status_code == 200 and "assessment" in r.json()


def test_refresh_needs_a_token(jwks):
    with TestClient(build(auth_settings(rate_limit_posts=5), jwks)) as c:
        assert_refused(c.post("/api/refresh"))
        assert c.post("/api/refresh", headers=bearer(mint())).status_code == 202


def test_cors_headers_wrap_the_401_for_an_allowed_origin(jwks):
    origin = "https://hybridcloudworks.com"
    with TestClient(build(auth_settings(allowed_origins=(origin,)), jwks)) as c:
        r = c.get("/api/catalog", headers={"Origin": origin})
        assert_refused(r)
        assert r.headers["access-control-allow-origin"] == origin
        pre = c.options(
            "/api/catalog",
            headers={"Origin": origin, "Access-Control-Request-Method": "GET"},
        )
        assert pre.status_code == 204  # a preflight carries no credentials and is answered by the CORS layer


# ----- logs -----


def test_logs_never_contain_a_token_or_claim(monkeypatch, jwks):
    buf = io.StringIO()
    monkeypatch.setattr(sys, "stderr", buf)
    good = mint()
    bad = [mint(aud="api://someone-else"), mint(tid=OTHER_TENANT), _tampered(), "x.y.z", REFUSED["alg none"][0]]
    with TestClient(build(auth_settings(log_silent=False), jwks)) as c:
        c.get("/api/catalog", headers=bearer(good))
        for token in bad:
            c.get("/api/catalog", headers=bearer(token))
        c.get("/api/catalog")
    out = buf.getvalue()
    for secret in [good, *bad, *good.split("."), TENANT, AUDIENCE, HOST, KID]:
        assert secret not in out
    events = [json.loads(line) for line in out.splitlines() if line]
    rejected = [e for e in events if e["event"] == "request_error"]
    assert len(rejected) == len(bad) + 1 and all(e["status"] == 401 and isinstance(e["reason"], int) for e in rejected)
    assert [e for e in events if e["event"] == "startup"][0]["authEnabled"] is True


# ----- keys -----


def test_keys_are_cached_across_requests(client, jwks):
    for _ in range(5):
        assert client.get("/api/catalog", headers=bearer(mint())).status_code == 200
    assert jwks.calls == 1


def test_unknown_kid_refetches_at_most_once_per_cooldown_and_picks_up_rotation():
    now = [0.0]
    jwks = Jwks((SIGNING_KEY, KID))
    cache = JwksCache("https://keys.example.test/keys", jwks, ttl=300, cooldown=60, clock=lambda: now[0])
    assert cache.key_for(KID) is not None and jwks.calls == 1
    for _ in range(20):  # forged kids inside the cooldown cause no outbound request
        assert cache.key_for("forged") is None
    assert jwks.calls == 1
    now[0] = 61
    jwks.keys.append(jwk_of(OTHER_KEY, "hcw-sample-key-2"))
    assert cache.key_for("hcw-sample-key-2") is not None and jwks.calls == 2
    now[0] = 100
    assert cache.key_for("forged") is None and jwks.calls == 2  # the cooldown restarted
    now[0] = 400  # older than the cache lifetime: refreshed whatever kid is asked
    assert cache.key_for(KID) is not None and jwks.calls == 3


def test_failed_fetch_with_no_keys_refuses_and_with_old_keys_keeps_them():
    now = [0.0]
    jwks = Jwks((SIGNING_KEY, KID))
    jwks.fail = True
    cache = JwksCache("https://keys.example.test/keys", jwks, ttl=300, cooldown=60, clock=lambda: now[0])
    with pytest.raises(TokenError) as raised:
        cache.key_for(KID)
    assert raised.value.reason is Reason.KEYS_UNAVAILABLE
    now[0] = 61
    jwks.fail = False
    assert cache.key_for(KID) is not None
    now[0] = 1000
    jwks.fail = True
    assert cache.key_for(KID) is not None  # last good set survives an outage


def test_outage_is_a_401_not_an_open_door(jwks):
    jwks.fail = True
    with TestClient(build(auth_settings(), jwks)) as c:
        assert_refused(c.get("/api/catalog", headers=bearer(mint())))


def test_only_rsa_signing_keys_are_loaded():
    jwks = Jwks((SIGNING_KEY, KID))
    jwks.keys += [
        {"kty": "oct", "kid": "sym", "k": b64(b"secret")},
        {**jwk_of(OTHER_KEY, "enc"), "use": "enc"},
        {"kty": "RSA", "n": "AQAB"},
        "junk",
    ]
    cache = JwksCache("https://keys.example.test/keys", jwks)
    assert cache.key_for(KID) is not None
    for kid in ("sym", "enc"):
        assert cache.key_for(kid) is None


def test_default_fetcher_refuses_plain_http():
    from cloud_assessor_appliance.security.entra import https_fetch

    with pytest.raises(OSError):
        https_fetch("http://keys.example.test/keys")


def test_jwks_address_is_built_from_the_host_and_tenant_unless_overridden():
    assert AuthConfig.from_settings(auth_settings()).jwks_url == f"https://{HOST}/{TENANT}/discovery/v2.0/keys"
    custom = auth_settings(auth_jwks_url="https://keys.example.test/k")
    assert AuthConfig.from_settings(custom).jwks_url == "https://keys.example.test/k"
    assert AuthConfig.from_settings(auth_settings()).issuers == (
        f"https://{HOST}/{TENANT}/v2.0",
        f"https://sts.windows.net/{TENANT}/",
    )


# ----- configuration and startup -----


ENV = {
    "CA_SCOPES": SCOPE,
    "CA_AUTH_ENABLED": "true",
    "CA_AUTH_TENANT_ID": TENANT,
    "CA_AUTH_AUDIENCE": f"{AUDIENCE}, 00000000-0000-0000-0000-000000000002",
    "CA_AUTH_AUTHORITY_HOST": HOST,
}


def test_sign_in_is_off_by_default_and_the_defaults_are_declared():
    s = Settings.from_env({"CA_SCOPES": SCOPE})
    assert not s.auth_enabled and s.auth_clock_skew_seconds == 60
    assert s.auth_required_roles == (ROLE,) and s.auth_required_scopes == (ROLE,)


def test_env_parsing_when_enabled():
    s = Settings.from_env(
        {
            **ENV,
            "CA_AUTH_CLOCK_SKEW_SECONDS": "30",
            "CA_AUTH_REQUIRED_ROLES": "A.B, C.D",
            "CA_AUTH_REQUIRED_SCOPES": "x",
        }
    )
    assert (
        s.auth_enabled
        and s.auth_tenant_id == TENANT
        and s.auth_audiences == (AUDIENCE, "00000000-0000-0000-0000-000000000002")
    )
    assert (
        s.auth_clock_skew_seconds == 30 and s.auth_required_roles == ("A.B", "C.D") and s.auth_required_scopes == ("x",)
    )


@pytest.mark.parametrize(
    ("drop", "text"),
    [("CA_AUTH_TENANT_ID", "TENANT"), ("CA_AUTH_AUDIENCE", "AUDIENCE"), ("CA_AUTH_AUTHORITY_HOST", "AUTHORITY_HOST")],
)
def test_enabled_without_its_settings_refuses_to_start(drop, text):
    env = {k: v for k, v in ENV.items() if k != drop}
    with pytest.raises(ValueError, match=text):
        Settings.from_env(env)


@pytest.mark.parametrize(
    "override",
    [
        {"CA_AUTH_TENANT_ID": "contoso.example.test"},
        {"CA_AUTH_TENANT_ID": TENANT + "/../x"},
        {"CA_AUTH_AUTHORITY_HOST": "https://login.example.test"},
        {"CA_AUTH_AUTHORITY_HOST": "login.example.test/path"},
        {"CA_AUTH_AUTHORITY_HOST": "127.0.0.1"},
        {"CA_AUTH_JWKS_URL": "http://keys.example.test/keys"},
        {"CA_AUTH_CLOCK_SKEW_SECONDS": "301"},
        {"CA_AUTH_AUDIENCE": ","},
    ],
)
def test_malformed_sign_in_settings_refuse_to_start(override):
    with pytest.raises(ValueError):
        Settings.from_env({**ENV, **override})


def test_publishing_results_without_sign_in_refuses_to_start():
    with pytest.raises(ValueError, match="CA_PUBLIC_RESULTS=true needs sign-in"):
        Settings.from_env({"CA_SCOPES": SCOPE, "CA_PUBLIC_RESULTS": "true"})
    assert Settings.from_env({**ENV, "CA_PUBLIC_RESULTS": "true"}).public_results


def test_create_app_refuses_bad_auth_settings_and_builds_a_verifier_when_good():
    with pytest.raises(AuthConfigError):
        make_app(auth_settings(auth_tenant_id=None))
    app = make_app(auth_settings())  # builds its own verifier; nothing is fetched until a token arrives
    with TestClient(app) as c:
        assert_refused(c.get("/api/catalog"))
        assert c.get("/api/health").status_code == 200


def test_sign_in_off_changes_nothing():
    with TestClient(make_app(make_settings())) as c:
        assert c.get("/api/catalog").status_code == 200
        assert c.get("/api/health").status_code == 200
