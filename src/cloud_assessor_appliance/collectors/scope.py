"""The parsed allow-list of scopes the appliance may read (REFACTOR_APP.md 7.5, T-027 scope half).

Entries are `/subscriptions/<guid>` or `/subscriptions/<guid>/resourceGroups/<name>`, comma or space separated, from
CA_SCOPES. No management-group traversal in v1. Enforced before any query (kql_filter) and on every resource id that
comes back (assert_contains).
"""

from __future__ import annotations

import os
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

_GUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
# Azure resource-group names: 1-90 characters of letters, digits, underscore, hyphen, period and parentheses, not
# ending with a period. Validated so the value can be placed in a KQL string literal without escaping.
_RG_NAME = re.compile(r"^(?=.{1,90}$)[\w.()-]*[\w()-]$")
_ENTRY = re.compile(r"^/subscriptions/(?P<sub>[^/]+)(?:/resourcegroups/(?P<rg>[^/]+))?/?$", re.IGNORECASE)
_RESOURCE_ID = re.compile(r"^/subscriptions/(?P<sub>[^/]+)(?:/resourcegroups/(?P<rg>[^/]+))?(?:/|$)", re.IGNORECASE)


class ScopeError(ValueError):
    """CA_SCOPES is missing, empty or malformed, or a resource lies outside the allow-list."""


@dataclass(frozen=True)
class Scope:
    subscription_id: str
    resource_group: str | None = None

    @property
    def id(self) -> str:
        if self.resource_group is None:
            return f"/subscriptions/{self.subscription_id}"
        return f"/subscriptions/{self.subscription_id}/resourceGroups/{self.resource_group}"


def _parse_entry(raw: str) -> Scope:
    m = _ENTRY.match(raw.strip())
    if m is None:
        raise ScopeError("entries must be /subscriptions/<guid> or /subscriptions/<guid>/resourceGroups/<name>")
    sub = m.group("sub").lower()
    if not _GUID.match(sub):
        raise ScopeError("the subscription id is not a GUID")
    rg = m.group("rg")
    if rg is not None and not _RG_NAME.match(rg):
        raise ScopeError("the resource group name is not valid")
    return Scope(sub, rg)


class ScopeAllowlist:
    __slots__ = ("_rg_scopes", "_scopes", "_subs")

    def __init__(self, scopes: Iterable[Scope]) -> None:
        ordered = list(dict.fromkeys(scopes))
        if not ordered:
            raise ScopeError("at least one scope is required")
        self._scopes: tuple[Scope, ...] = tuple(ordered)
        self._subs: frozenset[str] = frozenset(s.subscription_id for s in ordered if s.resource_group is None)
        self._rg_scopes: frozenset[tuple[str, str]] = frozenset(
            (s.subscription_id, s.resource_group.lower()) for s in ordered if s.resource_group is not None
        )

    @classmethod
    def parse(cls, value: str) -> ScopeAllowlist:
        """Parses the raw value, e.g. "/subscriptions/<guid>,/subscriptions/<guid>/resourceGroups/rg-app"."""
        parts = [p for p in value.replace(",", " ").split() if p]
        if not parts:
            raise ScopeError("CA_SCOPES is missing or empty")
        return cls(_parse_entry(p) for p in parts)

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> ScopeAllowlist:
        env = os.environ if env is None else env
        return cls.parse(env.get("CA_SCOPES", ""))  # the only place the key name CA_SCOPES is spelled

    @property
    def scopes(self) -> tuple[Scope, ...]:
        return self._scopes

    def subscriptions(self) -> list[str]:
        return sorted({s.subscription_id for s in self._scopes})

    def kql_filter(self) -> str:
        """`subscriptionId in~ ('...')` plus, when a resource-group entry exists, per-scope `resourceGroup =~` terms."""
        subs = ", ".join(f"'{s}'" for s in self.subscriptions())
        clause = f"subscriptionId in~ ({subs})"
        if not self._rg_scopes:
            return clause
        terms = []
        for scope in self._scopes:
            if scope.resource_group is None:
                terms.append(f"subscriptionId =~ '{scope.subscription_id}'")
            else:
                terms.append(
                    f"(subscriptionId =~ '{scope.subscription_id}' and resourceGroup =~ '{scope.resource_group}')"
                )
        return clause + " and (" + " or ".join(terms) + ")"

    def contains(self, resource_id: str) -> bool:
        m = _RESOURCE_ID.match(resource_id or "")
        if m is None:
            return False
        sub = m.group("sub").lower()
        if sub in self._subs:
            return True
        rg = m.group("rg")
        return rg is not None and (sub, rg.lower()) in self._rg_scopes

    def assert_contains(self, resource_id: str) -> None:
        if not self.contains(resource_id):
            raise ScopeError("a returned resource lies outside the configured scope")
