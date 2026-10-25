#!/usr/bin/env python
"""Documentation governance gate (README.md "Documentation", T-019, REFACTOR_APP.md 7.14 and 16).

Markdown is allowed only as the five root files, CLAUDE.md, the community-health files and platform templates under
.github/ (SECURITY, CONTRIBUTING, CODE_OF_CONDUCT, the pull request template), and the package
README that the cloud-assessor-core wheel metadata requires (adopted verbatim from the AddOn;
`readme = "README.md"`). Relative links inside the five root files must resolve (T-016; the wiki host is
excluded until T-030). Exits non-zero otherwise.

uv run python scripts/check-docs-governance.py            # validate (CI)
uv run python scripts/check-docs-governance.py --root DIR # validate another tree (tests)
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT_FILES = ("README.md", "CHANGELOG.md", "REVIEW.md", "TODO.md", "REFACTOR_APP.md")
ALLOWED = {
    # working agreement for AI coding agents; allow-listed by the owner on 2026-10-24
    "CLAUDE.md",
    ".github/SECURITY.md",
    # community health files GitHub itself reads from .github/ (ticket #32, CA-9; the allow-listing is confirmed by the
    # owner merging that pull request): the contributing guide and the code of conduct. Issue forms are YAML.
    ".github/CONTRIBUTING.md",
    ".github/CODE_OF_CONDUCT.md",
    ".github/PULL_REQUEST_TEMPLATE.md",
    ".github/pull_request_template.md",
    ".github/CODEOWNERS",
    # package metadata the wheel build requires, adopted verbatim from HCW-CloudAssessor_AddOn
    "packages/cloud-assessor-core/README.md",
}
ALLOWED_PREFIXES = (".github/ISSUE_TEMPLATE/",)
EXCLUDED_HOSTS = ("github.com/saulpatinojr/HCW-CloudAssessor_App/wiki",)
LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")


def tracked(root: Path) -> list[str]:
    try:
        out = subprocess.run(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
            cwd=root,
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        return [line for line in out.splitlines() if line]
    except subprocess.CalledProcessError, FileNotFoundError:
        return [p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file() and ".git" not in p.parts]


def check(root: Path) -> list[str]:
    problems: list[str] = []
    for rel in tracked(root):
        path = root / rel
        if not path.is_file():
            continue
        if path.suffix.lower() in {".md", ".markdown", ".rst"} or path.name.upper() == "README":
            if rel in ROOT_FILES or rel in ALLOWED or rel.startswith(ALLOWED_PREFIXES):
                continue
            problems.append(
                f"{rel}: markdown outside the five-file model; move it to the wiki (see README.md 'Documentation')"
            )
    for name in ROOT_FILES:
        path = root / name
        if not path.is_file():
            if name != "REFACTOR_APP.md":  # retired at v0.1.0 (moves to the wiki page Implementation-Plan)
                problems.append(f"{name}: missing root document")
            continue
        for target in LINK.findall(path.read_text(encoding="utf-8")):
            if target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            target = target.split("#", 1)[0]
            if not target or (root / target).exists():
                continue
            problems.append(f"{name}: link target {target!r} does not exist")
    return problems


def main(argv: list[str]) -> int:
    root = Path(__file__).resolve().parents[1]
    if "--root" in argv:
        root = Path(argv[argv.index("--root") + 1]).resolve()
    problems = check(root)
    for p in problems:
        print(f"ERROR: {p}", file=sys.stderr)
    if not problems:
        print(f"docs governance: {len(ROOT_FILES)} root files, no stray markdown, links resolve")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
