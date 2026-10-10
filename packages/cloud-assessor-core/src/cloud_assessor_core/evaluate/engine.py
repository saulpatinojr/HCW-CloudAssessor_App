"""Apply the catalog to the normalised estate: applicability by resourceTypes and `when`, estate checks run once."""

from __future__ import annotations

from cloud_assessor_core.evaluate.evaluators import (
    ALL_TYPES,
    ESTATE_TYPE,
    EVALUATORS,
    Outcome,
    is_estate_check,
    matches_when,
)
from cloud_assessor_core.model import Catalog, Criterion, Evidence, Finding, Resource, UnknownByDesign

UNKNOWN_BY_DESIGN: list[tuple[str, str]] = [
    ("Spend and forecasts", "Cost data is not in a Resource Graph export; it lives in Cost Management."),
    (
        "Budgets and cost alerts",
        "Budgets are not in the Resource Graph resources table unless exported from their own table.",
    ),
    (
        "Role assignments and identity posture",
        "Role assignments live in authorizationresources, not resources; Entra is never read.",
    ),
    ("Diagnostic settings", "microsoft.insights/diagnosticsettings is not in the resources table."),
    ("Policy compliance", "Policy states live in policyresources and are not exported here."),
    ("Defender plan state", "Subscription-level Defender plans are not resources."),
    ("Network flow and private DNS resolution", "An export shows configuration, not traffic or resolution."),
]


def _combine(outcomes: list[Outcome], any_pass: bool) -> Outcome:
    if len(outcomes) == 1:
        return outcomes[0]
    results = [o.result for o in outcomes]
    if any_pass:
        if "pass" in results:
            return next(o for o in outcomes if o.result == "pass")
        if any(o.state == "unknown" for o in outcomes):
            return next(o for o in outcomes if o.state == "unknown")
        return outcomes[0]
    if "fail" in results:
        return next(o for o in outcomes if o.result == "fail")
    if any(o.state == "unknown" for o in outcomes):
        return next(o for o in outcomes if o.state == "unknown")
    return outcomes[0]


def _finding(criterion: Criterion, resource: Resource | None, outcome: Outcome) -> Finding:
    return Finding(
        criterionId=criterion.id,
        framework=criterion.framework,
        pillar=criterion.pillar,
        severity=criterion.severity,
        resourceId=resource.id if resource else None,
        resourceName=resource.name if resource else None,
        resourceType=resource.type if resource else None,
        state=outcome.state,  # type: ignore[arg-type]
        result=outcome.result,  # type: ignore[arg-type]
        evidence=outcome.evidence,
        reason=outcome.reason,
        remediation=criterion.remediation,
        learnUrl=criterion.learnUrl,
    )


def _not_applicable(criterion: Criterion, resource: Resource, reason: str) -> Finding:
    return Finding(
        criterionId=criterion.id,
        framework=criterion.framework,
        pillar=criterion.pillar,
        severity=criterion.severity,
        resourceId=resource.id,
        resourceName=resource.name,
        resourceType=resource.type,
        state="not-applicable",
        result=None,
        evidence=Evidence(path=criterion.when.path if criterion.when else None),
        reason=reason,
        remediation=criterion.remediation,
        learnUrl=criterion.learnUrl,
    )


def _run_checks(criterion: Criterion, resource: Resource | None, estate: list[Resource]) -> Outcome:
    outcomes = [EVALUATORS[check.kind](resource, estate, check) for check in criterion.checks]
    return _combine(outcomes, criterion.anyPass)


def evaluate(resources: list[Resource], catalog: Catalog) -> list[Finding]:
    findings: list[Finding] = []
    estate = list(resources)
    for criterion in catalog.criteria:
        if criterion.resourceTypes == [ESTATE_TYPE] or all(is_estate_check(c) for c in criterion.checks):
            findings.append(_finding(criterion, None, _run_checks(criterion, None, estate)))
            continue
        wanted = set(criterion.resourceTypes)
        for resource in estate:
            if ALL_TYPES not in wanted and resource.type not in wanted:
                continue
            applicable = matches_when(resource, criterion.when)
            if applicable is False:
                findings.append(_not_applicable(criterion, resource, "applicability condition not met"))
                continue
            if applicable is None:
                findings.append(
                    _finding(
                        criterion,
                        resource,
                        Outcome(
                            "unknown",
                            None,
                            Evidence(path=criterion.when.path if criterion.when else None),
                            "applicability cannot be read from this export",
                        ),
                    )
                )
                continue
            findings.append(_finding(criterion, resource, _run_checks(criterion, resource, estate)))
    return findings


def unknown_by_design(catalog: Catalog, findings: list[Finding]) -> list[UnknownByDesign]:
    """The honesty panel: topics an export cannot show, with the criteria that returned unknown for that reason."""
    unknown_ids = sorted({f.criterionId for f in findings if f.state == "unknown"})
    estate_ids = {c.id for c in catalog.criteria if c.resourceTypes == [ESTATE_TYPE]}
    panel = []
    for topic, reason in UNKNOWN_BY_DESIGN:
        ids = []
        if "Budgets" in topic:
            ids = [i for i in unknown_ids if i in estate_ids and i.startswith("CA-FIN")]
        elif "Role assignments" in topic:
            ids = [i for i in unknown_ids if i in estate_ids and i.startswith("CA-ZT")]
        panel.append(UnknownByDesign(topic=topic, reason=reason, criteria=ids))
    return panel
