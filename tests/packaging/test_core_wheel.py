"""The built cloud-assessor-core wheel carries the catalog and the licence text, imports nothing under azure and names
no Azure endpoint."""

import re
import shutil
import subprocess
import tarfile
import zipfile

import pytest

from ..conftest import ROOT

ENDPOINTS = ("management.azure.com", "login.microsoftonline.com", "graph.microsoft.com")


@pytest.fixture(scope="module")
def dist(tmp_path_factory):
    """Build as publish-core.yml does: the sdist first, then the wheel from that sdist."""
    if shutil.which("uv") is None:
        pytest.skip("uv not on PATH")
    out = tmp_path_factory.mktemp("dist")
    proc = subprocess.run(
        ["uv", "build", "--no-create-gitignore", "--package", "cloud-assessor-core", "--out-dir", str(out)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=600,
    )
    assert proc.returncode == 0, proc.stderr
    return out


@pytest.fixture(scope="module")
def wheel(dist):
    wheels = list(dist.glob("cloud_assessor_core-*.whl"))
    assert len(wheels) == 1
    return wheels[0]


@pytest.fixture(scope="module")
def sdist(dist):
    sdists = list(dist.glob("cloud_assessor_core-*.tar.gz"))
    assert len(sdists) == 1
    return sdists[0]


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
    """The wheel's Requires-Python admits 3.15.2 and every later 3.15 release, and nothing from 3.16 on. The AddOn
    installs the released wheel with `pip install --require-hashes --no-deps` on the website's Python 3.15.2 base (its
    own floor is 3.15.2 too); pip refuses a wheel whose range excludes the interpreter, so a `<3.15` ceiling once
    blocked that image before any code ran. The floor moved from 3.14.6 to 3.15.0 in HCW-HybridCloudWorks#1707, and
    to 3.15.2, the latest 3.15 release, by the owner's decision of 2026-11-14."""
    z = zipfile.ZipFile(wheel)
    metadata = next(n for n in z.namelist() if n.endswith("METADATA"))
    line = re.search(r"^Requires-Python: (.+)$", z.read(metadata).decode("utf-8"), re.MULTILINE)
    assert line is not None, "the wheel declares no Requires-Python"
    assert {part.strip() for part in line.group(1).split(",")} == {">=3.15.2", "<3.16"}


def test_package_licence_is_a_copy_of_the_root_licence():
    """license-files cannot point outside the package folder, so the package keeps a copy of the root LICENSE."""
    assert (ROOT / "packages/cloud-assessor-core/LICENSE").read_bytes() == (ROOT / "LICENSE").read_bytes()


def test_wheel_ships_the_licence_text(wheel):
    """MIT asks that the copyright and permission notice travel with every copy. Up to 0.3.2 the wheel declared
    License-Expression: MIT but carried no LICENSE, so the AddOn image installed the engine without the text. PEP 639
    puts it under .dist-info/licenses/ and names it in a License-File line of METADATA."""
    z = zipfile.ZipFile(wheel)
    names = z.namelist()
    dist_info = next(n.split("/", 1)[0] for n in names if n.endswith(".dist-info/METADATA"))
    metadata = z.read(f"{dist_info}/METADATA").decode("utf-8").splitlines()
    assert "License-Expression: MIT" in metadata
    assert "License-File: LICENSE" in metadata
    assert f"{dist_info}/licenses/LICENSE," in z.read(f"{dist_info}/RECORD").decode("utf-8")
    assert z.read(f"{dist_info}/licenses/LICENSE") == (ROOT / "LICENSE").read_bytes()


def test_sdist_ships_the_licence_text(sdist):
    """The release attaches the sdist beside the wheel (publish-core.yml), so it carries LICENSE too, named in
    PKG-INFO."""
    with tarfile.open(sdist) as tf:
        top = tf.getnames()[0].split("/", 1)[0]
        pkg_info = tf.extractfile(f"{top}/PKG-INFO").read().decode("utf-8").splitlines()
        shipped = tf.extractfile(f"{top}/LICENSE").read()
    assert "License-Expression: MIT" in pkg_info
    assert "License-File: LICENSE" in pkg_info
    assert shipped == (ROOT / "LICENSE").read_bytes()
