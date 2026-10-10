import json
from pathlib import Path

import pytest
from cloud_assessor_core.catalog import (
    CatalogError,
    catalog_dir,
    generate_schema,
    load_catalog,
    load_scoring,
    schema_matches,
)
from cloud_assessor_core.catalog.schema import SCHEMA_DIALECT, schema_text
from cloud_assessor_core.model import LEARN_URL_HOSTS


def test_committed_catalog_loads_with_25_criteria(catalog, scoring):
    assert len(catalog.criteria) == 25
    assert sorted(c.id for c in catalog.criteria) == [c.id for c in catalog.criteria]
    ids = {c.id for c in catalog.criteria}
    assert (
        {f"CA-FIN-{i:03d}" for i in range(1, 8)} <= ids
        and {f"CA-WAF-{i:03d}" for i in range(1, 8)} <= ids
        and {f"CA-ZT-{i:03d}" for i in range(1, 12)} <= ids
    )
    assert {c.framework for c in catalog.criteria} == {"finops", "waf-cost", "zero-trust"}
    assert all(c.verify for c in catalog.criteria), "every learnUrl is still [VERIFY]"
    assert all(c.retrievedOn == "2026-10-10" for c in catalog.criteria)
    assert scoring.severityWeights == {"critical": 4, "high": 3, "medium": 2, "low": 1}
    kinds = {k.kind for c in catalog.criteria for k in c.checks}
    assert kinds == {"tag-present", "property-equals", "property-exists", "sku-in", "count-threshold", "cross-resource"}
    assert next(c for c in catalog.criteria if c.id == "CA-ZT-001").anyPass


def test_schema_is_draft_2020_12_and_matches_committed_file():
    schema = generate_schema()
    assert schema["$schema"] == SCHEMA_DIALECT
    committed = (catalog_dir() / "schema.json").read_text(encoding="utf-8")
    assert schema_matches(committed) and committed == schema_text()
    assert not schema_matches("{not json")
    assert not schema_matches(json.dumps({"x": 1}))


def test_learn_url_hosts(catalog):
    assert {"learn.microsoft.com", "www.finops.org"} == LEARN_URL_HOSTS
    assert all(
        c.learnUrl.startswith(("https://learn.microsoft.com/", "https://www.finops.org/")) for c in catalog.criteria
    )


def test_loader_fails_closed(tmp_path: Path):
    with pytest.raises(CatalogError):
        load_catalog(tmp_path)
    (tmp_path / "criteria.json").write_text("{bad", encoding="utf-8")
    with pytest.raises(CatalogError):
        load_catalog(tmp_path)
    (tmp_path / "criteria.json").write_text(json.dumps({"version": "1.0.0"}), encoding="utf-8")
    with pytest.raises(CatalogError):
        load_catalog(tmp_path)
    src = catalog_dir()
    (tmp_path / "criteria.json").write_text((src / "criteria.json").read_text(encoding="utf-8"), encoding="utf-8")
    (tmp_path / "scoring.json").write_text((src / "scoring.json").read_text(encoding="utf-8"), encoding="utf-8")
    with pytest.raises(CatalogError, match="drifted"):
        load_catalog(tmp_path)
    (tmp_path / "schema.json").write_text(schema_text(), encoding="utf-8")
    assert len(load_catalog(tmp_path).criteria) == 25
    (tmp_path / "scoring.json").write_text(
        json.dumps({"version": "1.0.0", "severityWeights": {}, "frameworks": {}}), encoding="utf-8"
    )
    with pytest.raises(CatalogError, match="no weight"):
        load_catalog(tmp_path)
    (tmp_path / "scoring.json").write_text("{", encoding="utf-8")
    with pytest.raises(CatalogError):
        load_scoring(tmp_path)
    (tmp_path / "scoring.json").write_text(json.dumps({"version": "x"}), encoding="utf-8")
    with pytest.raises(CatalogError):
        load_scoring(tmp_path)
    (tmp_path / "scoring.json").write_text(
        json.dumps(
            {"version": "1.0.0", "severityWeights": {}, "frameworks": {"f": {"label": "l", "pillars": {"p": 11}}}}
        ),
        encoding="utf-8",
    )
    with pytest.raises(CatalogError):
        load_scoring(tmp_path)
