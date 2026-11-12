"""Every workflow step that runs Node.js or Python comes after the job chose its version (HCW-HybridCloudWorks#1707).

A job that runs `python`, `pip` or `uv` without actions/setup-python, or `node`, `npm` or `npx` without
actions/setup-node, gets whatever the runner image ships. On ubuntu-26.04 in November 2026 that was Python 3.14 and
Node.js 24, both below the HCW floors (Python 3.15, Node.js 26). Nothing else would notice: a job that names no version
has no version for a reviewer to read. `uv` counts as Python, because uv runs the interpreter it finds on the runner.

A command counts when it is in command position on a line of a `run:` step: at the start, after `$(`, `<(`, a
backtick, `(`, `{`, `|`, `&&`, `||` or `;`, after leading `NAME=value` assignments, or after a word that runs the next
one (`env`, `sudo`, `xargs`, `exec`, `time`, `!`, `if`, `then`, `do` and the like). It does not count inside a quoted
string (unless a double-quoted string runs a command with `$(`, `<(` or a backtick), on a comment line, or as an
argument (`docker run img python ...`). The set-up step must come before the first such step. Limits, on purpose: a job
that runs in a `container:` uses that image's runtime and is not checked; and a script a step calls (`bash
scripts/x.sh`) is not read.

A set-up step with its own `if:` may be skipped while a later command still runs on the runner's own interpreter
(Copilot on HCW-NetworkEyes_AddOn#100), so it covers a later step only when that step's `if:` is the same condition,
or is one of the terms the set-up's condition joins with a top-level `||` (whenever that step runs, so did the
set-up). Conditions are compared without a surrounding `${{ }}`, with runs of spaces made one, and a term without one
pair of parentheses around the whole of it. A set-up step with no `if:` covers every later step. A job's own `if:`
does not matter here, because it decides whether every step of the job runs, alike.

Each set-up step must also ask for the floor or newer (Copilot on HCW-CloudCrawler_App#81): `python-version` or
`python-version-file`, `node-version` or `node-version-file`, read through `${{ env.X }}` (the step's, job's or
workflow's `env:`), `${{ matrix.X }}` (every entry of the job's matrix list) and the named file. A value this test
cannot work out fails it, naming the step, rather than passing unchecked.

Ported from scripts/workflow-runtime-setup.test.mjs in HCW-HybridCloudWorks.
"""

import re
from pathlib import Path

import pytest
import yaml

from ..conftest import ROOT

WORKFLOWS = sorted([*(ROOT / ".github" / "workflows").glob("*.yml"), *(ROOT / ".github" / "workflows").glob("*.yaml")])
ACTIONS = sorted((ROOT / ".github" / "actions").glob("*/action.y*ml"))

# Steps that use the runner's own interpreter on purpose, keyed "file > job > step name > runtime", each with a reason
# a reviewer can check. Keyed by step, not job, so a new step in the same job is still checked. Empty today: every job
# that runs Python sets it up first, and no workflow runs Node.js.
RUNNER_DEFAULT_ALLOWED: dict[str, str] = {}

# Where a command may start: the line's start or an opening or joining character, then any `NAME=value` assignments and
# words that run the next word (`env FOO=1 node`, `sudo node`, `if node ...; then`).
START = (
    r"(?:^|[$<]\(\s*|`\s*|[({|;&]\s*)"
    r"(?:[A-Za-z_][A-Za-z0-9_]*=\S*\s+|(?:env|sudo|xargs|exec|time|nice|command|if|then|else|elif|do|while|until|!)\s+)*"
)
COMMAND = {
    "node": re.compile(START + r"(?:node|npm|npx)(?=\s|$)"),
    "python": re.compile(START + r"(?:python(?:3(?:\.\d+)?)?|pip3?|uv)(?=\s|$)"),
}
SETUP = {"node": re.compile(r"^actions/setup-node@"), "python": re.compile(r"^actions/setup-python@")}

# The lowest versions a set-up step may ask for. The program's floors are kept in scripts/version-floors.json in
# HCW-HybridCloudWorks; change them there first, then here.
PYTHON_FLOOR = (3, 15)
NODE_FLOOR = 26
# The set-up step's inputs that name the version, directly or through a file in the repository.
VERSION_INPUTS = {"python": ("python-version", "python-version-file"), "node": ("node-version", "node-version-file")}


def _without_quoted_text(line: str) -> str:
    """The line with the text of its quoted strings taken out, so words in a message (`echo "...; if pip named..."`) do
    not count. A double-quoted string that runs a command (`"$(python x)"`, or the older "`python x`") is kept. An
    escaped backtick (`\\``, as in Markdown written to the step summary) is a plain character, so it is dropped
    first."""
    line = re.sub(r"'[^']*'", "''", line.replace("\\`", ""))
    return re.sub(r'"(?:[^"\\]|\\.)*"', lambda m: m.group(0) if re.search(r"[$<]\(|`", m.group(0)) else '""', line)


def runs_runtime(run, kind: str) -> bool:
    """True when a run step calls the runtime in command position on a line that is not a comment."""
    for raw in str(run or "").split("\n"):
        line = raw.strip()
        if line and not line.startswith("#") and COMMAND[kind].search(_without_quoted_text(line)):
            return True
    return False


def _text(value) -> str:
    """A YAML value as the text written in the file: `false` stays `false`, not Python's `False`."""
    return ("true" if value else "false") if isinstance(value, bool) else str(value if value is not None else "")


def _normalized(expression: str) -> str:
    """An `if:` expression without a surrounding `${{ }}` and with runs of spaces made one."""
    text = expression.strip()
    wrapped = re.fullmatch(r"\$\{\{(.*)\}\}", text, re.DOTALL)
    return " ".join((wrapped.group(1) if wrapped else text).split())


def _without_outer_parentheses(term: str) -> str:
    """The term without one pair of parentheses, when that pair encloses the whole of it."""
    if not (term.startswith("(") and term.endswith(")")):
        return term
    depth = 0
    for index, char in enumerate(term):
        depth += {"(": 1, ")": -1}.get(char, 0)
        if depth == 0 and index < len(term) - 1:
            return term
    return term[1:-1].strip()


def _top_level_or_terms(expression: str) -> list[str]:
    """The terms an expression joins with `||` outside parentheses and quotes, each without one pair of parentheses
    around the whole of it; a one-item list when there is no such `||`."""
    terms, depth, quote, start, index = [], 0, "", 0, 0
    while index < len(expression):
        char = expression[index]
        if quote:
            quote = "" if char == quote else quote
        elif char in "'\"":
            quote = char
        elif char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        elif depth == 0 and expression.startswith("||", index):
            terms.append(expression[start:index])
            start = index + 2
            index += 1
        index += 1
    terms.append(expression[start:])
    return [_without_outer_parentheses(term.strip()) for term in terms]


def condition(step: dict) -> str:
    """A step's `if:` as one comparable expression ("" when it has none)."""
    return _normalized(_text(step.get("if")))


def covers(setup: dict, step: dict) -> bool:
    """True when a set-up step runs whenever the later step does: it has no `if:`, the same `if:`, or an `if:` whose
    top-level `||` terms include the later step's."""
    wanted, given = condition(step), condition(setup)
    return given in ("", wanted) or wanted in _top_level_or_terms(given)


def _steps_of(jobs: dict):
    """Each job that has a list of steps, as (name, job, steps)."""
    for name, job in (jobs or {}).items():
        steps = job.get("steps") if isinstance(job, dict) else None
        if isinstance(steps, list):
            yield name, job, steps


def unset_steps(file: str, jobs: dict) -> list[str]:
    """The steps that run a runtime before (or without) setting it up, as "file > job > step > runtime". A step needs
    an earlier set-up step that covers it (see `covers`)."""
    found = []
    for name, job, steps in _steps_of(jobs):
        if job.get("container"):
            continue
        for kind in COMMAND:
            for i, step in enumerate(steps):
                if not runs_runtime(step.get("run"), kind):
                    continue
                if not any(SETUP[kind].search(str(s.get("uses") or "")) and covers(s, step) for s in steps[:i]):
                    found.append(f"{file} > {name} > {step.get('name') or f'step {i + 1}'} > {kind}")
    return found


def _resolved(value, step: dict, job: dict, env: dict, depth: int = 0) -> list[str] | None:
    """The plain values an input stands for: itself, or what `${{ env.X }}` (the step's, job's or workflow's `env:`) or
    `${{ matrix.X }}` (every entry of the job's matrix list) holds. None when it cannot be worked out here."""
    text = _text(value).strip()
    found = re.fullmatch(r"\$\{\{\s*(env|matrix)\.([A-Za-z0-9_-]+)\s*\}\}", text)
    if not found:
        return None if "${{" in text else [text]
    source, name = found.groups()
    if source == "env":
        scope = {**env, **(job.get("env") or {}), **(step.get("env") or {})}
        return _resolved(scope[name], step, job, env, depth + 1) if name in scope and depth < 5 else None
    matrix = (job.get("strategy") or {}).get("matrix") or {}
    values = matrix.get(name) if isinstance(matrix, dict) and "include" not in matrix else None
    return [_text(v) for v in values] if isinstance(values, list) and values else None


def requested_versions(step: dict, job: dict, env: dict, root: Path = ROOT) -> list[str] | None:
    """The versions a set-up step asks for, read through `env`, `matrix` and a version file; None when unreadable."""
    direct, from_file = VERSION_INPUTS["python" if SETUP["python"].search(str(step.get("uses") or "")) else "node"]
    given = step.get("with") or {}
    if direct in given:
        return _resolved(given[direct], step, job, env)
    if from_file not in given:
        return None
    paths = _resolved(given[from_file], step, job, env) or []
    if len(paths) != 1 or not (root / paths[0]).is_file():
        return None
    lines = (line.strip() for line in (root / paths[0]).read_text(encoding="utf-8").splitlines())
    return [line for line in lines if line and not line.startswith("#")] or None


def _below_floor(version: str, kind: str) -> bool | None:
    """True when the version is under the floor, False when at or above it, None when it is not a version number."""
    if kind == "python":
        found = re.match(r"(\d+)\.(\d+)(?!\d)", version)
        return None if not found else (int(found.group(1)), int(found.group(2))) < PYTHON_FLOOR
    found = re.match(r"v?(\d+)(?!\d)", version)
    return None if not found else int(found.group(1)) < NODE_FLOOR


def floor_problems(file: str, jobs: dict, env: dict | None = None, root: Path = ROOT) -> list[str]:
    """Every set-up step that asks for a version below the floor, or one this test cannot read, with the reason."""
    problems = []
    for name, job, steps in _steps_of(jobs):
        for i, step in enumerate(steps):
            for kind in COMMAND:
                if not SETUP[kind].search(str(step.get("uses") or "")):
                    continue
                label = f"{file} > {name} > {step.get('name') or f'step {i + 1}'} > {kind}"
                versions = requested_versions(step, job, env or {}, root)
                if not versions:
                    problems.append(f"{label}: cannot work out the version it asks for")
                for version in versions or []:
                    below = _below_floor(version, kind)
                    if below is None:
                        problems.append(f"{label}: {version!r} is not a version number this test can compare")
                    elif below:
                        problems.append(f"{label}: asks for {version}, below the floor")
    return problems


def _every_file() -> list[tuple[str, dict, dict]]:
    """Each workflow and composite action as (label, jobs, workflow env)."""
    files = []
    for path in WORKFLOWS:
        workflow = yaml.safe_load(path.read_text(encoding="utf-8"))
        files.append((path.name, workflow.get("jobs"), workflow.get("env") or {}))
    for path in ACTIONS:
        # A composite action's steps run in the caller's job, but the action is checked on its own: whatever it runs
        # must be set up inside it, because a caller cannot be relied on to have done it.
        runs = yaml.safe_load(path.read_text(encoding="utf-8")).get("runs") or {}
        if runs.get("using") == "composite":
            files.append((f"{path.parent.name}/{path.name}", {"runs": runs}, {}))
    return files


def _all_unset() -> list[str]:
    return [entry for file, jobs, _ in _every_file() for entry in unset_steps(file, jobs)]


@pytest.mark.parametrize(
    "line",
    [
        "token=$(node scripts/github-app-token.mjs)",
        "npm ci --no-audit",
        "FOO=1 node x",
        "env FOO=1 node x",
        "sudo node x",
        "xargs node x",
        "diff a <(node x)",
        "(node x)",
        "if node x; then",
        "! node x",
        "time node x",
        "exec node x",
        "cd y && npm ci",
        'token="$(node scripts/github-app-token.mjs)"',
        'echo "`node --version`"',
    ],
)
def test_node_in_command_position_counts(line):
    assert runs_runtime(line, "node")


@pytest.mark.parametrize(
    "line",
    [
        "cat x | python3 -I check.py",
        "python3.15 -I x.py",
        "python -m pip install uv",
        "pip install x",
        "uv sync --frozen",
        "cd y && uv run pytest",
        "CA_SCOPES=/subscriptions/x uv run python -m app",
        "version=`python3 scripts/check.py`",
        'echo "`python3 --version`"',
    ],
)
def test_python_in_command_position_counts(line):
    assert runs_runtime(line, "python")


@pytest.mark.parametrize(
    ("line", "kind"),
    [
        ('echo "run \\`node scripts/x.mjs\\` by hand"', "node"),
        ('docker run --rm img python -c "import azure"', "python"),
        ("/opt/az/bin/python3 -Im pip check", "python"),
        ("# node is not run here", "node"),
        ('for node in items["nodes"]:', "node"),
        ('echo "$NODE_VERSION"', "node"),
        ("nodes=3 nodejs-check", "node"),
        ('echo "the stage is wrong; if pip named the file differently, look"', "python"),
        ("uvicorn app:app", "python"),
        ("bash scripts/check-lockfiles.sh", "python"),
        ("echo 'literal `python3` text'", "python"),
    ],
)
def test_strings_arguments_and_comments_do_not_count(line, kind):
    assert not runs_runtime(line, kind)


def test_unset_steps_flags_late_or_missing_setup_and_skips_containers():
    jobs = {
        "late": {"steps": [{"name": "Early", "run": "node a.mjs"}, {"uses": "actions/setup-node@abc"}]},
        "none": {"steps": [{"run": "python3 b.py"}]},
        "uvOnly": {"steps": [{"uses": "astral-sh/setup-uv@abc"}, {"name": "Run", "run": "uv sync"}]},
        "good": {"steps": [{"uses": "actions/setup-python@abc"}, {"run": "uv sync && python3 b.py"}]},
        "boxed": {"container": "node:26", "steps": [{"run": "node a.mjs"}]},
    }
    assert unset_steps("x.yml", jobs) == [
        "x.yml > late > Early > node",
        "x.yml > none > step 1 > python",
        "x.yml > uvOnly > Run > python",
    ]


def test_a_set_up_step_with_its_own_condition_covers_only_steps_it_always_runs_before():
    py = {"uses": "actions/setup-python@abc"}
    node = {"uses": "actions/setup-node@abc"}
    jobs = {
        "skipped": {"steps": [{**py, "if": False}, {"name": "Run", "run": "python3 a.py"}]},
        "sameCondition": {
            "steps": [{**py, "if": "${{ !cancelled() }}"}, {"name": "Run", "if": "!cancelled()", "run": "python3 a.py"}]
        },
        "unconditionalSetup": {"steps": [py, {"name": "Run", "if": "failure()", "run": "python3 a.py"}]},
        "otherCondition": {
            "steps": [
                {**py, "if": "github.event_name == 'push'"},
                {"name": "Run", "if": "failure()", "run": "python3 a.py"},
            ]
        },
        "orTerm": {
            "steps": [
                {**node, "if": "matrix.relevant == 'true' || (matrix.name == 'scripts (operations)')"},
                {"name": "Run", "if": "matrix.name == 'scripts (operations)'", "run": "node a.mjs"},
            ]
        },
        "andTerm": {
            "steps": [
                {**node, "if": "matrix.relevant == 'true' && matrix.name == 'scripts'"},
                {"name": "Run", "if": "matrix.name == 'scripts'", "run": "node a.mjs"},
            ]
        },
        "jobCondition": {"if": "github.event_name == 'push'", "steps": [node, {"run": "node a.mjs"}]},
    }
    assert unset_steps("x.yml", jobs) == [
        "x.yml > skipped > Run > python",
        "x.yml > otherCondition > Run > python",
        "x.yml > andTerm > Run > node",
    ]


@pytest.mark.parametrize(
    ("setup", "step", "covered"),
    [
        ("${{  a &&   b }}", "a && b", True),
        ("a || b", "b", True),
        ("(a) || (b && c)", "b && c", True),
        ("x == 'p || q' || r", "x == 'p", False),
        ("(a || b) && c", "a", False),
        ("a || b", "a || c", False),
        ("", "anything", True),
    ],
)
def test_covers_compares_normalised_conditions_and_top_level_or_terms(setup, step, covered):
    assert covers({"if": setup}, {"if": step}) is covered


def test_a_set_up_step_must_ask_for_the_floor_or_newer(tmp_path):
    (tmp_path / ".python-version").write_text("# the line uv and setup-python read\n3.15\n", encoding="utf-8")
    (tmp_path / ".old-version").write_text("3.14\n", encoding="utf-8")
    workflow = yaml.safe_load(
        """
env: {PYTHON_VERSION: "3.15", OLD: "3.14"}
jobs:
  old:
    steps: [{uses: actions/setup-python@abc, with: {python-version: "3.14"}}]
  new:
    steps:
      - {uses: actions/setup-python@abc, with: {python-version: "3.15"}}
      - {uses: actions/setup-python@abc, with: {python-version-file: .python-version}}
      - {uses: actions/setup-python@abc, with: {python-version: "${{ env.PYTHON_VERSION }}"}}
      - {uses: actions/setup-node@abc, with: {node-version: 26, package-manager-cache: false}}
  old-node:
    steps: [{name: Node, uses: actions/setup-node@abc, with: {node-version: "24"}}]
  through-env:
    env: {PYTHON_VERSION: "${{ env.OLD }}"}
    steps:
      - {uses: actions/setup-python@abc, with: {python-version: "${{ env.PYTHON_VERSION }}"}}
      - {uses: actions/setup-python@abc, with: {python-version-file: .old-version}}
  matrix:
    strategy: {matrix: {python-version: ["3.15", "3.14"]}}
    steps: [{uses: actions/setup-python@abc, with: {python-version: "${{ matrix.python-version }}"}}]
  unreadable:
    steps:
      - {uses: actions/setup-python@abc}
      - {uses: actions/setup-node@abc, with: {node-version: "${{ inputs.node }}"}}
      - {uses: actions/setup-node@abc, with: {node-version: lts/*}}
"""
    )
    assert floor_problems("x.yml", workflow["jobs"], workflow["env"], tmp_path) == [
        "x.yml > old > step 1 > python: asks for 3.14, below the floor",
        "x.yml > old-node > Node > node: asks for 24, below the floor",
        "x.yml > through-env > step 1 > python: asks for 3.14, below the floor",
        "x.yml > through-env > step 2 > python: asks for 3.14, below the floor",
        "x.yml > matrix > step 1 > python: asks for 3.14, below the floor",
        "x.yml > unreadable > step 1 > python: cannot work out the version it asks for",
        "x.yml > unreadable > step 2 > node: cannot work out the version it asks for",
        "x.yml > unreadable > step 3 > node: 'lts/*' is not a version number this test can compare",
    ]


def test_every_set_up_step_asks_for_the_floor_or_newer():
    assert [problem for file, jobs, env in _every_file() for problem in floor_problems(file, jobs, env)] == []


def test_every_runtime_step_comes_after_its_setup():
    unset = _all_unset()
    assert [entry for entry in unset if entry not in RUNNER_DEFAULT_ALLOWED] == []


def test_every_allowed_exception_still_exists_and_has_a_reason():
    unset = _all_unset()
    for entry, reason in RUNNER_DEFAULT_ALLOWED.items():
        assert reason.strip(), f"{entry}: an exception needs a reason"
        assert entry in unset, f"{entry} no longer runs the runner's default; remove it from RUNNER_DEFAULT_ALLOWED"
