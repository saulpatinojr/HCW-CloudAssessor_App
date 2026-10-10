import pytest
from cloud_assessor_core import MODEL_VERSION, __version__
from cloud_assessor_core.model import Catalog, Check, Criterion, Resource, SourceRef
from pydantic import ValidationError


def test_model_version_and_package_version():
    assert MODEL_VERSION == 1
    assert __version__ == "0.1.0"


def test_resource_lowercases_type_and_is_frozen():
    r = Resource(id="/x", name="n", type="Microsoft.Compute/Disks", source=SourceRef(format="arg-json", row=1))
    assert r.type == "microsoft.compute/disks"
    with pytest.raises(ValidationError):
        r.name = "other"  # type: ignore[misc]


def test_learn_url_host_allow_list(make_criterion):
    make_criterion([Check(kind="property-exists", path="p")], learnUrl="https://www.finops.org/framework/")
    with pytest.raises(ValidationError):
        make_criterion([Check(kind="property-exists", path="p")], learnUrl="https://example.com/")
    with pytest.raises(ValidationError):
        make_criterion([Check(kind="property-exists", path="p")], learnUrl="http://learn.microsoft.com/")


def test_criterion_id_pattern_and_unknown_fields(make_criterion):
    with pytest.raises(ValidationError):
        make_criterion([Check(kind="property-exists", path="p")], id="XX-1")
    with pytest.raises(ValidationError):
        Check(kind="property-exists", path="p", bogus=1)  # type: ignore[call-arg]


def test_catalog_rejects_duplicate_ids(make_criterion):
    c = make_criterion([Check(kind="property-exists", path="p")])
    with pytest.raises(ValidationError):
        Catalog(version="1.0.0", retrievedOn="2026-10-10", attribution=["a"], criteria=[c, c])


def test_when_alias_in():
    c = Criterion.model_validate(
        {
            "id": "CA-FIN-099",
            "framework": "finops",
            "pillar": "Allocation",
            "severity": "low",
            "resourceTypes": ["X/Y"],
            "title": "t",
            "text": "x",
            "checks": [{"kind": "property-exists", "path": "p"}],
            "when": {"path": "tags.environment", "in": ["dev"]},
            "remediation": "r",
            "learnUrl": "https://learn.microsoft.com/azure/",
            "retrievedOn": "2026-10-10",
            "attribution": "a",
        }
    )
    assert c.when is not None and c.when.in_ == ["dev"]
    assert c.resourceTypes == ["x/y"]
