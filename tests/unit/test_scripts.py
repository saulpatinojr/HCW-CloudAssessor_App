"""Each repository script exits non-zero on a deliberately broken input (REFACTOR_APP.md 7.15)."""

import shutil
import subprocess
import sys

from ..conftest import ROOT

SCRIPTS = ROOT / "scripts"


def _run(*args, cwd=ROOT):
    return subprocess.run(list(args), cwd=cwd, capture_output=True, text=True, timeout=120)


def test_check_docs_governance_passes_here_and_fails_on_a_stray_markdown(tmp_path):
    ok = _run(sys.executable, str(SCRIPTS / "check-docs-governance.py"))
    assert ok.returncode == 0, ok.stderr
    tree = tmp_path / "repo"
    tree.mkdir()
    for name in ("README.md", "CHANGELOG.md", "REVIEW.md", "TODO.md", "REFACTOR_APP.md"):
        (tree / name).write_text("# x\n[ok](README.md)\n", encoding="utf-8")
    assert _run(sys.executable, str(SCRIPTS / "check-docs-governance.py"), "--root", str(tree)).returncode == 0
    (tree / "docs").mkdir()
    (tree / "docs" / "design.md").write_text("# stray\n", encoding="utf-8")
    bad = _run(sys.executable, str(SCRIPTS / "check-docs-governance.py"), "--root", str(tree))
    assert bad.returncode == 1 and "docs/design.md" in bad.stderr and "wiki" in bad.stderr
    (tree / "docs" / "design.md").unlink()
    (tree / "README.md").write_text("[broken](nope.md)\n", encoding="utf-8")
    bad = _run(sys.executable, str(SCRIPTS / "check-docs-governance.py"), "--root", str(tree))
    assert bad.returncode == 1 and "nope.md" in bad.stderr
    (tree / "REFACTOR_APP.md").unlink()
    (tree / "README.md").write_text("# x\n", encoding="utf-8")
    assert _run(sys.executable, str(SCRIPTS / "check-docs-governance.py"), "--root", str(tree)).returncode == 0


def test_check_versions_passes_here_and_fails_on_drift(tmp_path):
    assert _run("bash", str(SCRIPTS / "check-versions.sh")).returncode == 0
    dockerfile = tmp_path / "Dockerfile"
    versions = ROOT / "infrastructure" / "docker" / "versions.env"
    dockerfile.write_text("FROM python:3.14.7-slim-trixie@sha256:" + "0" * 64 + " AS build\nFROM build AS lab\n")
    bad = _run("bash", str(SCRIPTS / "check-versions.sh"), str(dockerfile), str(versions))
    assert bad.returncode == 1 and "neither an earlier stage" in bad.stdout + bad.stderr
    broken = tmp_path / "versions.env"
    broken.write_text("PYTHON_IMAGE=python:3.14.7-slim-trixie\nPYTHON_IMAGE_DIGEST=latest\n")
    bad = _run("bash", str(SCRIPTS / "check-versions.sh"), str(ROOT / "infrastructure/docker/Dockerfile"), str(broken))
    assert bad.returncode == 1


def test_check_lockfiles_passes_here_and_fails_on_drift(tmp_path):
    if shutil.which("uv") is None:
        import pytest

        pytest.skip("uv not on PATH")
    assert _run("bash", str(SCRIPTS / "check-lockfiles.sh")).returncode == 0
    copy = tmp_path / "repo"
    shutil.copytree(ROOT, copy, ignore=shutil.ignore_patterns(".venv", ".git", "__pycache__", ".pytest_cache"))
    (copy / "requirements.lock.txt").write_text("fastapi==0.0.1\n", encoding="utf-8")
    bad = _run("bash", str(copy / "scripts" / "check-lockfiles.sh"), cwd=copy)
    assert bad.returncode != 0


def test_check_catalog_fails_on_a_bad_learn_url(tmp_path, monkeypatch):
    import json

    copy = tmp_path / "repo"
    shutil.copytree(ROOT / "scripts", copy / "scripts")
    shutil.copytree(ROOT / "packages", copy / "packages", ignore=shutil.ignore_patterns("__pycache__"))
    path = copy / "packages" / "cloud-assessor-core" / "catalog" / "criteria.json"
    doc = json.loads(path.read_text(encoding="utf-8"))
    doc["criteria"][0]["id"] = "CA-ZT-000"  # breaks the sort order
    path.write_text(json.dumps(doc), encoding="utf-8")
    bad = _run(sys.executable, str(copy / "scripts" / "check-catalog.py"), cwd=copy)
    assert bad.returncode == 1 and "not sorted" in bad.stderr
