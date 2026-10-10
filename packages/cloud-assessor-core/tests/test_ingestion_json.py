import json

import pytest
from cloud_assessor_core.ingestion import IngestionError, parse_arg_json
from cloud_assessor_core.ingestion.arg_json import PAGED_WARNING, TooManyRows

ROW = {
    "id": "/subscriptions/s/resourceGroups/rg/providers/a/b/n",
    "name": "n",
    "type": "A/B",
    "properties": {"x": 1},
    "tags": {},
}


def test_bare_array():
    parsed = parse_arg_json(json.dumps([ROW]))
    assert len(parsed.rows) == 1 and parsed.warnings == [] and parsed.has_properties


def test_envelope_with_paging_and_total_warnings():
    doc = {"count": 1, "data": [ROW], "skip_token": "abc", "total_records": 5}
    parsed = parse_arg_json(json.dumps(doc))
    assert PAGED_WARNING in parsed.warnings
    assert any("5 records" in w for w in parsed.warnings)


def test_bom_is_stripped():
    assert len(parse_arg_json("﻿" + json.dumps([ROW])).rows) == 1


def test_invalid_json_cites_position_only():
    with pytest.raises(IngestionError) as exc:
        parse_arg_json("[{")
    assert "line 1" in str(exc.value)


def test_wrong_shapes():
    with pytest.raises(IngestionError):
        parse_arg_json(json.dumps({"nope": 1}))
    with pytest.raises(IngestionError):
        parse_arg_json(json.dumps("string"))
    with pytest.raises(IngestionError):
        parse_arg_json(json.dumps([1, 2]))


def test_non_object_rows_are_skipped_with_row_number():
    parsed = parse_arg_json(json.dumps([ROW, 7]))
    assert len(parsed.rows) == 1 and parsed.warnings == ["row 2: not an object; skipped"]


def test_max_rows():
    with pytest.raises(TooManyRows) as exc:
        parse_arg_json(json.dumps([ROW] * 3), max_rows=2)
    assert exc.value.count == 3 and exc.value.max_rows == 2


def test_rows_without_properties_warn():
    parsed = parse_arg_json(json.dumps([{"name": "n", "type": "a/b"}]))
    assert not parsed.has_properties and not parsed.has_tags
    assert any("no properties column" in w for w in parsed.warnings)
