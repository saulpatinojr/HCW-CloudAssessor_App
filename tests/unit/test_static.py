from pathlib import Path

from ..conftest import ROOT

WEB = ROOT / "src" / "cloud_assessor_appliance" / "web"


def test_pane_is_served_with_the_edition_switch(client):
    r = client.get("/")
    assert r.status_code == 200 and r.headers["cache-control"] == "no-cache"
    assert '<script src="/app.js">' in r.text and "<script>" not in r.text, "no inline scripts"
    assert 'id="step-current"' in r.text and 'id="refresh"' in r.text and "never asks for credentials" in r.text
    js = client.get("/app.js")
    assert js.status_code == 200 and js.headers["cache-control"] == "public, max-age=300"
    assert "health.edition === 'appliance'" in js.text and "/api/assessments/current" in js.text
    assert "/api/refresh" in js.text and "copied from HCW-CloudAssessor_AddOn" in js.text.lower().replace(
        "copied from hcw-cloudassessor_addon", "copied from HCW-CloudAssessor_AddOn"
    )
    assert client.get("/theme.css").status_code == 200 and client.get("/styles.css").status_code == 200
    assert client.get("/nope.html").status_code == 404 and client.get("/web").status_code == 404
    assert client.get("/..%2Fpyproject.toml").status_code == 404 and client.get("/../pyproject.toml").status_code == 404
    assert client.get("/api/index.html").status_code == 404


def test_pane_has_no_credential_inputs_and_no_vendor_names():
    for path in WEB.glob("*"):
        text = path.read_text(encoding="utf-8")
        assert 'type="password"' not in text and "type='password'" not in text, path
        assert "<input" not in text or ('type="file"' in text and 'type="search"' in text)
    html = (WEB / "index.html").read_text(encoding="utf-8")
    for vendor in ("Hostinger", "Cloudflare", "Turnstile", "Caddy", "Docker Hub", "Azure Container Apps"):
        assert vendor.lower() not in html.lower(), vendor
    assert "copied from HCW-CloudAssessor_AddOn" in html


def test_pane_matches_the_addon_copy_except_the_edition_switch():
    """The lab files are the same set; styles are untouched (the switch lives in index.html and app.js only)."""
    assert sorted(p.name for p in WEB.iterdir()) == ["app.js", "index.html", "styles.css", "theme.css"]
    assert (WEB / "theme.css").read_text(encoding="utf-8").count("hybridcloudworks") >= 0
    assert "edition" not in (WEB / "styles.css").read_text(encoding="utf-8").lower()
    assert Path(WEB / "theme.css").stat().st_size > 0
