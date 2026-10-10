"""Scorecards per framework and pillar. Unknown lowers coverage, never score."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from cloud_assessor_core.catalog.loader import Scoring
from cloud_assessor_core.model import SEVERITY_WEIGHTS, Finding, Scorecard

WEIGHT_MIN, WEIGHT_MAX = 0.0, 10.0


def bounded_weights(scoring: Scoring, overrides: dict[str, dict[str, Any]] | None) -> dict[str, dict[str, float]]:
    """Pillar weights from scoring.json with request overrides clamped to [0, 10]; unknown keys are ignored."""
    weights = {fw: dict(spec.pillars) for fw, spec in scoring.frameworks.items()}
    for fw, pillars in (overrides or {}).items():
        if fw not in weights or not isinstance(pillars, dict):
            continue
        for pillar, value in pillars.items():
            if pillar not in weights[fw] or isinstance(value, bool) or not isinstance(value, int | float):
                continue
            weights[fw][pillar] = min(WEIGHT_MAX, max(WEIGHT_MIN, float(value)))
    return weights


def _card(
    framework: str, pillar: str | None, weight: float, findings: list[Finding], severity_weights: dict[str, int]
) -> Scorecard:
    observed = [f for f in findings if f.state == "observed"]
    unknown = sum(1 for f in findings if f.state == "unknown")
    not_applicable = sum(1 for f in findings if f.state == "not-applicable")
    passed = [f for f in observed if f.result == "pass"]
    failed = [f for f in observed if f.result == "fail"]
    w_obs = sum(severity_weights.get(f.severity, 1) for f in observed)
    w_pass = sum(severity_weights.get(f.severity, 1) for f in passed)
    score = round(100.0 * w_pass / w_obs, 1) if w_obs else None
    coverage = round(len(observed) / (len(observed) + unknown), 3) if (observed or unknown) else None
    return Scorecard(
        framework=framework,  # type: ignore[arg-type]
        pillar=pillar,
        weight=weight,
        observed=len(observed),
        **{"pass": len(passed), "fail": len(failed)},
        unknown=unknown,
        notApplicable=not_applicable,
        score=score,
        coverage=coverage,
    )


def score(
    findings: list[Finding], scoring: Scoring, overrides: dict[str, dict[str, Any]] | None = None
) -> list[Scorecard]:
    """One card per (framework, pillar) with findings, and one framework total (pillar None) per framework."""
    weights = bounded_weights(scoring, overrides)
    severity_weights = dict(SEVERITY_WEIGHTS)
    severity_weights.update(scoring.severityWeights)
    by_pillar: dict[tuple[str, str], list[Finding]] = defaultdict(list)
    for f in findings:
        by_pillar[(f.framework, f.pillar)].append(f)
    cards: list[Scorecard] = []
    for framework in scoring.frameworks:
        pillar_cards = [
            _card(
                framework, pillar, weights[framework].get(pillar, 1.0), by_pillar[(framework, pillar)], severity_weights
            )
            for pillar in weights[framework]
            if by_pillar.get((framework, pillar))
        ]
        fw_findings = [f for (fw, _), fs in by_pillar.items() if fw == framework for f in fs]
        total = _card(framework, None, 1.0, fw_findings, severity_weights)
        scored = [(c.weight, c.score) for c in pillar_cards if c.score is not None and c.weight > 0]
        weighted = round(sum(w * s for w, s in scored) / sum(w for w, _ in scored), 1) if scored else None
        total = total.model_copy(update={"score": weighted})
        cards.append(total)
        cards.extend(pillar_cards)
    return cards
