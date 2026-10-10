"""Live collectors. Every query is built from the ScopeAllowlist and nothing else; no caller can widen the scope."""

from cloud_assessor_appliance.collectors.scope import Scope, ScopeAllowlist, ScopeError

__all__ = ["Scope", "ScopeAllowlist", "ScopeError"]
