"""Build an Assessment from normalised resources: evaluate, score, summarise. The one entry point editions call."""

from __future__ import annotations

import uuid
from collections import Counter
from datetime import UTC, datetime
from typing import Any

from cloud_assessor_core import __version__
from cloud_assessor_core.catalog.loader import Scoring
from cloud_assessor_core.evaluate.engine import evaluate, unknown_by_design
from cloud_assessor_core.model import Assessment, Catalog, Resource, Summary
from cloud_assessor_core.score import score


def assess(
    resources: list[Resource],
    catalog: Catalog,
    scoring: Scoring,
    *,
    source_format: str,
    file_name: str | None = None,
    ingestion_warnings: list[str] | None = None,
    weights: dict[str, dict[str, Any]] | None = None,
    assessment_id: str | None = None,
    now: datetime | None = None,
) -> Assessment:
    findings = evaluate(resources, catalog)
    cards = score(findings, scoring, weights)
    states = Counter(f.state for f in findings)
    results = Counter(f.result for f in findings if f.result)
    summary = Summary(
        resourceCount=len(resources),
        byType=dict(sorted(Counter(r.type for r in resources).items())),
        criteriaCount=len(catalog.criteria),
        findingsCount=len(findings),
        observed=states.get("observed", 0),
        **{"pass": results.get("pass", 0), "fail": results.get("fail", 0)},
        unknown=states.get("unknown", 0),
        notApplicable=states.get("not-applicable", 0),
    )
    return Assessment(
        id=assessment_id or str(uuid.uuid4()),
        created_at=now or datetime.now(UTC),
        catalog_version=catalog.version,
        core_version=__version__,
        source_format=source_format,  # type: ignore[arg-type]
        file_name=file_name,
        summary=summary,
        scorecards=cards,
        findings=findings,
        unknown_by_design=unknown_by_design(catalog, findings),
        ingestion_warnings=list(ingestion_warnings or []),
    )
