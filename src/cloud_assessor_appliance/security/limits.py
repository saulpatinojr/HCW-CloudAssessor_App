"""Client address resolution. The appliance parses no request body, so there is no body cap here."""

from __future__ import annotations

from fastapi import Request


def client_address(request: Request, trust_proxy: bool) -> str:
    if trust_proxy:
        forwarded = request.headers.get("x-forwarded-for", "")
        first = forwarded.split(",")[0].strip()
        if first:
            return first[:64]
    return request.client.host if request.client else "unknown"
