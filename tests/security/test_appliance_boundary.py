"""The boundary in both directions (REFACTOR_APP.md 7.12, 13): the core carries no cloud SDK and the default
dependency set cannot reach Azure; the appliance has no upload path and no client-secret credential."""

import ast
import re

from fastapi.testclient import TestClient

from cloud_assessor_appliance.api import api_routes
from cloud_assessor_appliance.identity import FORBIDDEN_ENV

from ..conftest import ROOT, make_app

FORBIDDEN_MODULES = ("azure", "msal", "boto3", "botocore", "msrest")
FORBIDDEN_ENDPOINTS = ("management.azure.com", "login.microsoftonline.com", "graph.microsoft.com")
CORE = ROOT / "packages" / "cloud-assessor-core"


def test_core_manifest_and_default_lock_have_no_cloud_sdk():
    core = (CORE / "pyproject.toml").read_text(encoding="utf-8")
    assert re.findall(r'^\s*"([a-z0-9-]+)[<>=!~]', core, re.MULTILINE) == ["pydantic"]
    for name in ("requirements.lock.txt",):
        text = (ROOT / name).read_text(encoding="utf-8")
        for pkg in ("azure-", "msal", "msrest", "boto3", "botocore"):
            assert not re.search(rf"^{pkg}[\w-]*==", text, re.MULTILINE), f"{name} pins {pkg}"
    root = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    deps = root.split("[project.optional-dependencies]")[0]
    assert "azure" not in deps.split("dependencies = [")[1].split("]")[0]
    assert "azure-identity==" in root.split("[project.optional-dependencies]")[1].split("[dependency-groups]")[0]


def test_no_cloud_sdk_import_in_the_core_or_the_scripts():
    for base in (CORE / "src", ROOT / "scripts"):
        for path in base.rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                names = []
                if isinstance(node, ast.Import):
                    names = [a.name for a in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module:
                    names = [node.module]
                for name in names:
                    assert name.split(".")[0] not in FORBIDDEN_MODULES, f"{path} imports {name}"


def test_cloud_sdk_imports_in_the_appliance_are_lazy_and_confined():
    """Module-level imports stay SDK-free so the package imports (and refuses to start) without the extra."""
    allowed_files = {"identity.py", "resource_graph.py", "cost_management.py"}
    for path in (ROOT / "src" / "cloud_assessor_appliance").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in tree.body:  # top level only
            names = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            for name in names:
                assert name.split(".")[0] not in FORBIDDEN_MODULES, f"{path} imports {name} at module level"
        text = path.read_text(encoding="utf-8")
        if re.search(r"^\s+from azure", text, re.MULTILINE):
            assert path.name in allowed_files, f"{path} touches the SDK"


def test_no_azure_endpoint_strings_in_code_or_pane():
    for base in (ROOT / "packages", ROOT / "src"):
        for path in base.rglob("*"):
            if path.is_file() and path.suffix in {".py", ".js", ".html", ".css", ".json"}:
                text = path.read_text(encoding="utf-8", errors="ignore")
                for endpoint in FORBIDDEN_ENDPOINTS:
                    assert endpoint not in text, f"{path} references {endpoint}"


def test_no_client_secret_credential_anywhere():
    for base in (ROOT / "src", ROOT / "packages", ROOT / "infrastructure"):
        for path in base.rglob("*"):
            if path.is_file() and path.suffix in {".py", ".tf", "", ".env"} and ".venv" not in path.parts:
                text = path.read_text(encoding="utf-8", errors="ignore")
                for needle in ("ClientSecretCredential", "CertificateCredential", "UsernamePasswordCredential"):
                    assert needle not in text, f"{path} mentions {needle}"
                if path.suffix == ".tf":
                    assert "client_secret" not in text.lower() and "secret {" not in text
    assert set(FORBIDDEN_ENV) == {
        "AZURE_CLIENT_SECRET",
        "AZURE_CLIENT_CERTIFICATE_PATH",
        "AZURE_USERNAME",
        "AZURE_PASSWORD",
        "AZURE_TENANT_ID",
    }


def test_create_app_registers_no_upload_handler():
    app = make_app()
    table = api_routes(app)
    assert table["/api/assessments"] == {"POST", "PUT", "PATCH", "DELETE"}
    with TestClient(app) as c:
        r = c.post("/api/assessments", content=b'{"format":"arg-json","content":"[]"}')
        assert r.status_code == 405 and r.json()["error"]["code"] == "edition_readonly"
    source = (ROOT / "src" / "cloud_assessor_appliance" / "api.py").read_text(encoding="utf-8")
    assert "multipart" not in source and "request.stream()" not in source and "await request.body()" not in source
    assert "x-owner-token" not in source and "owner_token" not in source


def test_dockerfile_lab_stage_installs_no_azure_and_appliance_does():
    text = (ROOT / "infrastructure" / "docker" / "Dockerfile").read_text(encoding="utf-8")
    stages = re.split(r"^FROM ", text, flags=re.MULTILINE)[1:]
    by_name = {}
    for stage in stages:
        name = re.search(r"\bAS (\S+)", stage.split("\n", 1)[0]).group(1)
        by_name[name] = stage
    assert set(by_name) == {"deps", "deps-azure", "lab", "appliance"}
    assert "requirements-azure.lock.txt" not in by_name["lab"] and "requirements-azure.lock.txt" not in by_name["deps"]
    assert "COPY --from=deps /install" in by_name["lab"] and "COPY --from=deps-azure /install" in by_name["appliance"]
    assert "requirements-azure.lock.txt" in by_name["deps-azure"]
    assert "HEALTHCHECK" not in by_name["lab"] and "HEALTHCHECK" in by_name["appliance"]
    code_lines = [line.split("#", 1)[0] for line in text.splitlines()]
    assert not any("cloud_assessment_lab" in line for line in code_lines), "no lab application is copied"
    assert "find_spec('azure') is None" in by_name["lab"]
    for stage in by_name.values():
        assert "USER 10001:10001" in stage or stage.startswith("python") and "pip install" in stage
        for line in stage.splitlines():
            code = line.split("#", 1)[0]
            assert "pip install" not in code or "--require-hashes" in code, line
