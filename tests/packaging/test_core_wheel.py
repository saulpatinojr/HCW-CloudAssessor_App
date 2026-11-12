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
    assert wheel.name.startswith("cloud_assessor_core-0.3.2-")
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
    assert requires == ["pydantic<3,>=2.14"]


def test_wheel_requires_python_315(wheel):
    """The wheel's Requires-Python admits every 3.15 release and nothing from 3.16 on. The AddOn installs the
    released wheel with `pip install --require-hashes --no-deps` on the website's Python 3.15 base (its own floor is
    3.15.1); pip refuses a wheel whose range excludes the interpreter, so a `<3.15` ceiling once blocked that image
    before any code ran. The floor moved from 3.14.6 to 3.15.0, the HCW floor, in HCW-HybridCloudWorks#1707: this
    repository's CI and image no longer run 3.14, so the wheel no longer claims it."""
    z = zipfile.ZipFile(wheel)
    metadata = next(n for n in z.namelist() if n.endswith("METADATA"))
    line = re.search(r"^Requires-Python: (.+)$", z.read(metadata).decode("utf-8"), re.MULTILINE)
    assert line is not None, "the wheel declares no Requires-Python"
    assert {part.strip() for part in line.group(1).split(",")} == {">=3.15.0", "<3.16"}
