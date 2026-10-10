from __future__ import annotations

from pathlib import Path

import pytest
from cloud_assessor_core.catalog import load_catalog, load_scoring
from cloud_assessor_core.model import Check, Criterion, Resource, SourceRef

ROOT = Path(__file__).resolve().parents[3]
SAMPLES = ROOT / "samples"


@pytest.fixture(scope="session")
def catalog():
    return load_catalog()


@pytest.fixture(scope="session")
def scoring():
    return load_scoring()


@pytest.fixture
def make_resource():
    def _make(**overrides) -> Resource:
        base = {
            "id": "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/rg-a"
            "/providers/microsoft.containerservice/managedclusters/hcw-sample-aks",
            "name": "hcw-sample-aks",
            "type": "microsoft.containerservice/managedclusters",
            "location": "eastus2",
            "resource_group": "rg-a",
            "subscription_id": "00000000-0000-0000-0000-000000000001",
            "tags": {"costCenter": "cc-1", "owner": "o", "environment": "dev"},
            "properties": {"a": {"b": [{"c": 1}, {"c": 2}]}, "flag": True, "count": 3},
            "sku": {"name": "Base", "tier": "Free"},
            "identity": {"type": "SystemAssigned"},
            "source": SourceRef(format="arg-json", row=1),
        }
        base.update(overrides)
        return Resource(**base)

    return _make


@pytest.fixture
def make_criterion():
    def _make(checks: list[Check], **overrides) -> Criterion:
        base = {
            "id": "CA-ZT-099",
            "framework": "zero-trust",
            "pillar": "Network",
            "severity": "high",
            "resourceTypes": ["microsoft.containerservice/managedclusters"],
            "title": "t",
            "text": "x",
            "checks": checks,
            "remediation": "r",
            "learnUrl": "https://learn.microsoft.com/azure/aks/",
            "retrievedOn": "2026-10-10",
            "attribution": "a",
        }
        base.update(overrides)
        return Criterion(**base)

    return _make
