"""The appliance edition: live, read-only, managed identity only. Refuses to start unless it can do its job safely.

The lab edition's guard (refusal under an identity endpoint, no cloud SDK importable) lives in the AddOn's
`src/cloud_assessment_lab/edition.py`; this repository ships no lab application, only the `lab` boundary-proof
Docker target (infrastructure/docker/Dockerfile).
"""

from __future__ import annotations

import importlib.util
import os
from collections.abc import Callable, Mapping

from cloud_assessor_appliance.collectors.scope import ScopeAllowlist, ScopeError
from cloud_assessor_appliance.identity import IdentityError, refuse_forbidden_env

EDITION = "appliance"
AZURE_CONNECTIVITY = "managed-identity"
CAPABILITIES = (
    "scorecard",
    "findings",
    "report-markdown",
    "report-json",
    "bundle-zip",
    "live-resource-graph",
    "live-cost",
)
REQUIRED_MODULES = ("azure.identity", "azure.mgmt.resourcegraph", "azure.mgmt.costmanagement")


class EditionError(RuntimeError):
    """Raised when the appliance cannot start as the appliance edition."""


def _find_spec(name: str):
    try:
        return importlib.util.find_spec(name)
    except ImportError, ValueError:
        return None


def assert_appliance_ready(
    env: Mapping[str, str] | None = None, *, find_spec: Callable[[str], object | None] = _find_spec
) -> ScopeAllowlist:
    """The `azure` extra is importable, no client-secret variable is present, and CA_SCOPES parses. Fail closed."""
    env = os.environ if env is None else env
    missing = [m for m in REQUIRED_MODULES if find_spec(m) is None]
    if missing:
        raise EditionError(
            "azure extra not installed (install with `uv sync --extra azure`); missing: " + ", ".join(missing)
        )
    try:
        refuse_forbidden_env(env)
    except IdentityError as exc:
        raise EditionError(str(exc)) from None
    try:
        return ScopeAllowlist.from_env(env)
    except ScopeError as exc:
        raise EditionError(f"CA_SCOPES: {exc}") from None
