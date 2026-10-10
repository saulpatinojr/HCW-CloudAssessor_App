"""Every `uses:` is a 40-hex SHA with a version comment; runners are ubuntu-26.04; no registry token anywhere."""

import re

import yaml

from ..conftest import ROOT

WORKFLOWS = sorted((ROOT / ".github" / "workflows").glob("*.yml"))
USES = re.compile(r"^\s*(?:-\s+)?uses:\s*([^\s#]+)\s*#\s*(v\S+)", re.MULTILINE)
ANY_USES = re.compile(r"^\s*(?:-\s+)?uses:\s*(\S+)", re.MULTILINE)


def test_workflow_set_is_complete():
    assert [p.name for p in WORKFLOWS] == [
        "ci.yml",
        "publish-core.yml",
        "publish-images.yml",
        "release.yml",
        "security.yml",
    ]


def test_every_uses_is_sha_pinned_with_a_version_comment():
    for path in WORKFLOWS:
        text = path.read_text(encoding="utf-8")
        every = ANY_USES.findall(text)
        pinned = USES.findall(text)
        assert len(every) == len(pinned), f"{path.name}: an action lacks a version comment"
        for ref, _version in pinned:
            owner_repo, sha = ref.rsplit("@", 1)
            assert re.fullmatch(r"[0-9a-f]{40}", sha), f"{path.name}: {ref} is not SHA-pinned"
            assert "/" in owner_repo


def test_runners_permissions_and_no_long_lived_tokens():
    for path in WORKFLOWS:
        text = path.read_text(encoding="utf-8")
        doc = yaml.safe_load(text)
        code = "\n".join(line.split("#", 1)[0] for line in text.splitlines())
        assert "ubuntu-latest" not in code and "DOCKERHUB_TOKEN" not in code and "DOCKERHUB_USERNAME" not in code
        assert "PYPI_TOKEN" not in code and "PYPI_API_TOKEN" not in code and "setup-uv" not in code
        assert doc["permissions"] == {"contents": "read"}, f"{path.name}: top-level permissions must be contents: read"
        for name, job in doc["jobs"].items():
            assert job["runs-on"] == "ubuntu-26.04", f"{path.name}:{name}"


def test_publish_images_pushes_only_the_appliance_target():
    text = (ROOT / ".github" / "workflows" / "publish-images.yml").read_text(encoding="utf-8")
    doc = yaml.safe_load(text)
    steps = doc["jobs"]["build-scan-publish"]["steps"]
    pushes = [s for s in steps if isinstance(s.get("with"), dict) and s["with"].get("push") is True]
    assert len(pushes) == 1 and pushes[0]["with"]["target"] == "appliance"
    assert "hcw-cloud-assessor-lab" in text and "hcw-addon-cloud-assessment" not in doc["env"]["IMAGE"]
    assert doc["env"]["IMAGE"] == "docker.io/hybridcloudworks/hcw-cloud-assessor-appliance"
    assert "vars.DOCKERHUB_ENABLED" in text and "DOCKERHUB_OIDC_CONNECTIONID" in text


def test_ci_runs_every_section_20_check_that_can_run_in_ci():
    text = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    for needle in (
        "uv run ruff check .",
        "uv run ruff format --check .",
        "scripts/check-catalog.py",
        "scripts/check-docs-governance.py",
        "scripts/check-versions.sh",
        "scripts/check-lockfiles.sh",
        "--cov-fail-under=85",
        "tests/security tests/packaging",
        "terraform fmt -check",
        "validate",
        "--target lab" if "--target lab" in text else "target: lab",
        "target: appliance",
        'python -c "import azure"',
        "import azure.identity",
        "ClientSecretCredential",
    ):
        assert needle in text, needle
