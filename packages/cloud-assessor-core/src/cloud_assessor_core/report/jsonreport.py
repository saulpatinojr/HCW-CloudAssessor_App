"""report.json: the assessment document with model and catalog versions."""

from __future__ import annotations

import json

from cloud_assessor_core.model import Assessment


def to_dict(assessment: Assessment) -> dict:
    return assessment.model_dump(mode="json", by_alias=True)


def to_json(assessment: Assessment) -> str:
    return json.dumps(to_dict(assessment), indent=2, sort_keys=False) + "\n"
