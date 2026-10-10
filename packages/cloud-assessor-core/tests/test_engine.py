from cloud_assessor_core.evaluate import evaluate, unknown_by_design
from cloud_assessor_core.model import Catalog, Check, SourceRef, When


def _catalog(*criteria):
    return Catalog(version="1.0.0", retrievedOn="2026-10-10", attribution=["a"], criteria=list(criteria))


def test_applicability_by_type_when_and_estate(make_resource, make_criterion):
    aks = make_resource()
    disk = make_resource(id="/d", type="microsoft.compute/disks", tags={"environment": "prod"})
    blind = make_resource(id="/b", source=SourceRef(format="arg-csv", row=3, has_tags=False))
    per_type = make_criterion([Check(kind="property-exists", path="properties.flag")], id="CA-ZT-001")
    conditional = make_criterion(
        [Check(kind="property-exists", path="properties.flag")],
        id="CA-ZT-002",
        resourceTypes=["*"],
        when=When(path="tags.environment", equals="dev"),
    )
    estate = make_criterion(
        [Check(kind="cross-resource", relation="estate-has", type="microsoft.compute/disks")],
        id="CA-ZT-003",
        resourceTypes=["estate"],
    )
    findings = evaluate([aks, disk, blind], _catalog(per_type, conditional, estate))
    by = {(f.criterionId, f.resourceId): f for f in findings}
    assert (
        by[
            (
                "CA-ZT-001",
                "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/rg-a/providers/microsoft.containerservice/managedclusters/hcw-sample-aks",
            )
        ].result
        == "pass"
    )
    assert ("CA-ZT-001", "/d") not in by
    assert by[("CA-ZT-002", "/d")].state == "not-applicable"
    assert by[("CA-ZT-002", "/b")].state == "unknown" and "applicability" in by[("CA-ZT-002", "/b")].reason
    assert by[("CA-ZT-003", None)].result == "pass"
    assert sum(1 for f in findings if f.criterionId == "CA-ZT-003") == 1


def test_any_pass_and_all_pass_combination(make_resource, make_criterion):
    r = make_resource(properties={"a": True, "b": False})
    a = Check(kind="property-equals", path="properties.a", equals=True)
    b = Check(kind="property-equals", path="properties.b", equals=True)
    missing = Check(kind="property-equals", path="properties.c", equals=True)
    assert evaluate([r], _catalog(make_criterion([a, b], anyPass=True)))[0].result == "pass"
    assert evaluate([r], _catalog(make_criterion([a, b])))[0].result == "fail"
    assert evaluate([r], _catalog(make_criterion([b, missing], anyPass=True)))[0].state == "unknown"
    assert evaluate([r], _catalog(make_criterion([a, missing])))[0].state == "unknown"
    assert evaluate([r], _catalog(make_criterion([a, a])))[0].result == "pass"
    assert evaluate([r], _catalog(make_criterion([b, b], anyPass=True)))[0].result == "fail"


def test_unknown_by_design_lists_estate_criteria_that_were_unknown(make_resource, make_criterion):
    r = make_resource()
    budgets = make_criterion(
        [Check(kind="cross-resource", relation="estate-has", type="microsoft.consumption/budgets")],
        id="CA-FIN-003",
        framework="finops",
        pillar="Budgeting",
        resourceTypes=["estate"],
    )
    roles = make_criterion(
        [Check(kind="cross-resource", relation="estate-has", type="microsoft.authorization/roleassignments")],
        id="CA-ZT-011",
        resourceTypes=["estate"],
    )
    cat = _catalog(budgets, roles)
    panel = unknown_by_design(cat, evaluate([r], cat))
    topics = {p.topic: p.criteria for p in panel}
    assert topics["Budgets and cost alerts"] == ["CA-FIN-003"]
    assert topics["Role assignments and identity posture"] == ["CA-ZT-011"]
    assert len(panel) == 7
