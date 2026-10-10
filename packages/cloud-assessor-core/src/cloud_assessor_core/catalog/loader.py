"""Load and validate the catalog from the installed package (or the source tree) and fail closed on drift."""

from __future__ import annotations

import json
from importlib import resources
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from cloud_assessor_core.catalog.schema import schema_matches
from cloud_assessor_core.model import Catalog


class CatalogError(RuntimeError):
    """The catalog could not be loaded; the application refuses to start (fail closed)."""


class FrameworkScoring(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    label: str
    pillars: dict[str, float]

    @field_validator("pillars")
    @classmethod
    def _bounded(cls, value: dict[str, float]) -> dict[str, float]:
        for k, v in value.items():
            if not 0 <= v <= 10:
                raise ValueError(f"pillar weight {k} outside [0, 10]")
        return value


class Scoring(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    severityWeights: dict[str, int]
    frameworks: dict[str, FrameworkScoring]


def catalog_dir() -> Path:
    """The installed package's catalog_data, or the source tree's catalog/ next to src/."""
    packaged = resources.files("cloud_assessor_core") / "catalog_data"
    with resources.as_file(packaged) as p:
        if p.is_dir():
            return p
    source = Path(__file__).resolve().parents[3] / "catalog"
    if source.is_dir():
        return source
    raise CatalogError("catalog directory not found")


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CatalogError(f"{path.name}: {type(exc).__name__}") from None


def load_catalog(path: Path | None = None, *, check_schema: bool = True) -> Catalog:
    base = path or catalog_dir()
    document = _read_json(base / "criteria.json")
    try:
        catalog = Catalog.model_validate(document)
    except ValidationError as exc:
        raise CatalogError(f"criteria.json: {exc.error_count()} validation errors") from None
    if check_schema:
        schema_path = base / "schema.json"
        if not schema_path.is_file() or not schema_matches(schema_path.read_text(encoding="utf-8")):
            raise CatalogError("schema.json has drifted from the model; run scripts/check-catalog.py --write-schema")
    scoring = load_scoring(base)
    for criterion in catalog.criteria:
        fw = scoring.frameworks.get(criterion.framework)
        if fw is None or criterion.pillar not in fw.pillars:
            raise CatalogError(f"{criterion.id}: pillar {criterion.pillar!r} has no weight in scoring.json")
    return catalog


def load_scoring(path: Path | None = None) -> Scoring:
    base = path or catalog_dir()
    try:
        return Scoring.model_validate(_read_json(base / "scoring.json"))
    except ValidationError as exc:
        raise CatalogError(f"scoring.json: {exc.error_count()} validation errors") from None
