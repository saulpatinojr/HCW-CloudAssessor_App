"""findings.csv, formula-neutralised on every cell."""

from __future__ import annotations

import csv
import io
import json

from cloud_assessor_core.ingestion.normalize import neutralise_formula
from cloud_assessor_core.model import Finding

COLUMNS = [
    "criterionId",
    "framework",
    "pillar",
    "severity",
    "state",
    "result",
    "resourceId",
    "resourceName",
    "resourceType",
    "evidencePath",
    "observed",
    "expected",
    "reason",
    "remediation",
    "learnUrl",
]


def _text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return neutralise_formula(value)
    return neutralise_formula(json.dumps(value, sort_keys=True))


def findings_csv(findings: list[Finding]) -> str:
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(COLUMNS)
    for f in findings:
        writer.writerow(
            [
                _text(f.criterionId),
                _text(f.framework),
                _text(f.pillar),
                _text(f.severity),
                _text(f.state),
                _text(f.result),
                _text(f.resourceId),
                _text(f.resourceName),
                _text(f.resourceType),
                _text(f.evidence.path),
                _text(f.evidence.observed),
                _text(f.evidence.expected),
                _text(f.reason),
                _text(f.remediation),
                _text(f.learnUrl),
            ]
        )
    return out.getvalue()
