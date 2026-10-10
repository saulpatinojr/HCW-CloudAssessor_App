from cloud_assessor_core.catalog.loader import FrameworkScoring, Scoring
from cloud_assessor_core.model import Finding
from cloud_assessor_core.score import bounded_weights, score

SCORING = Scoring(
    version="1.0.0",
    severityWeights={"critical": 4, "high": 3, "medium": 2, "low": 1},
    frameworks={
        "finops": FrameworkScoring(label="FinOps", pillars={"A": 2, "B": 1}),
        "zero-trust": FrameworkScoring(label="ZT", pillars={"N": 1}),
    },
)


def _f(cid, pillar, sev, state, result, framework="finops"):
    return Finding(
        criterionId=cid,
        framework=framework,
        pillar=pillar,
        severity=sev,
        resourceId="/r",
        resourceName="r",
        resourceType="t",
        state=state,
        result=result,
        reason="",
        remediation="",
        learnUrl="https://learn.microsoft.com/",
    )


def test_unknown_lowers_coverage_never_score():
    findings = [
        _f("CA-FIN-001", "A", "high", "observed", "pass"),
        _f("CA-FIN-001", "A", "high", "observed", "fail"),
        _f("CA-FIN-002", "A", "low", "unknown", None),
        _f("CA-FIN-003", "A", "low", "not-applicable", None),
    ]
    cards = {(c.framework, c.pillar): c for c in score(findings, SCORING)}
    a = cards[("finops", "A")]
    assert a.score == 50.0 and a.coverage == round(2 / 3, 3) and a.unknown == 1 and a.notApplicable == 1
    assert a.passed == 1 and a.failed == 1 and a.observed == 2 and a.weight == 2
    total = cards[("finops", None)]
    assert total.score == 50.0 and total.coverage == round(2 / 3, 3)
    assert ("finops", "B") not in cards, "pillars without findings have no card"
    zt = cards[("zero-trust", None)]
    assert zt.score is None and zt.coverage is None


def test_severity_weighting_and_framework_total_by_pillar_weight():
    findings = [
        _f("CA-FIN-001", "A", "critical", "observed", "fail"),
        _f("CA-FIN-002", "A", "low", "observed", "pass"),
        _f("CA-FIN-003", "B", "low", "observed", "pass"),
    ]
    cards = {(c.framework, c.pillar): c for c in score(findings, SCORING)}
    assert cards[("finops", "A")].score == 20.0
    assert cards[("finops", "B")].score == 100.0
    assert cards[("finops", None)].score == round((2 * 20 + 1 * 100) / 3, 1)


def test_weight_overrides_are_bounded_and_unknown_keys_ignored():
    w = bounded_weights(
        SCORING, {"finops": {"A": 99, "B": -5, "Z": 1}, "nope": {"A": 1}, "zero-trust": "junk", "finops2": None}
    )
    assert w["finops"] == {"A": 10.0, "B": 0.0} and w["zero-trust"] == {"N": 1}
    w = bounded_weights(SCORING, {"finops": {"A": True, "B": "3"}})
    assert w["finops"] == {"A": 2, "B": 1}
    findings = [_f("CA-FIN-001", "A", "high", "observed", "fail"), _f("CA-FIN-003", "B", "low", "observed", "pass")]
    cards = {(c.framework, c.pillar): c for c in score(findings, SCORING, {"finops": {"A": 0}})}
    assert cards[("finops", None)].score == 100.0, "a zero-weight pillar drops out of the framework total"
