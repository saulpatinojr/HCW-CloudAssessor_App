import pytest
from cloud_assessor_core.ingestion import IngestionError, ParsedRows, normalize


def test_derives_group_subscription_and_name_from_id():
    rows = ParsedRows(rows=[{"id": "/subscriptions/S1/resourceGroups/RG1/providers/A/B/name1", "type": "A/B"}])
    resources, warnings = normalize(rows, "arg-json")
    r = resources[0]
    assert r.subscription_id == "S1" and r.resource_group == "RG1" and r.name == "name1" and r.type == "a/b"
    assert warnings == []


def test_synthetic_id_when_absent_is_one_warning():
    rows = ParsedRows(
        rows=[{"name": "n", "type": "a/b", "resourceGroup": "rg", "subscriptionId": "s"}, {"name": "m", "type": "a/b"}]
    )
    resources, warnings = normalize(rows, "arg-csv")
    assert resources[0].id == "/subscriptions/s/resourceGroups/rg/providers/a/b/n"
    assert resources[1].id == "/subscriptions/unknown/resourceGroups/unknown/providers/a/b/m"
    assert len(warnings) == 1 and warnings[0].startswith("synthetic-id: 2 rows")


def test_rows_without_type_or_identity_are_skipped():
    rows = ParsedRows(rows=[{"name": "n"}, {"type": "a/b"}, {"type": "a/b", "name": "ok"}])
    resources, warnings = normalize(rows, "arg-json")
    assert [r.name for r in resources] == ["ok"]
    assert warnings[0] == "row 1: missing type; skipped" and warnings[1] == "row 2: missing id and name; skipped"


def test_all_rows_unusable_raises():
    with pytest.raises(IngestionError) as exc:
        normalize(ParsedRows(rows=[{"name": "n"}]), "arg-json")
    assert exc.value.warnings == ["row 1: missing type; skipped"]


def test_coercions_and_source_flags():
    rows = ParsedRows(
        rows=[
            {
                "id": "/subscriptions/s/providers/a/b/n",
                "type": "a/b",
                "tags": {"k": None, "n": 1},
                "properties": "junk",
                "sku": "x",
                "zones": ["1", 2],
                "kind": " k ",
            }
        ],
        has_properties=False,
        has_tags=False,
    )
    r, _ = normalize(rows, "arg-csv")
    assert r[0].tags == {"k": "", "n": "1"} and r[0].properties == {} and r[0].sku is None
    assert r[0].zones == ["1", "2"] and r[0].kind == "k" and r[0].resource_group is None and r[0].subscription_id == "s"
    assert r[0].source.has_properties is False and r[0].source.has_tags is False and r[0].source.format == "arg-csv"
