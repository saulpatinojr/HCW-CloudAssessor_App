"""The data contract shared by every edition. MODEL_VERSION changes only when Resource changes."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

MODEL_VERSION = 1

Framework = Literal["finops", "waf-cost", "zero-trust"]
Severity = Literal["critical", "high", "medium", "low"]
State = Literal["observed", "unknown", "not-applicable"]
Result = Literal["pass", "fail"]
CheckKind = Literal["tag-present", "property-equals", "property-exists", "sku-in", "count-threshold", "cross-resource"]

SEVERITY_WEIGHTS: dict[str, int] = {"critical": 4, "high": 3, "medium": 2, "low": 1}
LEARN_URL_HOSTS: frozenset[str] = frozenset({"learn.microsoft.com", "www.finops.org"})


class SourceRef(BaseModel):
    """Where a resource came from: the export format and the 1-based row number (never cell content)."""

    model_config = ConfigDict(frozen=True)

    format: Literal["arg-json", "arg-csv", "arg-live"]
    row: int = Field(ge=0)
    has_properties: bool = True
    has_tags: bool = True


class Resource(BaseModel):
    """One normalised Resource Graph row."""

    model_config = ConfigDict(frozen=True)

    model_version: Literal[1] = MODEL_VERSION
    id: str
    name: str
    type: str
    location: str | None = None
    resource_group: str | None = None
    subscription_id: str | None = None
    tags: dict[str, str] = Field(default_factory=dict)
    properties: dict[str, Any] = Field(default_factory=dict)
    sku: dict[str, Any] | None = None
    identity: dict[str, Any] | None = None
    kind: str | None = None
    zones: list[str] | None = None
    source: SourceRef

    @field_validator("type")
    @classmethod
    def _lower_type(cls, value: str) -> str:
        return value.strip().lower()


class When(BaseModel):
    """Applicability clause: the criterion applies only when the path equals / is in the given values."""

    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)

    path: str
    equals: Any | None = None
    in_: list[Any] | None = Field(default=None, alias="in")


class Check(BaseModel):
    """One evaluator invocation. Only the fields its kind reads are meaningful; the schema keeps them explicit."""

    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)

    kind: CheckKind
    # tag-present
    keys: list[str] | None = None
    mode: Literal["any", "all"] = "all"
    # property-equals / property-exists / sku-in / count-threshold
    path: str | None = None
    equals: Any | None = None
    anyOf: list[Any] | None = None
    missingIs: Literal["unknown", "fail", "pass"] = "unknown"
    mustBe: Literal["present", "absent", "non-empty"] = "present"
    allowed: list[str] | None = None
    disallowed: list[str] | None = None
    # count-threshold
    scope: Literal["resource", "estate"] = "resource"
    metric: Literal["count", "percent-present", "value"] = "count"
    op: Literal[">=", "<=", ">", "<", "==", "!="] = ">="
    value: float | None = None
    # cross-resource
    relation: Literal["has-child", "estate-has", "has-sibling"] | None = None
    type: str | None = None
    where: When | None = None
    absentIs: Literal["unknown", "fail"] = "unknown"
    # free text for the unknown state, so the honesty is in the data
    unknownReason: str | None = None


class Criterion(BaseModel):
    """A paraphrased, attributed criterion. `text` is the single replaceable field (R-005)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(pattern=r"^CA-(FIN|WAF|ZT)-\d{3}$")
    framework: Framework
    pillar: str = Field(min_length=1)
    severity: Severity
    resourceTypes: list[str] = Field(min_length=1)
    title: str = Field(min_length=1)
    text: str = Field(min_length=1)
    checks: list[Check] = Field(min_length=1)
    anyPass: bool = False
    when: When | None = None
    remediation: str = Field(min_length=1)
    learnUrl: str
    verify: bool = True
    retrievedOn: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    attribution: str = Field(min_length=1)

    @field_validator("learnUrl")
    @classmethod
    def _learn_url_host(cls, value: str) -> str:
        from urllib.parse import urlsplit

        parts = urlsplit(value)
        if parts.scheme != "https" or parts.hostname not in LEARN_URL_HOSTS:
            raise ValueError(f"learnUrl host must be one of {sorted(LEARN_URL_HOSTS)}")
        return value

    @field_validator("resourceTypes")
    @classmethod
    def _lower_types(cls, value: list[str]) -> list[str]:
        return [v.strip().lower() for v in value]


class Catalog(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    retrievedOn: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    attribution: list[str] = Field(min_length=1)
    criteria: list[Criterion] = Field(min_length=1)

    @field_validator("criteria")
    @classmethod
    def _unique_ids(cls, value: list[Criterion]) -> list[Criterion]:
        seen: set[str] = set()
        for c in value:
            if c.id in seen:
                raise ValueError(f"duplicate criterion id {c.id}")
            seen.add(c.id)
        return value


class Evidence(BaseModel):
    model_config = ConfigDict(frozen=True)

    path: str | None = None
    observed: Any | None = None
    expected: Any | None = None


class Finding(BaseModel):
    model_config = ConfigDict(frozen=True)

    criterionId: str
    framework: Framework
    pillar: str
    severity: Severity
    resourceId: str | None
    resourceName: str | None
    resourceType: str | None
    state: State
    result: Result | None = None
    evidence: Evidence = Field(default_factory=Evidence)
    reason: str
    remediation: str
    learnUrl: str


class Scorecard(BaseModel):
    model_config = ConfigDict(frozen=True, populate_by_name=True)

    framework: Framework
    pillar: str | None  # None is the framework total
    weight: float
    observed: int
    passed: int = Field(alias="pass")
    failed: int = Field(alias="fail")
    unknown: int
    notApplicable: int
    score: float | None  # weighted pass / weighted observed x 100; None when nothing was observed
    coverage: float | None  # observed / (observed + unknown); None when nothing could be evaluated


class UnknownByDesign(BaseModel):
    model_config = ConfigDict(frozen=True)

    topic: str
    reason: str
    criteria: list[str] = Field(default_factory=list)


class Summary(BaseModel):
    model_config = ConfigDict(frozen=True, populate_by_name=True)

    resourceCount: int
    byType: dict[str, int]
    criteriaCount: int
    findingsCount: int
    observed: int
    passed: int = Field(alias="pass")
    failed: int = Field(alias="fail")
    unknown: int
    notApplicable: int


class Assessment(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    created_at: datetime
    model_version: Literal[1] = MODEL_VERSION
    catalog_version: str
    core_version: str
    source_format: Literal["arg-json", "arg-csv", "arg-live"]
    file_name: str | None = None
    summary: Summary
    scorecards: list[Scorecard]
    findings: list[Finding]
    unknown_by_design: list[UnknownByDesign]
    ingestion_warnings: list[str]
