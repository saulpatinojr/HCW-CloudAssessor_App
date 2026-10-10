from enum import Enum

import pytest
from cloud_assessor_core.redaction import VisitorDataError, assert_no_visitor_data, scrub


def test_scrub_replaces_guids_paths_and_secret_shapes():
    text = (
        "sub /subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/x "
        "id 12345678-1234-1234-1234-123456789abc AccountKey=" + "A" * 40 + " ok"
    )
    out = scrub(text)
    assert "00000000-0000" not in out and "resourceGroups" not in out and "AccountKey=AAAA" not in out
    assert out.count("<redacted>") == 3 and out.endswith("ok")
    assert len(scrub("x" * 1000)) == 500


def test_assert_no_visitor_data_accepts_counts_flags_and_words():
    class E(Enum):
        A = 1

    assert_no_visitor_data(
        {"event": "startup", "n": 3, "ratio": 0.5, "flag": True, "none": None, "e": E.A, "code": "not_found"}
    )


@pytest.mark.parametrize(
    "event",
    [{"name": "hcw-sample-aks"}, {"path": "/subscriptions/x"}, {"bad key": 1}, {"x": ["list"]}, {"y": {"d": 1}}],
)
def test_assert_no_visitor_data_rejects_strings_and_structures(event):
    with pytest.raises(VisitorDataError):
        assert_no_visitor_data(event)
