"""Client address resolution. The appliance parses no request body, so there is no body cap here."""

from __future__ import annotations

from fastapi import Request


def client_address(request: Request, trust_proxy: bool) -> str:
    """The socket peer, or with CA_TRUST_PROXY=1 the LAST X-Forwarded-For entry: proxies append, so the last value is
    the address the trusted proxy saw; earlier entries are client-supplied and never trusted."""
    if trust_proxy:
        forwarded = request.headers.get("x-forwarded-for", "")
        last = forwarded.rsplit(",", 1)[-1].strip()
        if last:
            return last[:64]
    return request.client.host if request.client else "unknown"
