"""`arg-csv`: Resource Graph Explorer "Download as CSV" (JSON cells), or the portal "All resources" export."""

from __future__ import annotations

import csv
import io
import json
from typing import Any

from cloud_assessor_core.ingestion.arg_json import TooManyRows
from cloud_assessor_core.ingestion.normalize import (
    DEFAULT_MAX_ROWS,
    IngestionError,
    ParsedRows,
    neutralise_formula,
    strip_bom,
)

NO_PROPERTIES_WARNING = "no properties column"

HEADER_ALIASES: dict[str, str] = {
    "id": "id",
    "resourceid": "id",
    "name": "name",
    "type": "type",
    "resourcetype": "type",
    "location": "location",
    "region": "location",
    "resourcegroup": "resourceGroup",
    "resource group": "resourceGroup",
    "subscriptionid": "subscriptionId",
    "subscription": "subscriptionId",
    "subscription id": "subscriptionId",
    "tags": "tags",
    "properties": "properties",
    "sku": "sku",
    "identity": "identity",
    "kind": "kind",
    "zones": "zones",
}
JSON_COLUMNS = ("tags", "properties", "sku", "identity", "zones")

# The portal's "All resources" export writes display names in TYPE. The ones the catalog covers are mapped so the
# rows reach the right criteria (and come back `unknown` for lack of properties, honestly).
PORTAL_TYPE_NAMES: dict[str, str] = {
    "kubernetes service": "microsoft.containerservice/managedclusters",
    "container app": "microsoft.app/containerapps",
    "container apps environment": "microsoft.app/managedenvironments",
    "container registry": "microsoft.containerregistry/registries",
    "key vault": "microsoft.keyvault/vaults",
    "storage account": "microsoft.storage/storageaccounts",
    "disk": "microsoft.compute/disks",
    "public ip address": "microsoft.network/publicipaddresses",
    "log analytics workspace": "microsoft.operationalinsights/workspaces",
    "virtual machine": "microsoft.compute/virtualmachines",
    "virtual network": "microsoft.network/virtualnetworks",
    "network security group": "microsoft.network/networksecuritygroups",
    "network interface": "microsoft.network/networkinterfaces",
}

csv.field_size_limit(16 * 1024 * 1024)


def _sniff_delimiter(sample: str) -> str:
    first_line = sample.splitlines()[0] if sample else ""
    counts = {d: first_line.count(d) for d in (",", ";", "\t")}
    best = max(counts, key=counts.get)  # type: ignore[arg-type]
    return best if counts[best] > 0 else ","


def _parse_json_cell(value: str, column: str, index: int, warnings: list[str]) -> Any:
    if value is None or value.strip() == "":
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        warnings.append(f"row {index}: column {column} is not valid JSON; treated as empty")
        return {} if column != "zones" else None


def parse_arg_csv(text: str, *, max_rows: int = DEFAULT_MAX_ROWS) -> ParsedRows:
    text = strip_bom(text)
    if "\x00" in text:
        raise IngestionError("file looks binary")
    delimiter = _sniff_delimiter(text[:4096])
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    try:
        header = next(reader)
    except StopIteration:
        raise IngestionError("CSV is empty") from None
    columns = [HEADER_ALIASES.get(h.strip().strip('"').lower()) for h in header]
    if "type" not in columns:
        raise IngestionError("CSV has no TYPE column")
    has_properties = "properties" in columns
    has_tags = "tags" in columns
    warnings: list[str] = []
    if not has_properties:
        warnings.append(f"{NO_PROPERTIES_WARNING}: criteria that read properties cannot be assessed from this file")
    rows: list[dict[str, Any]] = []
    for index, record in enumerate(reader, start=1):
        if not any(cell.strip() for cell in record):
            continue
        if len(rows) >= max_rows:
            raise TooManyRows(len(rows) + 1, max_rows)
        row: dict[str, Any] = {}
        for column, raw in zip(columns, record, strict=False):
            if column is None:
                continue
            if column in JSON_COLUMNS:
                row[column] = _parse_json_cell(raw, column, index, warnings)
            else:
                row[column] = neutralise_formula(raw.strip())
        if not has_properties:
            rtype = str(row.get("type", "")).strip().lower()
            row["type"] = PORTAL_TYPE_NAMES.get(rtype, rtype)
        rows.append(row)
    if not rows:
        raise IngestionError("CSV has a header and no rows", warnings)
    return ParsedRows(rows=rows, warnings=warnings, has_properties=has_properties, has_tags=has_tags)
