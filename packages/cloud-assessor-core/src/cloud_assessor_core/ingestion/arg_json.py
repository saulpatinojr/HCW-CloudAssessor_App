"""`arg-json`: a bare JSON array of Resource Graph rows, or the `az graph query` envelope."""

from __future__ import annotations

import json
from typing import Any

from cloud_assessor_core.ingestion.normalize import DEFAULT_MAX_ROWS, IngestionError, ParsedRows, strip_bom

PAGED_WARNING = "export is paged; only the first page was uploaded"


class TooManyRows(IngestionError):
    def __init__(self, count: int, max_rows: int) -> None:
        super().__init__(f"export has {count} rows; the limit is {max_rows}")
        self.count = count
        self.max_rows = max_rows


def rows_from_document(document: Any) -> tuple[list[Any], list[str]]:
    """Accept a bare array or the envelope. Anything else is an ingestion error with no content echoed."""
    warnings: list[str] = []
    if isinstance(document, list):
        return document, warnings
    if isinstance(document, dict):
        data = document.get("data")
        if isinstance(data, list):
            if document.get("skip_token") not in (None, ""):
                warnings.append(PAGED_WARNING)
            total = document.get("total_records")
            if isinstance(total, int) and total > len(data):
                warnings.append(f"export reports {total} records; {len(data)} were uploaded")
            return data, warnings
        raise IngestionError("JSON object is not an az graph query envelope (no data array)")
    raise IngestionError("JSON document is neither an array nor an envelope")


def parse_arg_json(text: str, *, max_rows: int = DEFAULT_MAX_ROWS) -> ParsedRows:
    text = strip_bom(text)
    try:
        document = json.loads(text)
    except json.JSONDecodeError as exc:
        raise IngestionError(f"invalid JSON at line {exc.lineno}, column {exc.colno}") from None
    return parse_arg_document(document, max_rows=max_rows)


def parse_arg_document(document: Any, *, max_rows: int = DEFAULT_MAX_ROWS) -> ParsedRows:
    raw_rows, warnings = rows_from_document(document)
    if len(raw_rows) > max_rows:
        raise TooManyRows(len(raw_rows), max_rows)
    rows: list[dict[str, Any]] = []
    for index, row in enumerate(raw_rows, start=1):
        if not isinstance(row, dict):
            warnings.append(f"row {index}: not an object; skipped")
            continue
        rows.append(row)
    if not rows:
        raise IngestionError("export contains no rows", warnings)
    has_properties = any("properties" in r for r in rows)
    has_tags = any("tags" in r for r in rows)
    if not has_properties:
        warnings.append("no properties column: criteria that read properties cannot be assessed from this file")
    return ParsedRows(rows=rows, warnings=warnings, has_properties=has_properties, has_tags=has_tags)
