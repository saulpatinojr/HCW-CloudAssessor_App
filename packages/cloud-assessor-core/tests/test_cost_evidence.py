"""Change set D: `cost-evidence` checks are unknown without evidence, observed with it, and never alter the lab path."""

from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from cloud_assessor_core.assess import assess
from cloud_assessor_core.evaluate import evaluate
from cloud_assessor_core.evaluate.engine import _checks_for
from cloud_assessor_core.evaluate.evaluators import NO_COST_EVIDENCE, eval_cost_evidence, is_estate_check
from cloud_assessor_core.ingestion import normalize, parse_arg_json
from cloud_assessor_core.model import AssessmentScope, BudgetEvidence, Catalog, Check, CostEvidence

SAMPLES = Path(__file__).resolve().parents[3] / "samples"

COST_IDS = {"CA-FIN-002", "CA-FIN-003", "CA-FIN-007"}


def _evidence(**overrides) -> CostEvidence:
    base = {
        "scope": "/subscriptions/00000000-0000-0000-0000-000000000001",
        "period_start": date(2026, 10, 1),
        "period_end": date(2026, 10, 10),
        "currency": "USD",
        "total": 1234.5,
        "by_resource_group": {"rg-a": 1000.0, "rg-b": 234.5},
        "by_cost_center_tag": {"cc-1": 1100.0, "": 134.5},
        "untagged_share": 10.9,
        "budgets": [BudgetEvidence(name="hcw-sample-budget", amount=2000.0, time_grain="Monthly", notifications=2)],
        "anomaly_alerts": ["00000000-0000-4000-8000-000000000001"],
        "as_of": datetime(2026, 10, 10, 12, 0, tzinfo=UTC),
    }
    base.update(overrides)
    return CostEvidence(**base)


def _catalog(*criteria):
    return Catalog(version="1.1.0", retrievedOn="2026-10-10", attribution=["a"], criteria=list(criteria))


def _sample_resources():
    text = (SAMPLES / "sample-resource-graph.json").read_text(encoding="utf-8")
    return normalize(parse_arg_json(text), "arg-json")[0]


@pytest.mark.parametrize("metric", ["budgets-present", "anomaly-alerts-present", "untagged-share"])
def test_unknown_without_evidence(metric):
    out = eval_cost_evidence(None, [], Check(kind="cost-evidence", metric=metric, op=">=", value=1), None)
    assert out.state == "unknown" and out.result is None and out.reason == NO_COST_EVIDENCE
    custom = Check(kind="cost-evidence", metric=metric, unknownReason="custom")
    assert eval_cost_evidence(None, [], custom, None).reason == "custom"


def test_observed_with_evidence_pass_and_fail_per_metric():
    e = _evidence()
    budgets = Check(kind="cost-evidence", metric="budgets-present", op=">=", value=1)
    anomalies = Check(kind="cost-evidence", metric="anomaly-alerts-present", op=">=", value=1)
    untagged = Check(kind="cost-evidence", metric="untagged-share", op="<=", value=20)
    for check in (budgets, anomalies, untagged):
        out = eval_cost_evidence(None, [], check, e)
        assert out.state == "observed" and out.result == "pass", check.metric
        assert out.evidence.path == check.metric and out.evidence.observed is not None
    none = _evidence(budgets=[], anomaly_alerts=[], untagged_share=35.0)
    for check in (budgets, anomalies, untagged):
        out = eval_cost_evidence(None, [], check, none)
        assert out.state == "observed" and out.result == "fail", check.metric
    # defaults apply when the check carries no op/value
    assert eval_cost_evidence(None, [], Check(kind="cost-evidence", metric="budgets-present"), e).result == "pass"
    assert eval_cost_evidence(None, [], Check(kind="cost-evidence", metric="untagged-share"), none).result == "fail"
    assert is_estate_check(Check(kind="cost-evidence", metric="budgets-present"))


def test_gating_keeps_the_export_path_without_evidence_and_supersedes_it_with(catalog):
    for criterion in catalog.criteria:
        kinds_without = [c.kind for c in _checks_for(criterion, None)]
        kinds_with = [c.kind for c in _checks_for(criterion, _evidence())]
        if criterion.id in COST_IDS:
            assert "cost-evidence" not in kinds_without and kinds_with == ["cost-evidence"]
        else:
            assert kinds_without == kinds_with == [c.kind for c in criterion.checks]
    only_cost = _catalog(
        catalog.criteria[0].model_copy(
            update={
                "id": "CA-FIN-099",
                "resourceTypes": ["estate"],
                "checks": [Check(kind="cost-evidence", metric="budgets-present")],
            }
        )
    )
    assert _checks_for(only_cost.criteria[0], None)[0].kind == "cost-evidence"
    assert evaluate([], only_cost)[0].state == "unknown"
    assert evaluate([], only_cost, evidence=_evidence())[0].result == "pass"


def test_sample_flips_cost_criteria_to_observed_only_with_evidence(catalog, scoring):
    resources = _sample_resources()
    without = {f.criterionId: f for f in evaluate(resources, catalog) if f.criterionId in COST_IDS}
    assert without["CA-FIN-003"].state == "unknown"
    assert without["CA-FIN-007"].state == "observed" and without["CA-FIN-002"].state == "observed"
    good = {f.criterionId: f for f in evaluate(resources, catalog, evidence=_evidence()) if f.criterionId in COST_IDS}
    assert all(f.state == "observed" and f.result == "pass" for f in good.values())
    bad_evidence = _evidence(budgets=[], anomaly_alerts=[], untagged_share=50.0)
    bad = {f.criterionId: f for f in evaluate(resources, catalog, evidence=bad_evidence) if f.criterionId in COST_IDS}
    assert all(f.state == "observed" and f.result == "fail" for f in bad.values())
    untouched = [f.criterionId for f in evaluate(resources, catalog) if f.criterionId not in COST_IDS]
    assert untouched == [
        f.criterionId for f in evaluate(resources, catalog, evidence=_evidence()) if f.criterionId not in COST_IDS
    ]


def test_assess_carries_edition_scope_and_evidence(catalog, scoring):
    resources = _sample_resources()
    scope = AssessmentScope(count=1, subscriptions=["a" * 64])
    a = assess(
        resources, catalog, scoring, source_format="arg-live", evidence=_evidence(), edition="appliance", scope=scope
    )
    assert a.edition == "appliance" and a.scope == scope and a.core_version == "0.3.0" and a.catalog_version == "1.1.0"
    assert all(f.state == "observed" for f in a.findings if f.criterionId in COST_IDS)
    panel = {u.topic: u.criteria for u in a.unknown_by_design}
    assert panel["Budgets and cost alerts"] == []
    plain = assess(resources, catalog, scoring, source_format="arg-json")
    assert plain.edition is None and plain.scope is None
    assert "CA-FIN-003" in {u for u in plain.model_dump()["unknown_by_design"][1]["criteria"]}
