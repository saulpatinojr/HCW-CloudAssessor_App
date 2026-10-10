"""Cloud Assessor engine: declarative criteria over a normalised Azure Resource Graph export.

Pure functions over the pydantic model. No HTTP framework, no cloud SDK, no network. The package is seeded in the
AddOn repository and moves upstream to HCW-CloudAssessor_App unchanged (ADR-0001).
"""

from cloud_assessor_core.model import MODEL_VERSION

__version__ = "0.1.0"

__all__ = ["MODEL_VERSION", "__version__"]
