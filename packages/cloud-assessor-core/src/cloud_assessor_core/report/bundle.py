"""The output bundle: four files, zipped with STORE (no compression; the content is already small and textual)."""

from __future__ import annotations

import io
import zipfile

from cloud_assessor_core.model import Assessment, Catalog
from cloud_assessor_core.report.csvout import findings_csv
from cloud_assessor_core.report.jsonreport import to_json
from cloud_assessor_core.report.markdown import NOT_AN_AUDIT, render_markdown

BUNDLE_FILES = ("report.md", "report.json", "findings.csv", "NOT-AN-AUDIT.md")


def make_bundle(assessment: Assessment, catalog: Catalog | None = None) -> dict[str, bytes]:
    return {
        "report.md": render_markdown(assessment, catalog).encode("utf-8"),
        "report.json": to_json(assessment).encode("utf-8"),
        "findings.csv": findings_csv(assessment.findings).encode("utf-8"),
        "NOT-AN-AUDIT.md": NOT_AN_AUDIT.encode("utf-8"),
    }


def zip_bytes(files: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_STORED) as zf:
        for name in sorted(files):
            if name.startswith("/") or ".." in name.split("/"):
                raise ValueError("bundle paths must be relative and without '..'")
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_STORED
            zf.writestr(info, files[name])
    return buffer.getvalue()
