import pytest
from cloud_assessor_core.paths import get_path

DOC = {"a": {"b": [{"c": 1}, {"c": 2}, {"d": 3}], "Name": "x"}, "list": [1, 2], "empty": {}}


def test_simple_and_nested():
    assert get_path(DOC, "a.Name").values == ["x"]
    assert get_path(DOC, "a.name").values == ["x"], "keys are matched case-insensitively"


def test_wildcard_fans_out_and_skips_missing():
    r = get_path(DOC, "a.b[*].c")
    assert r.found and r.values == [1, 2]


def test_index():
    assert get_path(DOC, "a.b[1].c").values == [2]
    assert not get_path(DOC, "a.b[9].c").found


def test_missing_path():
    r = get_path(DOC, "a.zzz.c")
    assert not r.found and r.values == []
    assert not get_path(DOC, "list.x").found
    assert not get_path(None, "a").found


def test_wildcard_on_non_list_is_not_found():
    assert not get_path(DOC, "a[*]").found


def test_bad_segment_raises():
    with pytest.raises(ValueError):
        get_path(DOC, "a[x]")
    with pytest.raises(ValueError):
        get_path(DOC, "a[0]b")


def test_empty_segments_ignored():
    assert get_path(DOC, "a..Name").values == ["x"]
