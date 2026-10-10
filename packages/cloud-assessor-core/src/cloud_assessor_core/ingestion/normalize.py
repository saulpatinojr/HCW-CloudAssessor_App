"""Row normalisation into the Resource model, plus the shared helpers the two parsers use."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from pydantic import ValidationError

from cloud_assessor_core.model import Resource, SourceRef

DEFAULT_MAX_ROWS = 5_000
FORMULA_LEADERS = ("=", "+", "-", "@", "\t", "\r")

_ID_RG = re.compile(r"^/subscriptions/([^/]+)/resourcegroups/([^/]+)/", re.IGNORECASE)
_ID_SUB = re.compile(r"^/subscriptions/([^/]+)", re.IGNORECASE)


class IngestionError(ValueError):
    """The export cannot be read. `warnings` carry row numbers and column names, never cell content."""

    def __init__(self, message: str, warnings: list[str] | None = None) -> None:
        super().__init__(message)
        self.warnings = warnings or []


@dataclass
class ParsedRows:
    rows: list[dict[str, Any]]
    warnings: list[str] = field(default_factory=list)
    has_properties: bool = True
    has_tags: bool = True


def neutralise_formula(value: str) -> str:
    """Prefix a leading formula character with a quote so spreadsheet clients treat the cell as text."""
    if value and value[0] in FORMULA_LEADERS:
        return "'" + value
    return value


def strip_bom(text: str) -> str:
    return text[1:] if text.startswith("﻿") else text


def _as_str_dict(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    return {str(k): ("" if v is None else str(v)) for k, v in value.items()}


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_opt_dict(value: Any) -> dict[str, Any] | None:
    return value if isinstance(value, dict) else None


def _as_opt_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def normalize(parsed: ParsedRows, fmt: str) -> tuple[list[Resource], list[str]]:
    """Turn parsed rows into Resources. Lower-cases `type`, derives ids and groups, records synthetic ids."""
    resources: list[Resource] = []
    warnings = list(parsed.warnings)
    synthetic = 0
    for index, row in enumerate(parsed.rows, start=1):
        rtype = _as_opt_str(row.get("type"))
        if not rtype:
            warnings.append(f"row {index}: missing type; skipped")
            continue
        rtype = rtype.lower()
        rid = _as_opt_str(row.get("id"))
        name = _as_opt_str(row.get("name"))
        rg = _as_opt_str(row.get("resourceGroup"))
        sub = _as_opt_str(row.get("subscriptionId"))
        if rid:
            m = _ID_RG.match(rid)
            if m:
                sub = sub or m.group(1)
                rg = rg or m.group(2)
            else:
                m2 = _ID_SUB.match(rid)
                if m2:
                    sub = sub or m2.group(1)
            if not name:
                name = rid.rstrip("/").rsplit("/", 1)[-1]
        else:
            if not name:
                warnings.append(f"row {index}: missing id and name; skipped")
                continue
            rid = f"/subscriptions/{sub or 'unknown'}/resourceGroups/{rg or 'unknown'}/providers/{rtype}/{name}"
            synthetic += 1
        zones_raw = row.get("zones")
        zones = [str(z) for z in zones_raw] if isinstance(zones_raw, list) else None
        try:
            resources.append(
                Resource(
                    id=rid,
                    name=name,
                    type=rtype,
                    location=_as_opt_str(row.get("location")),
                    resource_group=rg,
                    subscription_id=sub,
                    tags=_as_str_dict(row.get("tags")),
                    properties=_as_dict(row.get("properties")),
                    sku=_as_opt_dict(row.get("sku")),
                    identity=_as_opt_dict(row.get("identity")),
                    kind=_as_opt_str(row.get("kind")),
                    zones=zones,
                    source=SourceRef(
                        format=fmt,  # type: ignore[arg-type]
                        row=index,
                        has_properties=parsed.has_properties,
                        has_tags=parsed.has_tags,
                    ),
                )
            )
        except ValidationError as exc:  # pragma: no cover - defensive; the coercions above make this unreachable
            warnings.append(f"row {index}: could not be normalised ({exc.error_count()} field errors); skipped")
    if synthetic:
        warnings.append(
            f"synthetic-id: {synthetic} rows had no id; one was derived from subscription, group, type and name"
        )
    if not resources:
        raise IngestionError("no usable rows: every row lacks a type", warnings)
    return resources, warnings
