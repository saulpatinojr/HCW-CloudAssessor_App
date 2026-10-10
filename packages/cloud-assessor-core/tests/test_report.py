import io
import json
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import pytest
from cloud_assessor_core.assess import assess
from cloud_assessor_core.ingestion import normalize, parse_arg_json
from cloud_assessor_core.report import (
    BUNDLE_FILES,
    NOT_AN_AUDIT,
    findings_csv,
    make_bundle,
    render_markdown,
    to_json,
    zip_bytes,
)
from cloud_assessor_core.report.jsonreport import to_dict

SAMPLES = Path(__file__).resolve().parents[3] / "samples"


@pytest.fixture(scope="module")
def assessment(catalog, scoring):
    parsed = parse_arg_json(Path(SAMPLES / "sample-resource-graph.json").read_text(encoding="utf-8"))
    resources, warnings = normalize(parsed, "arg-json")
    return assess(
        resources,
        catalog,
        scoring,
        source_format="arg-json",
        file_name="=x.json",
        ingestion_warnings=warnings + ["w1"],
        assessment_id="11111111-1111-4111-8111-111111111111",
        now=datetime(2026, 10, 10, tzinfo=UTC),
    )


def test_markdown_sections_and_coverage_sentence(assessment, catalog):
    md = render_markdown(assessment, catalog)
    for heading in (
        "# Cloud assessment report",
        "## Executive summary",
        "## Scorecards",
        "## Findings by severity",
        "## Unknown",
        "## What this export cannot show",
        "## Attribution",
    ):
        assert heading in md
    assert "Score covers" in md and "could not be assessed from an export" in md
    assert "not affiliated" in md and "Ingestion warnings: 1" in md and "w1" in md
    assert "`=x.json`" in md
    md2 = render_markdown(
        assessment.model_copy(update={"findings": [], "scorecards": [], "ingestion_warnings": [], "file_name": None})
    )
    assert "No failed checks" in md2 and "Every applicable check" in md2 and "not affiliated" in md2


def test_json_carries_versions(assessment):
    doc = json.loads(to_json(assessment))
    assert doc["model_version"] == 1 and doc["catalog_version"] == "1.0.0" and doc["core_version"] == "0.1.0"
    assert doc["summary"]["pass"] >= 1 and to_dict(assessment)["id"] == assessment.id
    assert doc["scorecards"][0]["pass"] >= 0


def test_findings_csv_is_neutralised(assessment):
    evil = assessment.findings[0].model_copy(update={"resourceName": "=cmd()", "reason": "+plus"})
    csv_text = findings_csv([evil])
    assert "'=cmd()" in csv_text and "'+plus" in csv_text
    assert csv_text.splitlines()[0].startswith("criterionId,framework,pillar")


def test_bundle_and_zip(assessment, catalog):
    files = make_bundle(assessment, catalog)
    assert tuple(files) == BUNDLE_FILES and files["NOT-AN-AUDIT.md"].decode() == NOT_AN_AUDIT
    data = zip_bytes(files)
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        assert sorted(zf.namelist()) == sorted(BUNDLE_FILES)
        assert all(i.compress_type == zipfile.ZIP_STORED for i in zf.infolist())
    with pytest.raises(ValueError):
        zip_bytes({"../x": b""})
    with pytest.raises(ValueError):
        zip_bytes({"/abs": b""})
