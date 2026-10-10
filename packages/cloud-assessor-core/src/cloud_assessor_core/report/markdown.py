"""report.md and NOT-AN-AUDIT.md. The report carries the visitor's own data back to the token holder."""

from __future__ import annotations

from cloud_assessor_core.model import Assessment, Catalog, Finding, Scorecard

FRAMEWORK_LABELS = {"finops": "FinOps", "waf-cost": "Well-Architected cost optimisation", "zero-trust": "Zero Trust"}
SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}

NOT_AN_AUDIT = """# This is not an audit

This assessment was produced by the Hybrid Cloud Works Cloud Assessment lab edition from a Resource Graph export you
uploaded. It evaluates paraphrased criteria over exported configuration only.

- It is not a compliance attestation, a security assessment of record, or financial advice.
- It saw only the rows in the export: no cost data, no role assignments, no policy state, no diagnostic settings,
  no Defender plans, no traffic. Every scorecard states its coverage for that reason.
- "Unknown" never lowers a score; it lowers coverage. Treat a high score with low coverage as a question, not an answer.
- Criteria are paraphrased from the FinOps Foundation Framework and the Microsoft Azure Well-Architected Framework
  with attribution; this project is not affiliated with or endorsed by either.
- The lab edition keeps nothing: the assessment expires after two hours or when you delete it.
"""


def _pct(value: float | None, suffix: str = "") -> str:
    return "n/a" if value is None else f"{value:g}{suffix}"


def _coverage_sentence(card: Scorecard) -> str:
    total = card.observed + card.unknown
    return f"Score covers {card.observed} of {total} checks; {card.unknown} could not be assessed from an export."


def _cell(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def render_markdown(assessment: Assessment, catalog: Catalog | None = None) -> str:
    a = assessment
    lines: list[str] = []
    lines.append("# Cloud assessment report (lab edition)")
    lines.append("")
    lines.append(
        f"Assessment `{a.id}` created {a.created_at.isoformat()} from a `{a.source_format}` export"
        + (f" (`{_cell(a.file_name)}`)" if a.file_name else "")
        + "."
    )
    lines.append(
        f"Model version {a.model_version}, catalog {a.catalog_version}, engine {a.core_version}. "
        "Not an audit; see NOT-AN-AUDIT.md."
    )
    lines.append("")
    lines.append("## Executive summary")
    lines.append("")
    s = a.summary
    lines.append(f"- Resources: {s.resourceCount} across {len(s.byType)} types")
    lines.append(
        f"- Criteria: {s.criteriaCount}; findings: {s.findingsCount} (observed {s.observed}: {s.passed} pass, "
        f"{s.failed} fail; unknown {s.unknown}; not applicable {s.notApplicable})"
    )
    if a.ingestion_warnings:
        lines.append(f"- Ingestion warnings: {len(a.ingestion_warnings)}")
        lines.extend(f"  - {_cell(w)}" for w in a.ingestion_warnings)
    lines.append("")
    lines.append("## Scorecards")
    lines.append("")
    lines.append("| Framework | Pillar | Score | Coverage | Pass | Fail | Unknown | N/A |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for c in a.scorecards:
        label = FRAMEWORK_LABELS.get(c.framework, c.framework)
        coverage = _pct(None if c.coverage is None else round(c.coverage * 100, 1), "%")
        lines.append(
            f"| {label} | {c.pillar or '*total*'} | {_pct(c.score)} | {coverage} "
            f"| {c.passed} | {c.failed} | {c.unknown} | {c.notApplicable} |"
        )
    for c in a.scorecards:
        if c.pillar is None:
            lines.append("")
            lines.append(f"{FRAMEWORK_LABELS.get(c.framework, c.framework)}: {_coverage_sentence(c)}")
    lines.append("")
    lines.append("## Findings by severity")
    lines.append("")
    failed = sorted(
        (f for f in a.findings if f.result == "fail"),
        key=lambda f: (SEVERITY_ORDER[f.severity], f.criterionId, f.resourceId or ""),
    )
    if not failed:
        lines.append("No failed checks were observed.")
    else:
        lines.append("| Severity | Criterion | Resource | Type | Evidence path | Observed | Expected | Remediation |")
        lines.append("|---|---|---|---|---|---|---|---|")
        for f in failed:
            lines.append(_finding_row(f))
    unknown = [f for f in a.findings if f.state == "unknown"]
    lines.append("")
    lines.append(f"## Unknown ({len(unknown)})")
    lines.append("")
    if unknown:
        lines.append("| Criterion | Resource | Reason |")
        lines.append("|---|---|---|")
        for f in sorted(unknown, key=lambda f: (f.criterionId, f.resourceId or "")):
            lines.append(f"| {f.criterionId} | {_cell(f.resourceName or '(estate)')} | {_cell(f.reason)} |")
    else:
        lines.append("Every applicable check could be assessed from the export.")
    lines.append("")
    lines.append("## What this export cannot show")
    lines.append("")
    for u in a.unknown_by_design:
        extra = f" (criteria: {', '.join(u.criteria)})" if u.criteria else ""
        lines.append(f"- **{u.topic}**: {u.reason}{extra}")
    lines.append("")
    lines.append("## Attribution")
    lines.append("")
    attribution = (
        catalog.attribution
        if catalog
        else [
            "Criteria are paraphrased from the FinOps Foundation Framework (finops.org) and the Microsoft Azure "
            "Well-Architected Framework (learn.microsoft.com).",
            "This project is not affiliated with or endorsed by the FinOps Foundation or Microsoft.",
        ]
    )
    lines.extend(f"- {line}" for line in attribution)
    lines.append("")
    return "\n".join(lines)


def _finding_row(f: Finding) -> str:
    return (
        f"| {f.severity} | {f.criterionId} | {_cell(f.resourceName or '(estate)')} | {_cell(f.resourceType or '')} "
        f"| {_cell(f.evidence.path or '')} | {_cell(f.evidence.observed)} | {_cell(f.evidence.expected)} "
        f"| {_cell(f.remediation)} |"
    )
