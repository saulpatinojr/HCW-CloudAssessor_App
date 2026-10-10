"""One credential factory; managed identity only. A client-secret shaped environment is a startup error, not a fallback.

`DefaultAzureCredential` is kept only for local runs under `az login` (no AZURE_CLIENT_ID set);
`ManagedIdentityCredential` is the production path. Credential objects are never logged; every exception message that
leaves this module is scrubbed.
"""

from __future__ import annotations

import os
import re
from collections.abc import Callable, Mapping
from typing import Any

from cloud_assessor_core.redaction import scrub

# AZURE_TENANT_ID is refused on purpose: ManagedIdentityCredential needs only the client id, and a tenant id in the
# environment is the signature of a service-principal login (REFACTOR_APP.md sections 7.4 and 10).
FORBIDDEN_ENV = (
    "AZURE_CLIENT_SECRET",
    "AZURE_CLIENT_CERTIFICATE_PATH",
    "AZURE_USERNAME",
    "AZURE_PASSWORD",
    "AZURE_TENANT_ID",
)
_GUID = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")


class IdentityError(RuntimeError):
    """Raised when the environment describes anything other than a managed identity or a local `az login` session."""


def refuse_forbidden_env(env: Mapping[str, str]) -> None:
    present = [k for k in FORBIDDEN_ENV if env.get(k, "").strip()]
    if present:
        raise IdentityError(f"client-secret style variables are refused: {','.join(present)}")


def client_id_from(env: Mapping[str, str]) -> str | None:
    client_id = env.get("AZURE_CLIENT_ID", "").strip() or None
    if client_id is not None and not _GUID.match(client_id):
        raise IdentityError("AZURE_CLIENT_ID must be the client id (GUID) of the user-assigned managed identity")
    return client_id


def build_credential(
    env: Mapping[str, str] | None = None,
    *,
    managed_identity: Callable[..., Any] | None = None,
    default: Callable[..., Any] | None = None,
) -> Any:
    """ManagedIdentityCredential(client_id=AZURE_CLIENT_ID) when the id is set; else a narrowed DefaultAzureCredential.

    The two factories are injectable so the selection is unit-tested without the SDK; production leaves them None and
    the classes are imported from azure.identity (the `azure` extra).
    """
    env = os.environ if env is None else env
    refuse_forbidden_env(env)
    client_id = client_id_from(env)
    if managed_identity is None or default is None:
        try:
            from azure.identity import DefaultAzureCredential, ManagedIdentityCredential
        except ImportError:
            raise IdentityError("the azure extra is not installed; run `uv sync --extra azure`") from None
        managed_identity = managed_identity or ManagedIdentityCredential
        default = default or DefaultAzureCredential
    try:
        if client_id:
            return managed_identity(client_id=client_id)
        return default(exclude_interactive_browser_credential=True, exclude_environment_credential=True)
    except Exception as exc:  # noqa: BLE001 - the SDK's message may carry ids; scrub before it leaves this module
        raise IdentityError(f"credential could not be built: {scrub(f'{type(exc).__name__}: {exc}')}") from None
