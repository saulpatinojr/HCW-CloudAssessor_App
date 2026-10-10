"""One function per check kind: (resource | None, estate, check) -> Outcome. Pure; never raises on data."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from cloud_assessor_core.model import Check, Evidence, Resource, When
from cloud_assessor_core.paths import get_path

NO_PROPERTIES = "no properties column in the export"
NO_TAGS = "no tags column in the export"
NOT_IN_EXPORT = "property not present in the export"


@dataclass(frozen=True)
class Outcome:
    state: str  # observed | unknown
    result: str | None  # pass | fail | None
    evidence: Evidence
    reason: str


def observed(result: bool, path: str | None, observed_value: Any, expected: Any, reason: str) -> Outcome:
    return Outcome(
        "observed",
        "pass" if result else "fail",
        Evidence(path=path, observed=observed_value, expected=expected),
        reason,
    )


def unknown(path: str | None, expected: Any, reason: str) -> Outcome:
    return Outcome("unknown", None, Evidence(path=path, observed=None, expected=expected), reason)


def _missing(check: Check, path: str | None, expected: Any) -> Outcome:
    reason = check.unknownReason or NOT_IN_EXPORT
    if check.missingIs == "unknown":
        return unknown(path, expected, reason)
    return observed(check.missingIs == "pass", path, None, expected, reason)


def _norm(value: Any) -> Any:
    return value.strip().lower() if isinstance(value, str) else value


def _equal(a: Any, b: Any) -> bool:
    return _norm(a) == _norm(b)


def _resource_data(resource: Resource) -> dict[str, Any]:
    return {
        "id": resource.id,
        "name": resource.name,
        "type": resource.type,
        "location": resource.location,
        "resourceGroup": resource.resource_group,
        "subscriptionId": resource.subscription_id,
        "tags": resource.tags,
        "properties": resource.properties,
        "sku": resource.sku,
        "identity": resource.identity,
        "kind": resource.kind,
        "zones": resource.zones,
    }


def matches_when(resource: Resource, when: When | None) -> bool | None:
    """True / False when decidable, None when the path cannot be read from this export."""
    if when is None:
        return True
    if not _path_readable(resource, when.path):
        return None
    found = get_path(_resource_data(resource), when.path)
    if not found.found:
        return False
    values = [_norm(v) for v in found.values]
    if when.in_ is not None:
        wanted = {_norm(v) for v in when.in_}
        return any(v in wanted for v in values)
    return any(_equal(v, when.equals) for v in values)


PROPERTY_LIKE = frozenset({"properties", "sku", "identity", "kind", "zones"})


def _path_readable(resource: Resource, path: str) -> bool:
    """A portal "All resources" export carries no properties, sku, identity, kind or zones; tags may be absent too."""
    head = path.split(".", 1)[0].split("[", 1)[0].lower()
    if head in PROPERTY_LIKE and not resource.source.has_properties:
        return False
    return not (head == "tags" and not resource.source.has_tags)


def _read(resource: Resource, path: str) -> tuple[bool, list[Any]] | None:
    """None when the export cannot carry the path; else (found, values)."""
    if not _path_readable(resource, path):
        return None
    r = get_path(_resource_data(resource), path)
    return r.found, r.values


def _unreadable_reason(path: str) -> str:
    return NO_TAGS if path.split(".", 1)[0].lower() == "tags" else NO_PROPERTIES


def eval_tag_present(resource: Resource | None, estate: list[Resource], check: Check) -> Outcome:
    assert resource is not None
    keys = check.keys or []
    if not resource.source.has_tags:
        return unknown("tags", keys, NO_TAGS)
    tags = {k.lower(): v for k, v in resource.tags.items()}
    present = []
    for key_group in keys:
        alternatives = [k.strip().lower() for k in key_group.split("|")]
        present.append(any(tags.get(a, "").strip() != "" for a in alternatives))
    ok = all(present) if check.mode == "all" else any(present)
    missing = [k for k, p in zip(keys, present, strict=True) if not p]
    return observed(
        ok,
        "tags",
        sorted(tags.keys()),
        keys,
        "all required tags present" if ok else f"missing tags: {', '.join(missing)}",
    )


def eval_property_equals(resource: Resource | None, estate: list[Resource], check: Check) -> Outcome:
    assert resource is not None and check.path
    expected = check.anyOf if check.anyOf is not None else check.equals
    read = _read(resource, check.path)
    if read is None:
        return unknown(check.path, expected, _unreadable_reason(check.path))
    found, values = read
    if not found:
        return _missing(check, check.path, expected)
    if check.anyOf is not None:
        ok = all(any(_equal(v, e) for e in check.anyOf) for v in values)
    else:
        ok = all(_equal(v, check.equals) for v in values)
    shown = values[0] if len(values) == 1 else values
    return observed(ok, check.path, shown, expected, "value matches" if ok else "value does not match")


def eval_property_exists(resource: Resource | None, estate: list[Resource], check: Check) -> Outcome:
    assert resource is not None and check.path
    read = _read(resource, check.path)
    if read is None:
        return unknown(check.path, check.mustBe, _unreadable_reason(check.path))
    found, values = read
    non_empty = found and any(v not in (None, "", [], {}) for v in values)
    if check.mustBe == "present":
        ok = found
    elif check.mustBe == "absent":
        ok = not found
    else:
        ok = bool(non_empty)
    shown = (values[0] if len(values) == 1 else values) if found else None
    return observed(ok, check.path, shown, check.mustBe, f"path is {'present' if found else 'absent'}")


def eval_sku_in(resource: Resource | None, estate: list[Resource], check: Check) -> Outcome:
    assert resource is not None
    path = check.path or "sku.name"
    expected = {"allowed": check.allowed} if check.allowed is not None else {"disallowed": check.disallowed}
    read = _read(resource, path)
    if read is None:
        return unknown(path, expected, _unreadable_reason(path))
    found, values = read
    if not found or all(v in (None, "") for v in values):
        return _missing(check, path, expected)
    norm_values = {_norm(v) for v in values}
    if check.allowed is not None:
        allowed = {_norm(a) for a in check.allowed}
        ok = norm_values <= allowed
    else:
        disallowed = {_norm(d) for d in (check.disallowed or [])}
        ok = not (norm_values & disallowed)
    shown = values[0] if len(values) == 1 else values
    return observed(
        ok, path, shown, expected, "value is in the accepted set" if ok else "value is outside the accepted set"
    )


def _compare(actual: float, op: str, value: float) -> bool:
    return {
        ">=": actual >= value,
        "<=": actual <= value,
        ">": actual > value,
        "<": actual < value,
        "==": actual == value,
        "!=": actual != value,
    }[op]


def _to_number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return None
    return None


def eval_count_threshold(resource: Resource | None, estate: list[Resource], check: Check) -> Outcome:
    assert check.path and check.value is not None
    expected = f"{check.metric} {check.op} {check.value:g}"
    if check.scope == "estate":
        readable = [r for r in estate if _path_readable(r, check.path)]
        if not readable:
            return unknown(check.path, expected, _unreadable_reason(check.path))
        if check.metric == "percent-present":
            hits = sum(1 for r in readable if _non_empty(r, check.path))
            actual = 100.0 * hits / len(readable)
        elif check.metric == "count":
            actual = float(sum(1 for r in readable if get_path(_resource_data(r), check.path).found))
        else:
            numbers = [
                n
                for r in readable
                for n in (_to_number(v) for v in get_path(_resource_data(r), check.path).values)
                if n is not None
            ]
            if not numbers:
                return _missing(check, check.path, expected)
            actual = float(sum(numbers))
        ok = _compare(actual, check.op, check.value)
        return observed(ok, check.path, round(actual, 2), expected, f"{check.metric} over {len(readable)} resources")
    assert resource is not None
    read = _read(resource, check.path)
    if read is None:
        return unknown(check.path, expected, _unreadable_reason(check.path))
    found, values = read
    if check.metric == "count":
        actual = float(len(values)) if found else 0.0
    else:
        if not found:
            return _missing(check, check.path, expected)
        numbers = [n for n in (_to_number(v) for v in values) if n is not None]
        if not numbers:
            return _missing(check, check.path, expected)
        actual = numbers[0] if check.metric == "value" else 100.0
    ok = _compare(actual, check.op, check.value)
    return observed(ok, check.path, actual, expected, "within threshold" if ok else "outside threshold")


def _non_empty(resource: Resource, path: str) -> bool:
    r = get_path(_resource_data(resource), path)
    return r.found and any(v not in (None, "", [], {}) for v in r.values)


def _where(resource: Resource, where: When | None) -> bool:
    return matches_when(resource, where) is True if where else True


def eval_cross_resource(resource: Resource | None, estate: list[Resource], check: Check) -> Outcome:
    assert check.relation and check.type
    wanted = check.type.lower()
    candidates = [r for r in estate if r.type == wanted and _where(r, check.where)]
    if check.relation == "estate-has":
        matches = candidates
    else:
        assert resource is not None
        if check.relation == "has-child":
            prefix = resource.id.lower().rstrip("/") + "/"
            matches = [r for r in candidates if r.id.lower().startswith(prefix)]
        else:
            matches = [
                r
                for r in candidates
                if r.id != resource.id
                and (r.resource_group or "").lower() == (resource.resource_group or "").lower()
                and (r.subscription_id or "") == (resource.subscription_id or "")
            ]
    expected = f"{check.relation} {wanted}"
    if matches:
        return observed(True, "type", len(matches), expected, f"{len(matches)} matching resource(s) in the export")
    reason = check.unknownReason or f"no {wanted} in the export"
    if check.absentIs == "fail":
        return observed(False, "type", 0, expected, reason)
    return unknown("type", expected, reason)


Evaluator = Callable[[Resource | None, list[Resource], Check], Outcome]

EVALUATORS: dict[str, Evaluator] = {
    "tag-present": eval_tag_present,
    "property-equals": eval_property_equals,
    "property-exists": eval_property_exists,
    "sku-in": eval_sku_in,
    "count-threshold": eval_count_threshold,
    "cross-resource": eval_cross_resource,
}

ESTATE_TYPE = "estate"
ALL_TYPES = "*"


def is_estate_check(check: Check) -> bool:
    return (check.kind == "count-threshold" and check.scope == "estate") or (
        check.kind == "cross-resource" and check.relation == "estate-has"
    )
