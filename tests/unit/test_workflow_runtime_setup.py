"""Every workflow step that runs Node.js or Python comes after the job chose its version (HCW-HybridCloudWorks#1707).

A job that runs `python`, `pip` or `uv` without actions/setup-python, or `node`, `npm` or `npx` without
actions/setup-node, gets whatever the runner image ships. On ubuntu-26.04 in November 2026 that was Python 3.14 and
Node.js 24, both below the HCW floors (Python 3.15, Node.js 26). Nothing else would notice: a job that names no version
has no version for a reviewer to read. `uv` counts as Python, because uv runs the interpreter it finds on the runner.

A command counts when it is in command position on a line of a `run:` step: at the start, after `$(`, `<(`, `(`, `{`,
`|`, `&&`, `||` or `;`, after leading `NAME=value` assignments, or after a word that runs the next one (`env`, `sudo`,
`xargs`, `exec`, `time`, `!`, `if`, `then`, `do` and the like). It does not count inside a quoted string (unless the
string runs a command with `$(` or `<(`), on a comment line, or as an argument (`docker run img python ...`). The set-up
step must come before the first such step. Limits, on purpose: a job that runs in a `container:` uses that image's
runtime and is not checked; a script a step calls (`bash scripts/x.sh`) is not read; and a set-up step with its own
`if:` counts as done, so give it the same condition as the steps that need it.

Ported from scripts/workflow-runtime-setup.test.mjs in HCW-HybridCloudWorks.
"""

import re

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
    r"(?:^|[$<]\(\s*|[({|;&]\s*)"
    r"(?:[A-Za-z_][A-Za-z0-9_]*=\S*\s+|(?:env|sudo|xargs|exec|time|nice|command|if|then|else|elif|do|while|until|!)\s+)*"
)
COMMAND = {
    "node": re.compile(START + r"(?:node|npm|npx)(?=\s|$)"),
    "python": re.compile(START + r"(?:python(?:3(?:\.\d+)?)?|pip3?|uv)(?=\s|$)"),
}
SETUP = {"node": re.compile(r"^actions/setup-node@"), "python": re.compile(r"^actions/setup-python@")}


def _without_quoted_text(line: str) -> str:
    """The line with the text of its quoted strings taken out, so words in a message (`echo "...; if pip named..."`) do
    not count. A double-quoted string that runs a command (`"$(python x)"`) is kept."""
    line = re.sub(r"'[^']*'", "''", line)
    return re.sub(r'"(?:[^"\\]|\\.)*"', lambda m: m.group(0) if re.search(r"[$<]\(", m.group(0)) else '""', line)


def runs_runtime(run, kind: str) -> bool:
    """True when a run step calls the runtime in command position on a line that is not a comment."""
    for raw in str(run or "").split("\n"):
        line = raw.strip()
        if line and not line.startswith("#") and COMMAND[kind].search(_without_quoted_text(line)):
            return True
    return False


def unset_steps(file: str, jobs: dict) -> list[str]:
    """The steps that run a runtime before (or without) setting it up, as "file > job > step > runtime"."""
    found = []
    for name, job in (jobs or {}).items():
        steps = job.get("steps") if isinstance(job, dict) else None
        if not isinstance(steps, list) or job.get("container"):
            continue
        for kind in COMMAND:
            setup = next((i for i, s in enumerate(steps) if SETUP[kind].search(str(s.get("uses") or ""))), None)
            for i, step in enumerate(steps):
                if (setup is None or setup > i) and runs_runtime(step.get("run"), kind):
                    found.append(f"{file} > {name} > {step.get('name') or f'step {i + 1}'} > {kind}")
    return found


def _all_unset() -> list[str]:
    found = []
    for path in WORKFLOWS:
        found += unset_steps(path.name, yaml.safe_load(path.read_text(encoding="utf-8")).get("jobs"))
    for path in ACTIONS:
        # A composite action's steps run in the caller's job, but the action is checked on its own: whatever it runs
        # must be set up inside it, because a caller cannot be relied on to have done it.
        runs = yaml.safe_load(path.read_text(encoding="utf-8")).get("runs") or {}
        if runs.get("using") == "composite":
            found += unset_steps(f"{path.parent.name}/{path.name}", {"runs": runs})
    return found


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
    ],
)
def test_python_in_command_position_counts(line):
    assert runs_runtime(line, "python")


@pytest.mark.parametrize(
    ("line", "kind"),
    [
        ('echo "run `node scripts/x.mjs` by hand"', "node"),
        ('docker run --rm img python -c "import azure"', "python"),
        ("/opt/az/bin/python3 -Im pip check", "python"),
        ("# node is not run here", "node"),
        ('for node in items["nodes"]:', "node"),
        ('echo "$NODE_VERSION"', "node"),
        ("nodes=3 nodejs-check", "node"),
        ('echo "the stage is wrong; if pip named the file differently, look"', "python"),
        ("uvicorn app:app", "python"),
        ("bash scripts/check-lockfiles.sh", "python"),
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


def test_every_runtime_step_comes_after_its_setup():
    unset = _all_unset()
    assert [entry for entry in unset if entry not in RUNNER_DEFAULT_ALLOWED] == []


def test_every_allowed_exception_still_exists_and_has_a_reason():
    unset = _all_unset()
    for entry, reason in RUNNER_DEFAULT_ALLOWED.items():
        assert reason.strip(), f"{entry}: an exception needs a reason"
        assert entry in unset, f"{entry} no longer runs the runner's default; remove it from RUNNER_DEFAULT_ALLOWED"
