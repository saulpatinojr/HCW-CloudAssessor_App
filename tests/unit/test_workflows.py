"""Every `uses:` is a 40-hex SHA with a version comment; runners are ubuntu-26.04; no registry token anywhere."""

import re

import yaml

from ..conftest import ROOT

WORKFLOWS = sorted((ROOT / ".github" / "workflows").glob("*.yml"))
USES = re.compile(r"^\s*(?:-\s+)?uses:\s*([^\s#]+)\s*#\s*(v\S+)", re.MULTILINE)
# A local action (`uses: ./.github/actions/...`) has no SHA to pin; its own `uses:` are pinned in its action.yml.
ANY_USES = re.compile(r"^\s*(?:-\s+)?uses:\s*(?!\./)(\S+)", re.MULTILINE)


def test_workflow_set_is_complete():
    assert [p.name for p in WORKFLOWS] == [
        "ci.yml",
        "publish-core.yml",
        "publish-images.yml",
        "rehearse-self-merging-pr.yml",
        "release.yml",
        "repository-admin.yml",
        "security.yml",
    ]


def test_every_uses_is_sha_pinned_with_a_version_comment():
    for path in WORKFLOWS:
        text = path.read_text(encoding="utf-8")
        every = ANY_USES.findall(text)
        pinned = USES.findall(text)
        assert len(every) == len(pinned), f"{path.name}: an action lacks a version comment"
        for ref, version in pinned:
            owner_repo, sha = ref.rsplit("@", 1)
            assert re.fullmatch(r"[0-9a-f]{40}", sha), f"{path.name}: {ref} is not SHA-pinned"
            assert "/" in owner_repo
            if "codeql-action" in owner_repo:
                assert re.fullmatch(r"v\d+\.\d+\.\d+", version), f"{path.name}: {ref} names {version}, not a release"


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
    assert doc["env"]["IMAGE"] == "docker.io/hybridcloudworks/img-ca-appliance-app"
    assert "${{ env.IMAGE }}:v${{ steps.version.outputs.version }}" in pushes[0]["with"]["tags"]
    assert 'echo "image_tag: v${VERSION}"' in text
    assert "vars.DOCKERHUB_ENABLED" in text and "DOCKERHUB_OIDC_CONNECTIONID" in text
    assert pushes[0]["if"].count("startsWith(github.ref, 'refs/tags/v')") == 1, "a branch dispatch never pushes"
    login = next(s for s in steps if "login-action" in s.get("uses", ""))
    assert "startsWith(github.ref, 'refs/tags/v')" in login["if"]


def test_ci_runs_every_section_20_check_that_can_run_in_ci():
    text = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    for needle in (
        "uv run ruff check .",
        "uv run ruff format --check .",
        "scripts/check-catalog.py",
        "scripts/check-docs-governance.py",
        "scripts/check-release-version.py",
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


def _steps(name: str) -> list[dict]:
    doc = yaml.safe_load((ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8"))
    return [step for job in doc["jobs"].values() for step in job["steps"]]


def test_the_release_version_guard_runs_before_anything_is_built_or_published():
    """CA-10 (ticket #33): a v* tag can never be moved or deleted, so every workflow a tag starts refuses a tag that
    does not match the version in the code, the lock, the changelog and main, before it builds or publishes."""
    guard = "scripts/check-release-version.py"
    assert (ROOT / guard).is_file()
    first_publishing = {
        "release.yml": "gh release create",
        "publish-core.yml": "uv build",
        "publish-images.yml": "docker/",
    }
    for name, publishing in first_publishing.items():
        text = (ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8")
        assert "--tag" in text and "--ancestor-of origin/main" in text and "fetch-depth: 0" in text, name
        rendered = [yaml.safe_dump(step) for step in _steps(name)]
        guarded = next(n for n, step in enumerate(rendered) if guard in step)
        publishes = next(n for n, step in enumerate(rendered) if publishing in step)
        assert guarded < publishes, f"{name}: the version guard must run before '{publishing}'"
    assert "--dist dist" in (ROOT / ".github" / "workflows" / "publish-core.yml").read_text(encoding="utf-8")
    assert "--notes-out" in (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    assert "uv run python " + guard in (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "uv run python " + guard in (ROOT / "Makefile").read_text(encoding="utf-8")


def test_release_creation_needs_the_check_job_and_only_it_holds_write_permission():
    doc = yaml.safe_load((ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8"))
    assert doc["jobs"]["create"]["needs"] == "check"
    assert "permissions" not in doc["jobs"]["check"]
    assert doc["jobs"]["create"]["permissions"] == {"contents": "write"}


def test_the_security_workflow_can_be_started_by_hand_without_changing_what_it_does_on_a_schedule():
    """CA-7 (ticket #30): the gitleaks job can be run on demand. The trigger takes no input, and the only job that
    depends on the event name is the pull-request-only dependency review, which a manual run skips."""
    doc = yaml.safe_load((ROOT / ".github" / "workflows" / "security.yml").read_text(encoding="utf-8"))
    triggers = doc.get("on", doc.get(True))  # PyYAML reads the bare key `on` as the boolean True
    assert set(triggers) == {"pull_request", "push", "schedule", "workflow_dispatch"}
    assert triggers["workflow_dispatch"] is None, "no inputs: a manual run must behave like the scheduled one"
    assert triggers["schedule"] == [{"cron": "23 6 * * 1"}]
    text = (ROOT / ".github" / "workflows" / "security.yml").read_text(encoding="utf-8")
    assert text.count("github.event_name") == 1
    assert doc["jobs"]["dependency-review"]["if"] == "github.event_name == 'pull_request'"
    assert "secret-scan" in doc["jobs"] and "gitleaks/gitleaks-action@" in text
