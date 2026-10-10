"""The built cloud-assessor-core wheel carries the catalog, imports nothing under azure and names no Azure endpoint."""

import re
import shutil
import subprocess
import zipfile

import pytest

from ..conftest import ROOT

ENDPOINTS = ("management.azure.com", "login.microsoftonline.com", "graph.microsoft.com")


@pytest.fixture(scope="module")
def wheel(tmp_path_factory):
    if shutil.which("uv") is None:
        pytest.skip("uv not on PATH")
    out = tmp_path_factory.mktemp("dist")
    proc = subprocess.run(
        ["uv", "build", "--package", "cloud-assessor-core", "--wheel", "--out-dir", str(out)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=600,
    )
    assert proc.returncode == 0, proc.stderr
    wheels = list(out.glob("cloud_assessor_core-*.whl"))
    assert len(wheels) == 1
    return wheels[0]


def test_wheel_name_version_and_catalog(wheel):
    assert wheel.name.startswith("cloud_assessor_core-0.2.0-")
    names = zipfile.ZipFile(wheel).namelist()
    for name in ("criteria.json", "schema.json", "scoring.json"):
        assert f"cloud_assessor_core/catalog_data/{name}" in names
    assert not any("tests/" in n for n in names)


def test_wheel_imports_no_cloud_sdk_and_names_no_endpoint(wheel):
    z = zipfile.ZipFile(wheel)
    for name in z.namelist():
        if not name.endswith(".py"):
            continue
        text = z.read(name).decode("utf-8")
        assert not re.search(r"^\s*(import|from)\s+(azure|msal|boto3|msrest)\b", text, re.MULTILINE), name
        for ep in ENDPOINTS:
            assert ep not in text, f"{name} references {ep}"
    metadata = next(n for n in z.namelist() if n.endswith("METADATA"))
    requires = re.findall(r"^Requires-Dist: (.+)$", z.read(metadata).decode("utf-8"), re.MULTILINE)
    assert requires == ["pydantic==2.14.0"]
