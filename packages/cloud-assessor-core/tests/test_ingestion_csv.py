import json

import pytest
from cloud_assessor_core.ingestion import IngestionError, neutralise_formula, parse_arg_csv
from cloud_assessor_core.ingestion.arg_json import TooManyRows

HEADER = "id,name,type,location,resourceGroup,subscriptionId,tags,properties,sku,identity,kind,zones"


def _row(tags='{"a":"b"}', props='{"x":1}'):
    return (
        f'/s/1,n1,A/B,eastus2,rg,sub,"{tags.replace(chr(34), chr(34) * 2)}","{props.replace(chr(34), chr(34) * 2)}",,,,'
    )


def test_explorer_csv_with_json_cells():
    parsed = parse_arg_csv(HEADER + "\n" + _row())
    assert parsed.has_properties and parsed.has_tags
    assert parsed.rows[0]["tags"] == {"a": "b"} and parsed.rows[0]["properties"] == {"x": 1}
    assert parsed.rows[0]["sku"] is None


def test_bad_json_cell_becomes_empty_with_row_warning():
    parsed = parse_arg_csv(HEADER + "\n" + _row(props="{not json"))
    assert parsed.rows[0]["properties"] == {}
    assert parsed.warnings == ["row 1: column properties is not valid JSON; treated as empty"]


def test_portal_export_is_accepted_with_warning_and_type_mapping():
    text = "﻿NAME,TYPE,RESOURCE GROUP,LOCATION,SUBSCRIPTION\r\nhcw-sample-aks,Kubernetes service,rg,East US 2,sub\r\n"
    parsed = parse_arg_csv(text)
    assert not parsed.has_properties and not parsed.has_tags
    assert parsed.warnings[0].startswith("no properties column")
    assert parsed.rows[0]["type"] == "microsoft.containerservice/managedclusters"
    assert parsed.rows[0]["resourceGroup"] == "rg" and parsed.rows[0]["subscriptionId"] == "sub"


@pytest.mark.parametrize("delim", [";", "\t"])
def test_delimiter_sniffing(delim):
    text = delim.join(["name", "type"]) + "\n" + delim.join(["n", "a/b"]) + "\n"
    parsed = parse_arg_csv(text)
    assert parsed.rows[0]["type"] == "a/b"


def test_formula_cells_are_neutralised():
    parsed = parse_arg_csv("name,type\n=HYPERLINK(1),a/b\n")
    assert parsed.rows[0]["name"] == "'=HYPERLINK(1)"
    assert neutralise_formula("+1") == "'+1" and neutralise_formula("ok") == "ok"


def test_errors():
    with pytest.raises(IngestionError):
        parse_arg_csv("")
    with pytest.raises(IngestionError):
        parse_arg_csv("name,location\nx,y\n")
    with pytest.raises(IngestionError):
        parse_arg_csv("name,type\n")
    with pytest.raises(IngestionError):
        parse_arg_csv("name,type\x00\nx,y\n")


def test_max_rows_csv():
    text = "name,type\n" + "\n".join(f"n{i},a/b" for i in range(4)) + "\n"
    with pytest.raises(TooManyRows):
        parse_arg_csv(text, max_rows=3)


def test_blank_lines_skipped_and_zones_cell():
    text = HEADER + "\n\n" + _row() + "\n"
    parsed = parse_arg_csv(text.replace(",,,,", ',,,,"[""1""]"'))
    assert len(parsed.rows) == 1 and parsed.rows[0]["zones"] == ["1"]
    assert json.dumps(parsed.rows[0]["zones"])
