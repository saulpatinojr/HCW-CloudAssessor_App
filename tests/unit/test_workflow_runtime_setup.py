"""Every workflow step that runs Node.js or Python comes after the job chose its version (HCW-HybridCloudWorks#1707).

A job that runs `python`, `pip` or `uv` without actions/setup-python, or `node`, `npm` or `npx` without
actions/setup-node, gets whatever the runner image ships. On ubuntu-26.04 in November 2026 that was Python 3.14 and
Node.js 24, both below the HCW floors (Python 3.15, Node.js 26). Nothing else would notice: a job that names no version
has no version for a reviewer to read. `uv` and `uvx` count as Python, because uv runs the interpreter it finds, the
runner's own unless one was set up; so astral-sh/setup-uv counts as setting Python up only when it is given a
`python-version` at or above the floor.

A command counts when it is in command position on a line of a `run:` step: at the start, after `$(`, `<(`, a backtick,
`(`, `{`, `|`, `&&`, `||` or `;`, after a `case` pattern at the start of a line (`check)`), after leading `NAME=value`
assignments (the value plain text, a quoted string, or both run together), or after a word that runs the next one
(`env`, `sudo`, `xargs`, `exec`, `time`, `nice`, `!`, `if`, `then`, `do` and the like) and that word's options (`sudo -u
nobody`, `env -i`). It counts with a path in front too (`/usr/bin/python3`, `./venv/bin/python`), because a path to the
runner's interpreter is still the runner's, and `python3.15.2` counts like `python3`. It does not count in a comment, a
heredoc's body, a quoted string (unless a double-quoted string runs a command with `$(`, `<(` or a backtick; a
single-quoted one may run over several lines, as a `docker run image bash -c '...'` script does) or as an argument
(`docker run image python ...`, or the first word of a line that continues the one before it). The set-up step must come
before the first such step. Limits, on purpose: a job that runs in a `container:` uses that image's runtime and is not
checked; and a script a step calls (`bash scripts/x.sh`) is not read, so a step whose script starts a runtime is listed
in INDIRECT_RUNTIME.

A set-up step with its own `if:` may be skipped while a later command still runs on the runner's own interpreter
(Copilot on HCW-NetworkEyes_AddOn#100), so it covers a later step only when that step's `if:` is the same condition, or
is one of the terms the set-up's condition joins with a top-level `||` (whenever that step runs, so did the set-up).
Conditions are compared without a surrounding `${{ }}`, with runs of spaces made one, and a term without one pair of
parentheses around the whole of it. A set-up step with no `if:` covers every later step whose condition does not test
the job's status. A job's own `if:` does not matter here, because it decides whether every step of the job runs, alike.

The job's status is compared on its own. Without `always()`, `failure()`, `cancelled()` or `success()` in it, a step's
condition includes an unwritten `success()`, so a set-up step with no `if:` is skipped once an earlier step has failed,
while a later `if: always()`, `failure()` or `!cancelled()` step still runs (Copilot on HCW-CloudAssessor_App#97). So
after each job status (success, a failure, a cancel) a later step may run after, its set-up step must surely run, or
depend on the same thing by the rule above, applied to the conditions with their status-only `&&` terms taken out. `||`,
`&&`, `!` and parentheses are followed: `always() && !cancelled()` runs after success and failure, not after a cancel.

Each set-up step must also ask for the floor or newer (Copilot on HCW-CloudCrawler_App#81): `python-version` or
`python-version-file`, `node-version` or `node-version-file`, read through `${{ env.X }}` (the step's, job's or
workflow's `env:`), `${{ matrix.X }}` (every entry of the job's matrix list) and the named file. A version that names a
line only (`26`, `26.x`, `3.15`) stands for that line's newest release, so it passes when the line is at or above the
floor's; an exact version (`26.10.0`) must be at or above the floor itself; anything else (`26.11.0-rc.1`, `26.11.0.0`,
`lts/*`) cannot be compared. A value this test cannot work out fails it, naming the step, rather than passing unchecked.

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

# Steps that start a runtime through a script they run, which the command check cannot see in the `run:` text. Each
# counts as running that runtime, so its set-up step must come first. Same keys, each with a reason.
INDIRECT_RUNTIME: dict[str, str] = {
    "ci.yml > lint > uv.lock matches pyproject.toml and both requirements exports > python": (
        "`bash scripts/check-lockfiles.sh` runs `uv lock --check`, then scripts/export-lockfiles.sh (`uv export`)"
    ),
    "dependabot-lockfiles.yml > export > Regenerate both exports from uv.lock > python": (
        "`bash scripts/export-lockfiles.sh` runs `uv export`"
    ),
}

# Where a command may start: the line's start or an opening or joining character, then any `NAME=value` assignments
# (the value plain text, a quoted string, or both run together: `FOO="a b"`) and words that run the next word
# (`env FOO=1 node`, `sudo node`, `if node ...; then`).
ASSIGNMENT = r"""[A-Za-z_][A-Za-z0-9_]*=(?:"(?:[^"\\]|\\.)*"|'[^']*'|[^\s"'])*\s+"""
# Words that run the next word, each with the options it may take first: the letters of the options that take an
# argument (`sudo -u nobody`, `nice -n 10`), and any other `-x`/`--long` flag. `command` only with `-p`, because
# `command -v node` looks node up and runs nothing.
WRAPPER_OPTIONS = {"env": "uCS", "sudo": "ugCDhprtU", "xargs": "InPLdaEs", "exec": "a", "time": "of", "nice": "n"}
WRAPPERS = "|".join(
    [
        rf"{word}(?:\s+(?:-[A-Za-z]*[{takes}]\s*[^\s-]\S*|--?\w[\w-]*(?:=\S+)?))*\s+"
        for word, takes in WRAPPER_OPTIONS.items()
    ]
    + [r"command(?:\s+-p)*\s+", r"(?:if|then|else|elif|do|while|until|!)\s+"]
)
# A `case` pattern that ends at the start of a line (`check)`, `a|b)`), after which a command may follow.
CASE_PATTERN = r"^[^()\s|]+(?:\|[^()\s|]+)*\)\s*"
START = r"(?:^|[$<]\(\s*|`\s*|[({|;&]\s*|" + CASE_PATTERN + r")(?:" + ASSIGNMENT + "|" + WRAPPERS + r")*"
# A runtime may be named with a path in front (`/usr/bin/python3`, `./venv/bin/python`): a path to the runner's own
# interpreter is still the runner's. The path holds no `=`, so an assignment (`NODE=/x/node`) is not a command.
PATH = r"(?:[^\s=]*/)?"
COMMAND = {
    "node": re.compile(START + PATH + r"(?:node|npm|npx)(?=\s|$)"),
    "python": re.compile(START + PATH + r"(?:python(?:3(?:\.\d+){0,2})?|pip3?|uvx?)(?=\s|$)"),
}
SETUP = {"node": re.compile(r"^actions/setup-node@"), "python": re.compile(r"^actions/setup-python@")}
# astral-sh/setup-uv sets Python up only when given a `python-version` (see `sets_up`).
SETUP_UV = re.compile(r"^astral-sh/setup-uv@")

# The lowest versions a set-up step may ask for. The program's floors are kept in scripts/version-floors.json in
# HCW-HybridCloudWorks; change them there first, then here.
PYTHON_FLOOR = (3, 15, 0)
NODE_FLOOR = (26, 11, 0)
FLOORS = {"python": PYTHON_FLOOR, "node": NODE_FLOOR}
# The job statuses a step can run after, and the status functions that name them.
STATUSES = {"success", "failure", "cancelled"}
STATUS_CALL = re.compile(r"(!?)\s*\b(always|failure|cancelled|success)\(\s*\)")
# The set-up step's inputs that name the version, directly or through a file in the repository.
VERSION_INPUTS = {"python": ("python-version", "python-version-file"), "node": ("node-version", "node-version-file")}


def _shell_text(run: str) -> str:
    """The script as the shell reads it, for finding commands: comments and heredoc bodies dropped, a line that ends
    in `\\` joined to the next (so the next line's first word is still an argument), single-quoted text emptied, and
    double-quoted text emptied unless it runs a command (`"$(node x)"`, or the older "`node x`"). An escaped backtick
    (`\\``, as in Markdown written to the step summary) is a plain character. A quoted string may run over several
    lines, as the script of `docker run image bash -c '...'` does; what it runs is the container's, not the runner's."""
    out: list[str] = []
    heredocs: list[str] = []
    i, n = 0, len(run)
    while i < n:
        char = run[i]
        if char == "\\" and i + 1 < n:
            out.append(" " if run[i + 1] == "\n" else "" if run[i + 1] == "`" else run[i : i + 2])
            i += 2
        elif char == "'":
            end = run.find("'", i + 1)
            out.append("''")
            i = n if end == -1 else end + 1
        elif char == '"':
            j, body = i + 1, []
            while j < n and run[j] != '"':
                step = 2 if run[j] == "\\" and j + 1 < n else 1
                body.append("" if run[j : j + 2] == "\\`" else run[j : j + step])
                j += step
            text = "".join(body)
            out.append(f'"{text}"' if re.search(r"[$<]\(|`", text) else '""')
            i = j + 1
        elif char == "#" and (i == 0 or run[i - 1] in " \t\n;"):
            end = run.find("\n", i)
            i = n if end == -1 else end
        elif run.startswith("<<", i) and not run.startswith("<<<", i):
            found = re.match(r"<<-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1", run[i:])
            if found:
                heredocs.append(found.group(2))
            out.append("<<")
            i += len(found.group(0)) if found else 2
        elif char == "\n" and heredocs:
            out.append("\n")
            i += 1
            for delimiter in heredocs:
                while i < n:
                    end = run.find("\n", i)
                    end = n if end == -1 else end
                    line, i = run[i:end], end + 1
                    if line.strip() == delimiter:
                        break
            heredocs = []
        else:
            out.append(char)
            i += 1
    return "".join(out)


def runs_runtime(run, kind: str) -> bool:
    """True when a run script calls the runtime in command position (see `_shell_text` for what is left out)."""
    return any(COMMAND[kind].search(line.strip()) for line in _shell_text(str(run or "")).split("\n"))


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


def _top_level_terms(expression: str, operator: str = "||", unwrap: bool = True) -> list[str]:
    """The terms an expression joins with `||` (or `&&`) outside parentheses and quotes, each without one pair of
    parentheses around the whole of it (unless `unwrap` is false); a one-item list when there is no such operator."""
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
        elif depth == 0 and expression.startswith(operator, index):
            terms.append(expression[start:index])
            start = index + len(operator)
            index += len(operator) - 1
        index += 1
    terms.append(expression[start:])
    return [_without_outer_parentheses(term.strip()) if unwrap else term.strip() for term in terms]


def condition(step: dict) -> str:
    """A step's `if:` as one comparable expression ("" when it has none)."""
    return _normalized(_text(step.get("if")))


def _status_value(expression: str, status: str) -> bool | None:
    """Whether a condition holds after the job so far ended in `status` (success, failure or cancelled): True, False,
    or None when it also depends on something else (`steps.x.outputs.y == 'true'`). `||`, `&&`, `!` and parentheses
    are followed, so `always() && !cancelled()` holds after success and failure only; anything that is not a status
    function or `true`/`false` is unknown."""
    text = expression.strip()
    while (unwrapped := _without_outer_parentheses(text)) != text:
        text = unwrapped
    for operator, decides in (("||", True), ("&&", False)):
        terms = _top_level_terms(text, operator, unwrap=False)
        if len(terms) > 1:
            values = [_status_value(term, status) for term in terms]
            return decides if decides in values else None if None in values else not decides
    if text.startswith("!") and not text.startswith("!="):
        value = _status_value(text[1:], status)
        return None if value is None else not value
    call = re.fullmatch(r"(always|failure|cancelled|success)\(\s*\)", text)
    if call:
        return call.group(1) in ("always", status)
    return {"true": True, "false": False}.get(text)


def _runs_after(expression: str, status: str) -> bool | None:
    """`_status_value` of a step's whole condition, with GitHub's unwritten `success() &&` in front of one that names
    no status function (and of no condition at all)."""
    if not STATUS_CALL.search(expression) and status != "success":
        return False
    return _status_value(expression, status) if expression else True


def statuses(expression: str) -> set[str]:
    """The job statuses a step with this condition may run after (`success` alone for no status function)."""
    return {status for status in STATUSES if _runs_after(expression, status) is not False}


def _without_status(expression: str) -> str:
    """The condition without its top-level `&&` terms that test only the job's status (`always()`, `!cancelled()`)."""
    terms = _top_level_terms(expression, "&&", unwrap=False)
    kept = [term for term in terms if re.sub(r"[\s!()&|]", "", STATUS_CALL.sub("", term))]
    return expression if len(kept) == len(terms) else " && ".join(kept)


def _conditions_cover(given: str, wanted: str) -> bool:
    """True when a set-up step with condition `given` runs whenever a later step with condition `wanted` does: after
    every job status the later step may run after, the set-up step surely runs, or its condition depends on the same
    thing (status terms aside: the same condition, or one of the terms it joins with a top-level `||`)."""
    for status in sorted(STATUSES):
        if _runs_after(wanted, status) is False:
            continue
        runs = _runs_after(given, status)
        if runs is False:
            return False
        if runs is None:
            rest, need = _without_status(given), _without_status(wanted)
            if not (rest in ("", need) or need in _top_level_terms(rest, "||")):
                return False
    return True


def covers(setup: dict, step: dict) -> bool:
    """True when a set-up step runs whenever the later step does: it runs after every job status the later step can
    run after, and, status terms aside, it has no `if:`, the same `if:`, or an `if:` whose top-level `||` terms
    include the later step's."""
    return _conditions_cover(condition(setup), condition(step))


def _steps_of(jobs: dict):
    """Each job that has a list of steps, as (name, job, steps)."""
    for name, job in (jobs or {}).items():
        steps = job.get("steps") if isinstance(job, dict) else None
        if isinstance(steps, list):
            yield name, job, steps


def step_key(file: str, job: str, step: dict, i: int, kind: str) -> str:
    return f"{file} > {job} > {step.get('name') or f'step {i + 1}'} > {kind}"


def unset_steps(
    file: str, jobs: dict, env: dict | None = None, indirect: dict[str, str] | None = None, root: Path = ROOT
) -> list[str]:
    """The steps that run a runtime before (or without) setting it up, as "file > job > step > runtime". A step needs
    an earlier set-up step that covers it (see `sets_up` and `covers`). A step named in `indirect` counts as running
    its runtime even when its `run:` text does not show it."""
    indirect = INDIRECT_RUNTIME if indirect is None else indirect
    found = []
    for name, job, steps in _steps_of(jobs):
        if job.get("container"):
            continue
        for kind in COMMAND:
            for i, step in enumerate(steps):
                key = step_key(file, name, step, i, kind)
                if not (runs_runtime(step.get("run"), kind) or key in indirect):
                    continue
                if not any(sets_up(s, job, kind, env or {}, root) and covers(s, step) for s in steps[:i]):
                    found.append(key)
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


def is_set_up(step: dict, kind: str) -> bool:
    """True for a step that sets the runtime up: actions/setup-node or actions/setup-python, or, for Python,
    astral-sh/setup-uv given a `python-version`."""
    uses = str(step.get("uses") or "")
    if kind == "python" and SETUP_UV.search(uses):
        return "python-version" in (step.get("with") or {})
    return bool(SETUP[kind].search(uses))


def sets_up(step: dict, job: dict, kind: str, env: dict, root: Path = ROOT) -> bool:
    """True when the step chooses the runtime for the steps after it. setup-uv counts only with a `python-version` at
    or above the floor (a lower one is also reported by the floor test); without one uv uses the runner's Python."""
    if not is_set_up(step, kind):
        return False
    if not SETUP_UV.search(str(step.get("uses") or "")):
        return True
    versions = requested_versions(step, job, env, kind, root)
    return bool(versions) and all(_below_floor(version, kind) is False for version in versions)


def requested_versions(step: dict, job: dict, env: dict, kind: str, root: Path = ROOT) -> list[str] | None:
    """The versions a set-up step asks for, read through `env`, `matrix` and a version file; None when unreadable."""
    direct, from_file = VERSION_INPUTS[kind]
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
    """True when the version is under the floor, False when at or above it, None when it is not one of the forms this
    test reads: `N`, `N.x` and `N.M` name a line and mean its newest release, so only their numbers are compared with
    the floor's (`26` with 26, `3.15` with 3.15); `N.M.P` is exact and compared in full. Anything else, trailing text
    included (`26.11.0-rc.1`, `26.11.0.0`, `lts/*`), is None, so the floor test names the step."""
    found = re.fullmatch(r"v?(\d+)(?:\.x|\.(\d+)(?:\.(\d+))?)?", version.strip())
    if not found:
        return None
    numbers = tuple(int(number) for number in found.groups() if number is not None)
    return numbers < FLOORS[kind][: len(numbers)]


def floor_problems(file: str, jobs: dict, env: dict | None = None, root: Path = ROOT) -> list[str]:
    """Every set-up step that asks for a version below the floor, or one this test cannot read, with the reason."""
    problems = []
    for name, job, steps in _steps_of(jobs):
        for i, step in enumerate(steps):
            for kind in COMMAND:
                if not is_set_up(step, kind):
                    continue
                label = step_key(file, name, step, i, kind)
                versions = requested_versions(step, job, env or {}, kind, root)
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
    return [entry for file, jobs, env in _every_file() for entry in unset_steps(file, jobs, env)]


@pytest.mark.parametrize(
    "line",
    [
        "token=$(node scripts/github-app-token.mjs)",
        "npm ci --no-audit",
        "FOO=1 node x",
        "env FOO=1 node x",
        "env FOO='bar baz' node x.js",
        "FOO=\"a b\"'c d'e node x.js",
        "/opt/node/bin/node x.js",
        "env -i npm ci",
        "nice -n 10 node x.js",
        "xargs -n 1 node",
        "a|b) node x.js ;;",
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
        "/usr/bin/python3 -I check.py",
        "/opt/az/bin/python3 -Im pip check",
        "./venv/bin/python x.py",
        "python3.15.2 -c 'print(1)'",
        "/usr/bin/python3 -c 'print(1)'",
        "env -i python3 check.py",
        "sudo -u nobody python3 check.py",
        "sudo -u runner python3 check.py",
        "time -p python3 check.py",
        "check) python3 scripts/check.py ;;",
        "docker run --rm img bash -c 'x' && python3 y.py",
        "CA_SCOPES=/subscriptions/x uv run python -m app",
        "version=`python3 scripts/check.py`",
        'echo "`python3 --version`"',
        'FOO="bar baz" python3 check.py',
        'STAMP="$(date +%s) run" python3 check.py',
        "uvx zizmor .github",
    ],
)
def test_python_in_command_position_counts(line):
    assert runs_runtime(line, "python")


@pytest.mark.parametrize(
    ("line", "kind"),
    [
        ('echo "run \\`node scripts/x.mjs\\` by hand"', "node"),
        ('docker run --rm img python -c "import azure"', "python"),
        ("# node is not run here", "node"),
        ('for node in items["nodes"]:', "node"),
        ('echo "$NODE_VERSION"', "node"),
        ("nodes=3 nodejs-check", "node"),
        ('echo "the stage is wrong; if pip named the file differently, look"', "python"),
        ("uvicorn app:app", "python"),
        ("bash scripts/check-lockfiles.sh", "python"),
        ("echo 'literal `python3` text'", "python"),
        ('FOO="python3 x" true', "python"),
        ("NODE_BIN=/opt/node/bin/node", "node"),
        ("command -v node", "node"),
        ("echo $(foo) python3 x", "python"),
        ("docker run --rm img bash -c '\n  /opt/az/bin/python3 -Im pip check\n'", "python"),
        ("docker run --rm img \\\n  /opt/az/bin/python3 -Im pip check", "python"),
        ("cat > x.txt <<'EOF'\npython3 is named here\nEOF", "python"),
        ("echo x # node y", "node"),
    ],
)
def test_strings_arguments_and_comments_do_not_count(line, kind):
    assert not runs_runtime(line, kind)


def test_unset_steps_flags_late_or_missing_setup_and_skips_containers():
    jobs = {
        "late": {"steps": [{"name": "Early", "run": "node a.mjs"}, {"uses": "actions/setup-node@abc"}]},
        "none": {"steps": [{"run": "python3 b.py"}]},
        "uvOnly": {"steps": [{"uses": "astral-sh/setup-uv@abc"}, {"name": "Run", "run": "uv sync"}]},
        "uvNew": {
            "steps": [{"uses": "astral-sh/setup-uv@abc", "with": {"python-version": "3.15"}}, {"run": "uv sync"}]
        },
        "uvOld": {
            "steps": [{"uses": "astral-sh/setup-uv@abc", "with": {"python-version": "3.14"}}, {"run": "uv sync"}]
        },
        "good": {"steps": [{"uses": "actions/setup-python@abc"}, {"run": "uv sync && python3 b.py"}]},
        "boxed": {"container": "node:26", "steps": [{"run": "node a.mjs"}]},
    }
    assert unset_steps("x.yml", jobs) == [
        "x.yml > late > Early > node",
        "x.yml > none > step 1 > python",
        "x.yml > uvOnly > Run > python",
        "x.yml > uvOld > step 2 > python",
    ]
    uv_jobs = {name: jobs[name] for name in ("uvNew", "uvOld")}
    assert floor_problems("x.yml", uv_jobs) == ["x.yml > uvOld > step 1 > python: asks for 3.14, below the floor"]


def test_a_set_up_step_with_its_own_condition_covers_only_steps_it_always_runs_before():
    py = {"uses": "actions/setup-python@abc"}
    node = {"uses": "actions/setup-node@abc"}
    jobs = {
        "skipped": {"steps": [{**py, "if": False}, {"name": "Run", "run": "python3 a.py"}]},
        "sameCondition": {
            "steps": [{**py, "if": "${{ !cancelled() }}"}, {"name": "Run", "if": "!cancelled()", "run": "python3 a.py"}]
        },
        "unconditionalSetup": {
            "steps": [py, {"name": "Run", "if": "github.ref == 'refs/heads/main'", "run": "python3 a.py"}]
        },
        "afterAFailure": {"steps": [py, {"name": "Run", "if": "always()", "run": "python3 a.py"}]},
        "afterAFailureSetUpToo": {
            "steps": [{**py, "if": "always()"}, {"name": "Run", "if": "failure()", "run": "python3 a.py"}]
        },
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
        "x.yml > afterAFailure > Run > python",
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
        # The job's status: a set-up step with no `if:` runs only after success (the unwritten `success()`).
        ("", "", True),
        ("", "always()", False),
        ("", "${{ !cancelled() }}", False),
        ("", "failure()", False),
        ("${{ !cancelled() }}", "${{ !cancelled() }}", True),
        ("always()", "failure()", True),
        ("always()", "cancelled()", True),
        ("!cancelled()", "always()", False),
        ("!cancelled()", "cancelled()", False),
        ("failure()", "", False),
        ("always() && a", "a", True),
        ("always() && a", "!cancelled() && a", True),
        ("a", "failure() && a", False),
        ("always()", "a || b", True),
        # Status functions joined by `&&` and `||` (Copilot on HCW-CloudAssessor_AddOn#89).
        ("always() && !cancelled()", "cancelled()", False),
        ("always() && !cancelled()", "failure()", True),
        ("failure() || cancelled()", "cancelled()", True),
        ("failure() || cancelled()", "", False),
        ("success() || failure()", "!cancelled()", True),
    ],
)
def test_covers_compares_normalised_conditions_and_top_level_or_terms(setup, step, covered):
    assert covers({"if": setup}, {"if": step}) is covered


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("", {"success"}),
        ("a", {"success"}),
        ("always()", {"success", "failure", "cancelled"}),
        ("!cancelled()", {"success", "failure"}),
        ("always() && !cancelled()", {"success", "failure"}),
        ("failure() || cancelled()", {"failure", "cancelled"}),
        ("(failure() || cancelled()) && a", {"failure", "cancelled"}),
        ("!(failure() || cancelled())", {"success"}),
        ("false", set()),
    ],
)
def test_statuses_follow_and_or_and_not(expression, expected):
    assert statuses(expression) == expected


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


@pytest.mark.parametrize(
    ("version", "kind", "below"),
    [
        ("26.0.0", "node", True),
        ("26.10.0", "node", True),
        ("26.11.0", "node", False),
        ("26", "node", False),
        ("26.x", "node", False),
        ("v27.0.0", "node", False),
        ("24", "node", True),
        ("3.15", "python", False),
        ("3.15.0", "python", False),
        ("3.14.9", "python", True),
        ("3.14", "python", True),
        ("lts/*", "node", None),
        ("26.11.0-not-a-version", "node", None),
        ("26.11.0garbage", "node", None),
        ("26.11.0-rc.1", "node", None),
        ("26.11.0.0", "node", None),
        ("3.15.0b4", "python", None),
    ],
)
def test_a_line_meets_the_floor_by_its_line_and_an_exact_version_in_full(version, kind, below):
    assert _below_floor(version, kind) is below


def test_an_indirect_step_counts_as_running_its_runtime():
    jobs = {"j": {"steps": [{"name": "Export", "run": "bash scripts/export-lockfiles.sh"}]}}
    key = "x.yml > j > Export > python"
    assert unset_steps("x.yml", jobs, indirect={key: "the script runs uv"}) == [key]
    assert unset_steps("x.yml", jobs, indirect={}) == []


def test_every_indirect_step_still_exists_and_has_a_reason():
    """So a renamed or removed step cannot leave the indirect list pointing at nothing."""
    keys = {
        step_key(file, name, step, i, kind)
        for file, jobs, _ in _every_file()
        for name, _, steps in _steps_of(jobs)
        for i, step in enumerate(steps)
        for kind in COMMAND
    }
    for entry, reason in INDIRECT_RUNTIME.items():
        assert isinstance(reason, str) and reason.strip(), f"{entry}: an indirect step needs a reason"
        assert entry in keys, entry


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
