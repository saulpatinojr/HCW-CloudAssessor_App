import pytest
from cloud_assessor_core.evaluate.evaluators import (
    EVALUATORS,
    NO_PROPERTIES,
    NO_TAGS,
    eval_count_threshold,
    eval_cross_resource,
    eval_property_equals,
    eval_property_exists,
    eval_sku_in,
    eval_tag_present,
    is_estate_check,
    matches_when,
)
from cloud_assessor_core.model import Check, SourceRef, When


def test_registry_has_six_kinds():
    assert set(EVALUATORS) == {
        "tag-present",
        "property-equals",
        "property-exists",
        "sku-in",
        "count-threshold",
        "cross-resource",
    }


def test_tag_present_all_any_and_alternatives(make_resource):
    r = make_resource(tags={"CostCenter": "x", "owner": " "})
    out = eval_tag_present(r, [], Check(kind="tag-present", keys=["costCenter|cost-center", "owner"], mode="all"))
    assert out.state == "observed" and out.result == "fail" and "owner" in out.reason
    out = eval_tag_present(r, [], Check(kind="tag-present", keys=["cost-center|costCenter", "owner"], mode="any"))
    assert out.result == "pass"


def test_tag_present_unknown_without_tags_column(make_resource):
    r = make_resource(source=SourceRef(format="arg-csv", row=1, has_tags=False))
    out = eval_tag_present(r, [], Check(kind="tag-present", keys=["owner"]))
    assert out.state == "unknown" and out.reason == NO_TAGS


def test_property_equals_scalar_wildcard_anyof_and_missing(make_resource):
    r = make_resource()
    assert (
        eval_property_equals(r, [], Check(kind="property-equals", path="properties.flag", equals=True)).result == "pass"
    )
    assert (
        eval_property_equals(r, [], Check(kind="property-equals", path="properties.a.b[*].c", equals=1)).result
        == "fail"
    )
    assert (
        eval_property_equals(r, [], Check(kind="property-equals", path="properties.a.b[*].c", anyOf=[1, 2])).result
        == "pass"
    )
    out = eval_property_equals(r, [], Check(kind="property-equals", path="properties.nope", equals=1))
    assert out.state == "unknown" and out.evidence.expected == 1
    out = eval_property_equals(r, [], Check(kind="property-equals", path="properties.nope", equals=1, missingIs="fail"))
    assert out.state == "observed" and out.result == "fail"
    out = eval_property_equals(
        r, [], Check(kind="property-equals", path="properties.nope", equals=1, missingIs="pass", unknownReason="x")
    )
    assert out.result == "pass" and out.reason == "x"


def test_property_equals_is_case_insensitive_for_strings(make_resource):
    r = make_resource(properties={"publicNetworkAccess": "disabled"})
    assert (
        eval_property_equals(
            r, [], Check(kind="property-equals", path="properties.publicNetworkAccess", equals="Disabled")
        ).result
        == "pass"
    )


def test_property_reads_are_unknown_without_properties_column(make_resource):
    r = make_resource(source=SourceRef(format="arg-csv", row=1, has_properties=False))
    for check in (
        Check(kind="property-equals", path="properties.flag", equals=True),
        Check(kind="property-exists", path="properties.flag"),
        Check(kind="sku-in", path="sku.tier", allowed=["Free"]),
        Check(kind="sku-in", path="identity.type", allowed=["SystemAssigned"]),
        Check(kind="count-threshold", path="properties.count", metric="value", op=">=", value=1),
    ):
        out = EVALUATORS[check.kind](r, [r], check)
        assert out.state == "unknown" and out.reason == NO_PROPERTIES, check.kind


def test_property_exists_modes(make_resource):
    r = make_resource(properties={"empty": [], "full": [1]})
    assert (
        eval_property_exists(r, [], Check(kind="property-exists", path="properties.empty", mustBe="present")).result
        == "pass"
    )
    assert (
        eval_property_exists(r, [], Check(kind="property-exists", path="properties.empty", mustBe="non-empty")).result
        == "fail"
    )
    assert (
        eval_property_exists(r, [], Check(kind="property-exists", path="properties.full", mustBe="non-empty")).result
        == "pass"
    )
    assert (
        eval_property_exists(r, [], Check(kind="property-exists", path="properties.nope", mustBe="absent")).result
        == "pass"
    )
    assert (
        eval_property_exists(r, [], Check(kind="property-exists", path="properties.nope", mustBe="present")).result
        == "fail"
    )


def test_sku_in_allowed_disallowed_default_path_and_missing(make_resource):
    r = make_resource()
    assert eval_sku_in(r, [], Check(kind="sku-in", allowed=["base"])).result == "pass"
    assert eval_sku_in(r, [], Check(kind="sku-in", path="sku.tier", disallowed=["Free"])).result == "fail"
    assert eval_sku_in(r, [], Check(kind="sku-in", path="identity.type", allowed=["UserAssigned"])).result == "fail"
    out = eval_sku_in(
        make_resource(identity=None), [], Check(kind="sku-in", path="identity.type", allowed=["x"], missingIs="fail")
    )
    assert out.result == "fail"
    out = eval_sku_in(make_resource(sku={"name": ""}), [], Check(kind="sku-in", allowed=["x"]))
    assert out.state == "unknown"


def test_count_threshold_resource_scope(make_resource):
    r = make_resource()
    assert (
        eval_count_threshold(
            r, [], Check(kind="count-threshold", path="properties.a.b[*]", metric="count", op="==", value=2)
        ).result
        == "pass"
    )
    assert (
        eval_count_threshold(
            r, [], Check(kind="count-threshold", path="properties.count", metric="value", op="<=", value=2)
        ).result
        == "fail"
    )
    assert (
        eval_count_threshold(
            r, [], Check(kind="count-threshold", path="properties.nope", metric="count", op="==", value=0)
        ).result
        == "pass"
    )
    out = eval_count_threshold(
        r, [], Check(kind="count-threshold", path="properties.nope", metric="value", op=">", value=0)
    )
    assert out.state == "unknown"
    out = eval_count_threshold(
        r, [], Check(kind="count-threshold", path="properties.flag", metric="value", op=">", value=0, missingIs="fail")
    )
    assert out.result == "fail", "a boolean is not a number"
    assert (
        eval_count_threshold(
            make_resource(properties={"n": "7"}),
            [],
            Check(kind="count-threshold", path="properties.n", metric="value", op="!=", value=7),
        ).result
        == "fail"
    )
    assert (
        eval_count_threshold(
            make_resource(properties={"n": "7"}),
            [],
            Check(kind="count-threshold", path="properties.n", metric="value", op="<", value=8),
        ).result
        == "pass"
    )


def test_count_threshold_estate_scope(make_resource):
    estate = [make_resource(id=f"/r{i}", tags={"costCenter": "x"} if i < 8 else {}) for i in range(10)]
    check = Check(
        kind="count-threshold", scope="estate", path="tags.costCenter", metric="percent-present", op=">=", value=80
    )
    out = eval_count_threshold(None, estate, check)
    assert out.result == "pass" and out.evidence.observed == 80.0
    assert (
        eval_count_threshold(
            None,
            estate,
            Check(kind="count-threshold", scope="estate", path="tags.costCenter", metric="count", op=">", value=8),
        ).result
        == "fail"
    )
    assert (
        eval_count_threshold(
            None,
            estate,
            Check(kind="count-threshold", scope="estate", path="properties.count", metric="value", op="==", value=30),
        ).result
        == "pass"
    )
    out = eval_count_threshold(
        None,
        estate,
        Check(kind="count-threshold", scope="estate", path="properties.nope", metric="value", op="==", value=30),
    )
    assert out.state == "unknown"
    blind = [make_resource(source=SourceRef(format="arg-csv", row=1, has_tags=False))]
    assert eval_count_threshold(None, blind, check).state == "unknown"


def test_cross_resource_relations(make_resource):
    parent = make_resource(
        id="/subscriptions/s/resourceGroups/rg/providers/a/b/p", resource_group="rg", subscription_id="s"
    )
    child = make_resource(
        id="/subscriptions/s/resourceGroups/rg/providers/a/b/p/children/c",
        type="a/b/children",
        resource_group="rg",
        subscription_id="s",
    )
    sibling = make_resource(
        id="/subscriptions/s/resourceGroups/rg/providers/x/y/sib",
        type="x/y",
        resource_group="rg",
        subscription_id="s",
        tags={"environment": "prod"},
    )
    estate = [parent, child, sibling]
    assert (
        eval_cross_resource(
            parent, estate, Check(kind="cross-resource", relation="has-child", type="a/b/children")
        ).result
        == "pass"
    )
    assert (
        eval_cross_resource(parent, estate, Check(kind="cross-resource", relation="estate-has", type="X/Y")).result
        == "pass"
    )
    assert (
        eval_cross_resource(parent, estate, Check(kind="cross-resource", relation="has-sibling", type="x/y")).result
        == "pass"
    )
    where = When(path="tags.environment", equals="dev")
    assert (
        eval_cross_resource(
            parent, estate, Check(kind="cross-resource", relation="has-sibling", type="x/y", where=where)
        ).state
        == "unknown"
    )
    out = eval_cross_resource(
        parent,
        estate,
        Check(kind="cross-resource", relation="estate-has", type="nope/x", absentIs="fail", unknownReason="why"),
    )
    assert out.result == "fail" and out.reason == "why"
    assert is_estate_check(Check(kind="cross-resource", relation="estate-has", type="a"))
    assert not is_estate_check(Check(kind="cross-resource", relation="has-child", type="a"))


def test_matches_when(make_resource):
    r = make_resource()
    assert matches_when(r, None) is True
    assert matches_when(r, When(path="tags.environment", **{"in": ["dev", "test"]})) is True
    assert matches_when(r, When(path="tags.environment", equals="prod")) is False
    assert matches_when(r, When(path="tags.nope", equals="x")) is False
    assert (
        matches_when(
            make_resource(source=SourceRef(format="arg-csv", row=1, has_tags=False)),
            When(path="tags.environment", equals="x"),
        )
        is None
    )


@pytest.mark.parametrize("kind", ["tag-present", "property-equals", "property-exists", "sku-in"])
def test_resource_evaluators_require_a_resource(kind):
    check = Check(kind=kind, path="p", keys=["k"], allowed=["a"], equals=1)
    with pytest.raises(AssertionError):
        EVALUATORS[kind](None, [], check)
