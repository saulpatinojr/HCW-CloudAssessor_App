"""JSON Schema (draft 2020-12) for catalog/criteria.json, generated from the pydantic Catalog model."""

from __future__ import annotations

import json
from typing import Any

from pydantic.json_schema import GenerateJsonSchema

from cloud_assessor_core.model import Catalog

SCHEMA_DIALECT = "https://json-schema.org/draft/2020-12/schema"
SCHEMA_ID = "https://hybridcloudworks.com/schemas/cloud-assessor/catalog-1.json"


class _Generator(GenerateJsonSchema):
    schema_dialect = SCHEMA_DIALECT


def generate_schema() -> dict[str, Any]:
    schema = Catalog.model_json_schema(schema_generator=_Generator, mode="validation")
    return {"$schema": SCHEMA_DIALECT, "$id": SCHEMA_ID, **schema}


def schema_text() -> str:
    return json.dumps(generate_schema(), indent=2, sort_keys=True) + "\n"


def schema_matches(committed: str) -> bool:
    """True when the committed schema.json equals the schema generated from the model (CI drift check)."""
    try:
        return json.loads(committed) == generate_schema()
    except json.JSONDecodeError:
        return False
