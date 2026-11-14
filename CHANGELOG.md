# Changelog

All notable completed changes to this repository are recorded here. This file contains
completed work only — planned work lives in [TODO.md](TODO.md) and blocked decisions live
in [REVIEW.md](REVIEW.md).

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## Conventions (checked by `scripts/check-release-version.py`)

- **One version for the whole repository.** The engine wheel, the appliance, `/api/health` and the container image share a
  plain `X.Y.Z`, and one `vX.Y.Z` tag releases all of them. The policy, the places that name the version and the release
  steps are in [README.md](README.md), section "Releasing and versioning".
- **Work lands under `## [Unreleased]`**, in the same pull request as the change. Use the Keep a Changelog headings
  (`### Added`, `### Changed`, `### Fixed`, `### Security`, `### Removed`).
- **A release is a pull request.** It changes the version in the four places and `uv.lock`, moves everything under
  `## [Unreleased]` into a new `## [X.Y.Z] - YYYY-MM-DD` section (the exact heading format; the section is the release
  notes), and leaves `## [Unreleased]` with no entries. The release workflows refuse a tag while the section is missing,
  undated or empty, or while `[Unreleased]` still has entries.
- Headings that do not look like `## [X.Y.Z] - date` (for example the repository initialization entry) are history and are
  ignored by the check.

## [Unreleased]

### Added

- **CI now checks the workflow files and the Dockerfile with the same three linters as the lab edition, and checks that
  every workflow installs the same uv**
  ([HCW-HybridCloudWorks#1707](https://github.com/saulpatinojr/HCW-HybridCloudWorks/issues/1707), following
  [HCW-HybridCloudWorks#1575](https://github.com/saulpatinojr/HCW-HybridCloudWorks/issues/1575)). A linter is a tool
  that reads a file and reports mistakes without running it. The `lint` job in `ci.yml` (already a required check; no
  job is added or renamed) gains these steps, copied from the lab edition's `ci.yml` with the same versions and
  digests:
  - **actionlint 1.7.12** checks the workflow files for mistakes, and runs shellcheck (a shell script checker) on
    their scripts. `.github/actionlint.yaml` tells it that `ubuntu-26.04` is a GitHub-hosted runner, which this
    release does not know yet; the file is the same as the lab edition's.
  - **zizmor 1.31.1** checks the workflow files, and the composite action in `.github/actions` (it is handed the App
    key), for security problems. It reported one: `rehearse-self-merging-pr.yml`
    runs this repository's own action with `uses: ./...`, where GitHub now offers a safer `uses: $/...` form
    ([GitHub's announcement](https://github.blog/changelog/2026-07-30-reference-same-repository-actions-with-self-repository-syntax/),
    [zizmor's explanation](https://docs.zizmor.sh/audits/#self-repository)). The pinned actionlint does not understand
    `$/` and fails on it, so that one line is ignored in the new `.github/zizmor.yml`, with the reason written there
    (only a `printf` runs between the checkout and that line) and the step to undo it once actionlint accepts `$/`.
    zizmor matches the ignore against the whole step, so moving the step down by a line can keep it ignored; the
    file says to check the line number whenever the workflow changes.
  - **hadolint 2.14.0** checks `infrastructure/docker/Dockerfile`. It found nothing.
  - Each tool is downloaded at its pinned version and its SHA-256 (a fingerprint of the file) is checked before it
    runs; the three values were checked again against the publishers' own checksum files and PyPI on 2026-11-14.
  - **Every workflow uses the uv this workflow uses:** a new script, `scripts/check_uv_pins.py`, run by this step.
    It uses only Python's standard library, because it runs before uv is installed, and it is the same file in
    HCW-CloudCrawler_App. `UV_VERSION` in `ci.yml` is the one uv version. The step names the workflows that must
    install it (`publish-core.yml`, `security.yml` and `dependabot-lockfiles.yml`); the script fails if one of them is
    missing or does not install that uv. An install counts only as an argument of a `pip`, `pipx`, `uv pip` or
    `uv tool` install command in a `run:` script, outside a comment, so `echo "uv==…"` or a commented-out line does
    not count; and `uv==${UV_VERSION}` counts only in a file that sets `UV_VERSION` outside a comment (a YAML key or
    a shell assignment). It then reads every `.yml` and `.yaml` file under `.github/workflows` and
    every `action.yml` and `action.yaml` under `.github/actions`, at any depth, and fails on:
    - uv pinned to anything but `==` and that exact version: any operator (`===`, `~=`, `!=`, `>=`, `uv@…`), any
      spacing, any extras, and the name in any case or spelling pip reads as uv (`UV`, `Uv[foo.bar]`);
    - pip, pipx, `uv pip` or `uv tool` installing uv with no version;
    - `uses: astral-sh/setup-uv`, or the `ghcr.io/astral-sh/uv` image at another tag;
    - `UV_VERSION` given another value in any YAML or shell form;
    - `${UV_VERSION}`, `$UV_VERSION` or `env.UV_VERSION` in a file that never sets it.

    These are reported wherever they are written, comments included. Other packages are left alone (`pyuv`, `uvicorn`, `uv-dynamic-versioning`), and so is `uv_==…`, which pip refuses
    as a name. What it cannot see: a version worked out while a job runs, or an install written in a way these
    patterns do not describe. `tests/unit/test_check_uv_pins.py` (also the same file in both repositories) builds a
    small made-up repository for each of 50 changes that must fail and 21 that must pass, and runs the script on
    this repository with the file list `ci.yml` gives it. Uneven uv pins are how the versions drifted apart
    before.

  To make the linters pass, `setup-python` in the `lint` job now also runs after an earlier failure (the zizmor install
  makes a Python environment with `python3 -m venv` to install zizmor from PyPI, and runs then too, as in the lab
  edition), and the retry loop in `publish-core.yml` that waits for the GitHub Release names its unused counter `_`
  instead of `i` (shellcheck warning SC2034; no change in behaviour).
  The three linters and then the uv check run first in the `lint` job, straight after setting up Python and before uv is
  installed (from Copilot's review of the same change in MigrateOrchestrator_App): before, they ran after `uv sync`
  and the repository's own scripts, so code in a pull request could have rewritten `.github` on disk before it was
  read.
  Nothing here reaches the lab edition: it already runs these steps, and no engine, catalog or release asset changed,
  so its `docs/whats-new-upstream.md` needs no entry. Checked locally with uv 0.13.8: the three linters run exactly as
  the new steps run them (exit 0 each, with shellcheck 0.11.0 present as it is on the runner); the uv check passes on
  this repository; its tests fail when the script is broken on purpose (without its case folding, three cases fail;
  reading `.github/actions` one level deep only, the nested-action case fails); `make setup`, `make lint`, `make
  test` (1189 passed, 1 skipped; 95 percent coverage, 73 of the tests in `tests/unit/test_check_uv_pins.py`) and
  `make test-security` (38 passed).

### Changed

- **The workflow runtime check is refreshed to round three**
  ([HCW-HybridCloudWorks#1707](https://github.com/saulpatinojr/HCW-HybridCloudWorks/issues/1707)).
  `tests/unit/test_workflow_runtime_setup.py` is the test that fails when a workflow step runs Node.js or Python before
  its job has set up the version HCW requires (Node.js 26.11.0, Python 3.15.0), so the runner's own older versions
  cannot slip back in unnoticed. Round three closes the gaps a third review of the check found. Its logic and test cases
  are taken unchanged from the canonical Python copy in HCW-NetworkEyes_App
  ([HCW-NetworkEyes_App#399](https://github.com/saulpatinojr/HCW-NetworkEyes_App/pull/399)), which gives the same
  answers as the website's JavaScript copy
  ([HCW-HybridCloudWorks#1722](https://github.com/saulpatinojr/HCW-HybridCloudWorks/pull/1722)); only the lists of this
  repository's own steps are its own, and long lines are rewrapped to this repository's 120 columns (each made-up test
  workflow, one long line in the canonical copy, is split into pieces that Python joins back into the same text). What
  it now catches: a command written in quotes (`'node' x.js`) or with a backslash in it, or run through `eval` or
  `builtin`; a command run with `sudo`, which looks programs up in its own fixed list of folders and so gets the
  runner's own version (`sudo env "PATH=$PATH" ...` hands it the job's list instead); a step whose `shell:` is `python`
  or `node {0}`, or that takes it from `defaults.run.shell`. For pipx (a tool that installs and runs Python programs)
  the setting that chooses its Python is followed through `unset`, `export -n` and `declare +x` (which remove a setting,
  or keep it from the programs a script starts), the last change in a shell winning; a bare `python3` no longer counts
  as the set-up Python (only `python3.15` does), and neither does a value over two lines, a path under `/usr/local/bin`,
  one that climbs out of setup-python's folder with `..`, or a pattern the shell would still expand (`python*`,
  `~/...`); and `${{ env.X }}` is worked out one level at a time, as GitHub does. The test's small YAML reader (it reads
  the workflow files without a YAML library) now reads quoted values, comments and block values the way YAML does, reads
  `3.10` as `3.1` as GitHub hands it to an action, and stops with an error on a form it cannot read (an anchor, alias or
  tag, or a matrix item continued on the next line) instead of guessing. Nothing new is found here and no workflow
  changed. The new steps of the `lint` job still pass, because its `setup-python` step runs whenever they do
  (`if: ${{ !cancelled() }}`); with that `if:` taken out of a scratch copy of `ci.yml`, the check names the linter
  install step (it makes zizmor's environment with `python3 -m venv`) and the uv pin check
  (`python scripts/check_uv_pins.py`). The `INDIRECT_RUNTIME` entries (steps that start uv through a script, which the
  check cannot see in their own `run:` text) all stay, because the check still does not read the runtime in those steps;
  the note above them now also names `scripts/check_uv_pins.py`, added to the `lint` job after the note was written,
  which is run with `python` (read by the check) and starts nothing. Checked here with uv 0.13.8: `make setup`,
  `make lint`, `make test` (1391 passed, 1 skipped; 95 percent coverage, 901 of the tests in this file, 699 before) and
  `make test-security` (38 passed). The Python syntax tree (the code's structure as Python reads it) of this file matches the canonical copy at `9b96396` once the
  docstrings and this repository's lists are set aside, and the 12,975 round-three cases, the reviewer's 348 and the
  66,583 earlier ones give 0 disagreements with the canonical copy. The AddOn (HCW-CloudAssessor_AddOn) gets the same
  change in its own pull request, with its own `docs/whats-new-upstream.md` entry; nothing it adopts from this
  repository (the engine wheel, the catalog) changes, so this change adds no entry there.
  Copilot's review of this pull request and of its sister pull requests then found six more ways past the check,
  closed first in the two canonical copies (the website's JavaScript and HCW-NetworkEyes_App's Python) and copied here
  unchanged: a `sudo` inside a script that `sudo` already runs (there `$PATH` is already sudo's own list of folders,
  so `sudo bash -c 'sudo env PATH=$PATH node x'` still gets the runner's Node.js); a PATH replaced for one command
  (`env PATH=/usr/bin python3 x`); the runner's interpreter named by its folder or by an older version
  (`/usr/bin/python3`, `/usr/local/bin/node`, `python3.14`); one-line `case` clauses (`case "$k" in a) node x ;;
  esac`); a `${{ matrix.* }}` in the workflow-level `env:`, which GitHub does not fill in there; and pipx under a
  step's `shell:` that clears or changes `PIPX_DEFAULT_PYTHON` (`shell: env -u PIPX_DEFAULT_PYTHON bash -e {0}`). None
  of these forms is used in this repository's workflows, so the check reports exactly what it did before, and the test
  file grows to 977 cases. Checked again after this change: `make lint`, `make test` (1467 passed, 1 skipped; 95
  percent coverage) and `make test-security` (38 passed); the file still matches the canonical copy (now at `82b9258`)
  once the docstrings and this repository's lists are set aside, and the 19,584 generated cases of this change, the
  4,844 nested-sudo cases and the review's 348 inputs give 0 disagreements with it.
- **uv 0.13.7 to 0.13.8 in every workflow**
  ([HCW-HybridCloudWorks#1707](https://github.com/saulpatinojr/HCW-HybridCloudWorks/issues/1707)). uv is the tool that
  installs this repository's Python packages, keeps `uv.lock` (the file that records the exact versions installed) and
  builds the engine wheel. 0.13.8 is a patch release of uv (released 2026-11-12,
  [release notes](https://github.com/astral-sh/uv/blob/0.13.8/CHANGELOG.md)) with no change to the lock format. The pin
  moved in `ci.yml` and `dependabot-lockfiles.yml` (`UV_VERSION`), `security.yml` and `publish-core.yml`, with the uv
  wording in `README.md`, `.github/CONTRIBUTING.md` and `REFACTOR_APP.md`. In `REFACTOR_APP.md`, the note on section
  7.13 said the section was "kept as written", but its Python version and uv pin had been updated in place; the note
  now says those two are kept current, and the uv pin there moves too. Nothing else changed with it: with uv 0.13.8,
  `uv lock --check` passes and `make lock` leaves `uv.lock` and both `requirements*.lock.txt` files exactly as they
  were. **This reaches the lab edition** through `publish-core.yml`, which builds the engine wheel the AddOn installs:
  the wheel and the source archive built from the same commit with uv 0.13.7 and with uv 0.13.8 are byte for byte the
  same (wheel sha256 `2e763e7a…12be`, source archive `196e36f3…43cb4`, both built locally on 2026-11-13), so the next
  release's wheel does not differ because of uv. The AddOn's `docs/whats-new-upstream.md` says so in its own pull
  request. No Dockerfile here copies uv, so no image changes. Checked here with uv 0.13.8: `make setup`, `make lint`,
  `make test` (1116 passed, 1 skipped; 95 percent coverage), `make test-security` (38 passed), `uv lock --check`, and
  actionlint and zizmor on the four changed workflows (no findings; actionlint 1.7.12 does not yet know the
  `ubuntu-26.04` runner label, so that one message was set aside).
- **The workflows read the uv version as a shell variable** ([HCW-HybridCloudWorks#1707](https://github.com/saulpatinojr/HCW-HybridCloudWorks/issues/1707)). In the four `uv` install steps of `ci.yml` and the one in `dependabot-lockfiles.yml`, `python -m pip install "uv==${{ env.UV_VERSION }}"` becomes `python -m pip install "uv==${UV_VERSION}"`. `UV_VERSION` is set once in the workflow's own `env:` block, so the version installed is the same; the difference is that GitHub no longer pastes the value into the script text before the shell runs it (a `${{ }}` expression is filled in first, which zizmor, the workflow security checker, reports as a possible template injection at its strictest setting). The other steps of the same file already wrote it this way. No job name changes.
- **The workflow runtime check is refreshed to round two**
  ([HCW-HybridCloudWorks#1707](https://github.com/saulpatinojr/HCW-HybridCloudWorks/issues/1707)).
  `tests/unit/test_workflow_runtime_setup.py` is the test that fails when a workflow step runs Node.js or Python before
  its job has chosen the version, so the runner's own older versions cannot slip back in unnoticed. Its logic and test
  cases are taken unchanged from the canonical Python copy in HCW-NetworkEyes_App
  ([HCW-NetworkEyes_App#395](https://github.com/saulpatinojr/HCW-NetworkEyes_App/pull/395)), which works the same way as
  the website's own check ([HCW-HybridCloudWorks#1719](https://github.com/saulpatinojr/HCW-HybridCloudWorks/pull/1719));
  only the lists of this repository's own steps are its own. It now reads a script the way the shell runs it in more
  places: the script a shell is fed through a heredoc (`bash <<'EOF'`, a block of text handed to a command), the
  commands a heredoc's text runs with `$(...)`, and `$'...'` strings, while the rest of a heredoc's text and a `$` the
  shell passes on as text stay plain text. A step that runs `pipx` must hand pipx the Python a set-up step installed:
  the runner's own (`/usr/bin/python3`, or the Azure CLI's `/opt/az/bin/python3`) and a value the test cannot work out
  (`"$(command -v python3)"`) no longer count, `${{ steps.<id>.outputs.python-path }}` counts only from an earlier
  `actions/setup-python` step that is sure to have run, a shell variable set earlier in the script counts only in the
  same shell, and `sudo` passes the setting on only with `-E` or `--preserve-env`. Composite actions
  (`.github/actions/<name>/action.yml`, a list of steps that workflows reuse) are checked like a job of their own. A
  version file is read only when it is a `.python-version`, `.nvmrc` or `.node-version` file inside the checkout,
  `3.15.x` reads as the 3.15 line, YAML's folded `>` scripts and empty values are read as YAML reads them, and a
  workflow written in a shape the reader cannot follow (a step list on one line) now fails the test instead of being
  skipped. This copy's own check of composite actions, kept from before, is dropped, because the shared copy now reads
  them itself: `.github/actions/self-merging-pr/action.yml` is read with the same rules, and an exception for one of its
  steps would be keyed `.github/actions/self-merging-pr/action.yml > composite > step name > runtime` (it was
  `actions/self-merging-pr/action.yml > (composite) > ...`; no exception used the old key). Nothing new was found here:
  the composite action runs only `gh`, and no workflow runs pipx. The two steps that start uv through a script (the
  lockfile check in `ci.yml` and the export in `dependabot-lockfiles.yml`) stay in `INDIRECT_RUNTIME`, the list of steps
  that start a runtime the check cannot see: the check still does not read the runtime in their own `run:` text. It also
  carries the fourth review round's fixes (Copilot on
  [HCW-NetworkEyes_AddOn#109](https://github.com/saulpatinojr/HCW-NetworkEyes_AddOn/pull/109),
  [HCW-MigrateOrchestrator_AddOn#75](https://github.com/saulpatinojr/HCW-MigrateOrchestrator_AddOn/pull/75) and
  [HCW-MigrateOrchestrator_App#118](https://github.com/saulpatinojr/HCW-MigrateOrchestrator_App/pull/118)): a comment
  after a block value in `env:` or `with:` (a value written over several lines after `|`) ends the value instead of
  being read into it; a GitHub expression given to pipx chooses its Python only when it is setup-python's `python-path`
  output, `env.pythonLocation`, or an `env.X` or `matrix.X` whose value does, and `$pythonLocation` counts only after a
  set-up step; a runner path written with `.` or `..` (`/usr/bin/../bin/python3`) is still the runner's; and a set-up
  step under `(a || b) && c` now covers a later step under `a && c`. No workflow changed. Checked here: `make setup`,
  `make lint`, `make test` (1116 passed, 1 skipped; 95 percent coverage, 699 of the tests in this file, 356 before) and
  `make test-security` (38 passed). The AddOn (HCW-CloudAssessor_AddOn) gets the same change in its own pull request,
  with its own `docs/whats-new-upstream.md` entry.
- **The workflow runtime check is now the finished copy every HCW repository runs**
  ([HCW-HybridCloudWorks#1707](https://github.com/saulpatinojr/HCW-HybridCloudWorks/issues/1707)).
  `tests/unit/test_workflow_runtime_setup.py` is the test that fails when a workflow step runs Node.js or Python before
  its job has chosen the version, so the runner's own older versions cannot slip back in unnoticed. It now carries the
  same logic and test cases as the original (the website's `scripts/workflow-runtime-setup.test.mjs`), taken from the
  Python copy in `saulpatinojr/HCW-NetworkEyes_App`; only the lists of this repository's own steps are its own.
  What the finished copy reads that this one did not: `yarn` and `pnpm` count as Node.js, and `pytest` and `pipx`
  as Python; a step that runs `pipx` must also say which Python pipx uses (`--python`, or `PIPX_DEFAULT_PYTHON` in
  front of it or in an `env:` block), because pipx otherwise builds its tools on the runner's own Python even after
  `actions/setup-python`; the script given to `bash -c` or `sh -c` is read, while the same words handed to a
  container stay the container's; more words that run the next word are followed (`nohup`, `stdbuf`, `timeout`,
  `env -S`, `command -p`, `--`); and a set-up step's own `if:` covers a later step only when that step's condition
  makes it true, never by matching text that a step can change (`env.*`, `steps.*` of a later step).
  Two empty lists join it: `PIPX_ALLOWED` and `BELOW_FLOOR_ALLOWED`, for a deliberate exception with its reason.
  This repository's copy keeps one addition of its own from before: it also checks the steps of each composite
  action under `.github/actions` (the website's and the add-ons' copies read workflows only), now with the same
  reader as the workflows.
  Nothing new was found here: every step already sets its version up first, and no workflow runs pipx. The two steps
  that start uv through a script (the lockfile check in `ci.yml` and the export in `dependabot-lockfiles.yml`) stay in
  `INDIRECT_RUNTIME`, the list of steps that start a runtime the check cannot see; every other script a workflow
  calls was read on 2026-11-13 and starts nothing the check cannot see. No workflow changed. Checked here: `make
  setup`, `make lint`, `make test` (773 passed, 1 skipped; 95 percent coverage, 356 of the tests in this file) and
  `make test-security` (38 passed).
- **uv 0.11.32 to 0.13.7 in every workflow**
  ([HCW-HybridCloudWorks#1707](https://github.com/saulpatinojr/HCW-HybridCloudWorks/issues/1707)). uv is the tool that
  installs this repository's Python packages and keeps `uv.lock` (the file that records the exact versions installed).
  The old version could download only a beta of Python 3.15, so CI depended entirely on `actions/setup-python` for the
  interpreter; 0.13.0 is the first uv that can fetch a finished 3.15 (3.15.0) and 0.13.6 the first to offer 3.15.2,
  and 0.13.7 is the version `saulpatinojr/HCW-NetworkEyes_App` already uses, so the App repositories now share one uv.
  The pin moved in `ci.yml` and `dependabot-lockfiles.yml` (`UV_VERSION`), `security.yml` and `publish-core.yml`, with
  the uv wording in `README.md`, `.github/CONTRIBUTING.md` and `REFACTOR_APP.md`. Nothing else changed with it: `uv
  lock --check` passes with uv 0.13.7, and `make lock` run with it leaves `uv.lock` and both `requirements*.lock.txt`
  files exactly as they were. No Dockerfile copies uv (the images install from the exported lock files with pip), so
  no image changes.
- **The pre-commit ruff hook now matches the ruff the project pins.** `.pre-commit-config.yaml` (the optional local
  checks that run before each commit) pinned `ruff-pre-commit` at `v0.17.1` and its comment claimed that mirrored
  `pyproject.toml`, but `pyproject.toml` pins `ruff==0.17.4`. Both now say 0.17.4, so the hook and CI format and lint
  the same way.
- **Python 3.15 everywhere this repository chooses a Python**
  ([HCW-HybridCloudWorks#1707](https://github.com/saulpatinojr/HCW-HybridCloudWorks/issues/1707)). Python 3.15 is the
  HCW floor (the newest release line, at most two patches behind its newest, kept in `scripts/version-floors.json` in
  HCW-HybridCloudWorks), and the website and the AddOn already run it. What moved:
  - The container base image, from `python:3.14.10-slim-trixie` to `python:3.15.2-slim-trixie` by index digest
    `sha256:65a65fc7b30b…`, the same pin as the website's `lab-image/versions.env` and the AddOn (read again from
    Docker Hub on 2026-11-12; `python:3.15-slim-trixie` points at the same digest). `versions.env` and all four `FROM`
    lines move together, and the Dockerfile's `python3.14` site-packages paths become `python3.15`.
  - `requires-python` in both packages, from `>=3.14.6,<3.16` to `>=3.15.0,<3.16`. **This reaches the lab edition**: the
    next engine wheel will not install on Python 3.14. The AddOn already requires `>=3.15.1` and runs 3.15.2, so it is
    not affected, and no other consumer of the wheel is known. The engine moved with the appliance because nothing in
    this repository tests 3.14 any more, so keeping 3.14 in the wheel's range would be a promise nobody checks.
    `tests/packaging/test_core_wheel.py` now expects the new range. Because the published wheel drops Python 3.14, the
    next engine release should be a minor release, 0.4.0, not a patch.
  - `.python-version` and `make setup` now name the line only, `3.15`, as the AddOn does. CI gets its interpreter from
    `actions/setup-python` (the newest 3.15.x it has), and the pinned uv 0.11.32 cannot download a stable 3.15 itself
    (it offers only `3.15.0b4`), so an exact patch there would fail whenever the two differ. Locally, `uv python install
    3.15` needs uv 0.13.6 or newer to fetch 3.15.2 (`README.md` says so).
  - Every workflow's `python-version` (`ci.yml`, `dependabot-lockfiles.yml`, `publish-core.yml`, `publish-images.yml`,
    `release.yml`, `security.yml`) and ruff's `target-version` (`py315`).
  - `uv.lock` re-locked with uv 0.11.32, and both `requirements*.lock.txt` exports regenerated: only Python 3.15
    wheels remain. Every locked package has a 3.15 wheel (its own `cp315` wheel, an `abi3` one or a pure-Python one)
    except PyYAML 6.0.3, a test-only dependency that is in neither image: its newest release publishes no 3.15 wheel
    ([yaml/pyyaml#951](https://github.com/yaml/pyyaml/issues/951)), so `uv sync` builds it from its source archive,
    which `uv.lock` pins by sha256. The tools that build it are pinned too, `setuptools==84.2.1` and `cython==3.3.1`
    (`[tool.uv] build-constraint-dependencies` in `pyproject.toml`, recorded in `uv.lock`), so the build no longer takes
    whatever is newest that day; uv 0.11.32 honours the setting (its build log shows both pins). `TODO.md` T-035 removes
    them once PyYAML ships a 3.15 wheel.
  - The `.github/dependabot.yml` comment on the base image, and the Python wording in `README.md`, `CONTRIBUTING.md`,
    `REVIEW.md` and `REFACTOR_APP.md`. The README's engine-install example now installs the `v0.3.2` wheel: the
    `v0.2.1` one it named declares `<3.15` and cannot install on Python 3.15.
  - New `tests/unit/test_workflow_runtime_setup.py` fails any workflow step (and any composite action step) that runs
    `python`, `pip`, `uv`, `node`, `npm` or `npx` before its job has used `actions/setup-python` or
    `actions/setup-node`, so the runner image's own, older interpreter cannot come back unnoticed. Exceptions go in an
    allow-list keyed by file, job, step and runtime, each with a reason; it is empty today, and a second test fails any
    entry that no longer matches. Ported from the website's `scripts/workflow-runtime-setup.test.mjs`.
    A set-up step with its own `if:` covers only later steps under the same condition (or one of its top-level `||`
    terms), a command in backticks counts like one in `$(...)`, and every set-up step must ask for Python 3.15 or
    Node.js 26 or newer. A step's condition now counts GitHub's unwritten `success()`, a quoted `NAME="a b"` prefix
    counts, setup-uv sets Python up only with a `python-version`, an exact version must meet the full floor (Node.js
    26.11.0), and the two lockfile steps that run uv through a script are listed in `INDIRECT_RUNTIME`.
    A path in front of the interpreter (`/usr/bin/python3`) now counts, as do `python3.15.2`, a wrapper's options
    (`sudo -u nobody`) and a command after a `case` pattern, while a heredoc, a comment or a script quoted across lines
    for a container does not; `&&` and `||` of status functions are followed; and a version with trailing text
    (`26.11.0-rc.1`, `26.11.0.0`) is reported as unreadable.
  - `.qlty/qlty.toml` pins qlty's ruff to 0.17.4, the version in `uv.lock`: qlty's own default, 0.14.6, cannot read
    `target-version = "py315"`.
  Checked on CPython 3.15.2: `make lint`'s steps, the full test suite with the `azure` extra (451 passed, 1 skipped,
  95 percent coverage), the security and packaging suites without it (38 passed), and `pip install --require-hashes
  --no-deps --only-binary=:all:` of both exports. The images themselves were not built (no Docker in the session); the
  `image` job of CI builds and checks both targets. No workflow runs `python` or `node` on the runner's own default:
  every Python job already used `actions/setup-python`, and this repository has no Node.js code.
- The container base image moves from `python:3.14.8-slim-trixie` to `python:3.14.10-slim-trixie` (CPython 3.14.10 on
  Debian 13), pinned by its index digest `sha256:af8a5aa14780…` in `infrastructure/docker/versions.env` and in all four
  `FROM` lines of `infrastructure/docker/Dockerfile` together, so `scripts/check-versions.sh` still agrees. 3.14.10 is
  the newest Python 3.14 build on Docker Hub (read on 2026-11-07; `python:3.14-slim-trixie` points at the same digest
  and no 3.14.11 exists). Both final stages keep their `apt-get upgrade` step for Debian security fixes published after
  the base. `.python-version` and `make setup` stay on 3.14.6: that is the local and CI interpreter, the newest 3.14
  build uv 0.11.32 can download, and it remains the floor of `requires-python`; the image's 3.14.10 is inside the same
  range. `versions.env` and `REFACTOR_APP.md` no longer say the AddOn shares this pin: it moved to Python 3.15.2 with
  the website.
- `dependabot-lockfiles.yml` now says why the HCW Main Admin App's token could not be made when that step fails
  ([HCW-CloudCrawler_App#70](https://github.com/saulpatinojr/HCW-CloudCrawler_App/issues/70), the same change as its
  [#74](https://github.com/saulpatinojr/HCW-CloudCrawler_App/pull/74)). On 2026-11-06 a 401 from a private key that
  belonged to another App was first read as "secrets not set", the only message there was. The new step runs only when
  the token step fails, after the check that both secrets are present, and names the usual causes: a key or Client ID
  that is not that App's, or the App not installed on this repository. `tests/unit/test_workflows.py` pins it.
  Repository process only; nothing in the engine, the appliance or the lab edition changes.

### Removed

- **CodeRabbit, the review bot, is removed until further notice** (the owner's instruction of 2026-11-06). Its settings
  file `.coderabbit.yaml` is deleted. The 0.3.0 entry that turned on its approvals stays as history. The `Protect main`
  ruleset still requires one approving review, as `.github/workflows/repository-admin.yml` sets it; lowering it there
  and in the live ruleset is the owner's step. Repository process only; nothing in the engine, the appliance or the
  image changes.

### Security

- **The appliance image's lockfile now installs oauthlib 4.0.1, not 4.0.0 (CVE-2026-49272).** Dependabot's #89 moved
  oauthlib to 4.0.1 in `uv.lock` but not in `requirements-azure.lock.txt`, the hash-pinned export the appliance image
  installs, because the workflow that regenerates the exports on Dependabot's pull requests could not sign in as the
  HCW Main Admin App. `lint` and `test` caught the gap on #89 and failed; the pull request was merged past them, so
  `pip-audit` failed on `main`. `make lock` regenerated both exports from `uv.lock` (only the azure export changed; the
  default set has no oauthlib). A new test, `test_check_lockfiles_fails_when_one_export_lags_uv_lock`, now proves
  `scripts/check-lockfiles.sh` fails and names the file when either export lags `uv.lock`; the older test only broke the
  default export. Nothing in the engine changes, so the lab edition is not affected.

## [0.3.2] - 2026-11-04

A release of what was already on `main`, with the dry run fixed so it checks what the tag checks. **The `v0.3.1`
tag published nothing**: it was pushed after #87 had added entries under `[Unreleased]`, so the changelog guard in
all three tag workflows stopped at `CHANGELOG.md still has entries under [Unreleased]`
([release run 41910568739](https://github.com/saulpatinojr/HCW-CloudAssessor_App/actions/runs/41910568739),
[publish-core run 41910568892](https://github.com/saulpatinojr/HCW-CloudAssessor_App/actions/runs/41910568892),
[publish-images run 41910568940](https://github.com/saulpatinojr/HCW-CloudAssessor_App/actions/runs/41910568940)),
and a `v*` tag can never be moved or deleted (ruleset "Protect release tags"). **0.3.2 is therefore the release
that carries 0.3.1's `Requires-Python` widening to `<3.16`**, the wheel the lab edition's `fix/python-315-base`
branch pins; the `[0.3.1]` section below stays as history of what that number was meant to be.

### Changed

- Dependencies: `pydantic` 2.14.1 → 2.14.2 (the exact pin in `pyproject.toml`) with `pydantic-core` 2.50.1 → 2.50.2,
  `starlette` 1.9.0 → 1.10.0 and `opentelemetry-api` 1.45.1 → 1.45.2, in `uv.lock` and both `requirements*.lock.txt`
  files. This replaces the open Dependabot pull requests #78, #79 and #80, which all failed `lint`: #79 and #80 moved a
  version in the two exports alone and left `uv.lock` behind, and #78 rewrote the exports in a shape `uv export` does
  not produce. The engine package's `pydantic>=2.14,<3` range is unchanged, so nothing reaches the lab edition.
- **Dependabot Python pull requests no longer need a hand-run `make lock`** (TODO T-009 follow-up). `.github/dependabot.yml`
  excludes both exports from the `uv` entry (`exclude-paths`), so Dependabot edits `pyproject.toml` and `uv.lock` only.
  The new `.github/workflows/dependabot-lockfiles.yml` regenerates the exports on Dependabot's own pull requests
  (`uv export --frozen`: it reads `uv.lock` only, so no dependency code runs) and pushes them with a short-lived,
  contents-only token of the HCW Main Admin GitHub App (the add-ons' App, reused instead of a new one; HCW-CloudCrawler_App
  issue #70), so the required checks run on that commit as on any push. It cannot
  use `GITHUB_TOKEN`: a push made with it starts no workflow, and checks from a `workflow_dispatch` run never count as a
  pull request's required checks ([GitHub documentation](https://docs.github.com/en/pull-requests/how-tos/merge-and-close-pull-requests/troubleshooting-required-status-checks#checks-from-some-workflow-jobs-are-not-evaluated)).
  The job's own `GITHUB_TOKEN` is read-only. **Owner step:** install HCW Main Admin here and add the Dependabot
  secrets `HCW_MAIN_ADMIN_CLIENT_ID` and `HCW_MAIN_ADMIN_PRIVATE_KEY` (TODO T-009); until then the workflow stops with an error
  naming them. `scripts/export-lockfiles.sh` is now the one place the export flags live; `make lock` and
  `scripts/check-lockfiles.sh` call it (the check still runs `uv lock --check` first). `tests/unit/test_workflows.py`
  pins what the workflow may do.
- `.github/dependabot.yml`: the `github-actions` entry groups every action into one weekly pull request, as the other
  App repositories do.
- **Release 0.3.2 prepared.** The engine, the appliance and the image move together from `0.3.1` to `0.3.2` in
  `packages/cloud-assessor-core/pyproject.toml`, `pyproject.toml`, both `__version__` constants and `uv.lock`
  (re-locked with uv 0.11.32, the version CI uses; the dependency set is unchanged). The five tests that name the
  version follow. A patch number: nothing in the engine or the appliance behaves differently from 0.3.1. Tagging
  `v0.3.2` is the owner's step, after a green dry run of both publish workflows on the commit to be tagged.

### Fixed

- **The manual dry run of `publish-core.yml` and `publish-images.yml` is now a true rehearsal.** Before this, a
  manual run called `scripts/check-release-version.py` with no `--tag`, which checks only that the six version
  places agree and never reads `CHANGELOG.md`; that is why the two dry runs on `08632ed` were green
  ([41910180301](https://github.com/saulpatinojr/HCW-CloudAssessor_App/actions/runs/41910180301),
  [41910183097](https://github.com/saulpatinojr/HCW-CloudAssessor_App/actions/runs/41910183097)) while the `v0.3.1`
  tag on the same commit was refused. The script gains `--rehearse` (mirroring HCW-CloudCrawler_App): it takes the
  tag to be `v` + the package version and runs every check a real tag runs (tag format, a dated non-empty changelog
  section, nothing under `[Unreleased]`, the commit on `main`, the built files), and also fails when that tag already
  exists, because the version must then move on. Both workflows' manual path now calls it. `make lint` and `ci.yml`
  still run the script without a tag, so ordinary work with entries under `[Unreleased]` is unaffected.
  `tests/unit/test_release_guard.py` proves the dry run and the tag run refuse the same states and say the same
  thing, and `tests/unit/test_workflows.py` pins `--rehearse` in both workflows. README "Releasing and versioning"
  now tells the release pull request to run the rehearsal locally and the owner to dry-run before tagging.
- **CodeQL ran an unreleased build.** `codeql-action/init` and `/analyze` were pinned to `4c0873e…` with the comment
  `# v4.37.8`, but v4.37.8 is `db488dd…`; the pin was a commit between releases. Because it named no release, Dependabot
  tracked the branch and proposed another unreleased commit, `913e1bb…`, as two separate pull requests (#82, #83) that
  each left the pair split. Both are now pinned to the v4.39.2 release, `1fc58d04a4d4374f921bdac573c3811c240f9c26`
  (read with `git ls-remote https://github.com/github/codeql-action refs/tags/v4.39.2^{}` on 2026-11-04), and a new test
  fails if `init` and `analyze` are ever pinned apart. This replaces #82 and #83. Every other action pin in the
  repository was checked the same way and matches its tag.

### Security

- The ten `actions/checkout` steps in `ci.yml` and `security.yml` now set `persist-credentials: false`, so the job's
  `GITHUB_TOKEN` is not left in `.git/config` for later steps (zizmor `artipacked`, medium). No step in either workflow
  pushes with git. CloudCrawler already does this everywhere. A new test pins it for those two workflows and the new
  one. The release workflows followed in the entry below.
- The checkouts in `publish-core.yml` and `publish-images.yml` set `persist-credentials: false` as well (issue #85), so
  no checkout in any workflow keeps the token. Nothing after them needs it: the release-version check runs only the local
  `git merge-base` and `git rev-parse` on the full-history checkout, the builds use the checked-out files, and the
  release upload passes `GH_TOKEN` to `gh`. The checkout test now covers every workflow, matching the action name without
  regard to case. Proven by a manual run of both workflows on the branch, which publishes nothing.

## [0.3.1] - 2026-11-03

A metadata-only release. The engine wheel can now be installed on Python 3.15; no code changed.

### Changed
- **The Python ceiling widens from `<3.15` to `<3.16` (website issue
  [HCW-HybridCloudWorks#1386](https://github.com/saulpatinojr/HCW-HybridCloudWorks/issues/1386)).** Both
  `pyproject.toml` files and `uv.lock` now say `requires-python = ">=3.14.6,<3.16"`. The website moved its Python base
  to 3.15.2 ([HCW-HybridCloudWorks#1468](https://github.com/saulpatinojr/HCW-HybridCloudWorks/pull/1468)) and the lab
  edition (`HCW-CloudAssessor_AddOn`, branch `fix/python-315-base`) must follow, but the 0.3.0 wheel carries
  `Requires-Python: <3.15,>=3.14.6`, so `pip install --require-hashes --no-deps` on 3.15.2 stops with `Package
  'cloud-assessor-core' requires a different Python: 3.15.2 not in '<3.15,>=3.14.6'`. The code already runs on 3.15.2
  (the lab edition's 321 tests passed there); only the metadata blocked it. This is a widening, not a move: this
  repository's own image, CI and `.python-version` stay on 3.14 until the base image is moved by hand with its digest
  (`infrastructure/docker/versions.env`). New `tests/packaging/test_core_wheel.py::test_wheel_installs_on_python_314_and_315`
  reads the built wheel's `Requires-Python` so the ceiling cannot drift back unnoticed.
- **Release 0.3.1 prepared.** The engine, the appliance and the image move together from `0.3.0` to `0.3.1` in
  `packages/cloud-assessor-core/pyproject.toml`, `pyproject.toml`, both `__version__` constants and `uv.lock`
  (re-locked with uv 0.11.32, the version CI uses; the dependency set is unchanged). A patch number, because nothing
  in the engine or the appliance behaves differently. Tagging `v0.3.1` is the owner's step; it publishes the wheel the
  lab edition will pin, the GitHub Release and the image.

## [0.3.0] - 2026-10-25

Caller sign-in with Microsoft Entra ID and the Terraform that turns it on, a `/api/health` status that says when collection is failing, the release version guard, repository-admin safety, and fixes. The engine (`packages/cloud-assessor-core`) has no code change since 0.2.1; only its version number moves, so the lab edition receives the same engine under a new number.

### Added
- **Release version guard (ticket #33, CA-10).** `scripts/check-release-version.py` (standard library only) fails when
  the engine's and the appliance's `pyproject.toml`, their two `__version__` constants and their two `uv.lock` entries do
  not name the same plain `X.Y.Z`. With `--tag` it also requires the exact tag `vX.Y.Z`, a dated non-empty
  `## [X.Y.Z] - YYYY-MM-DD` changelog section, an empty `[Unreleased]`, and (`--ancestor-of origin/main`) a tagged commit
  that is on `main`; `--dist` checks the built files and `--notes-out` writes the release notes. Run by `ci.yml` (`lint`),
  `make lint` and the three tag workflows. `tests/unit/test_release_guard.py` covers it, including that `/api/health`
  reports the same version as `pyproject.toml`.
- **`CONTRIBUTING.md`, `CODE_OF_CONDUCT.md` and YAML issue forms (ticket #32, CA-9).** Both documents live under `.github/`.
  The markdown issue templates are replaced by forms with required fields and fixed dropdown values: `bug_report.yml`,
  `feature_request.yml` and `work_item.yml` (the shape the tracked tickets use; its dropdowns use the repository's
  priority, severity and workstream label values). `config.yml` keeps blank issues off. The README links to all of them
  ("Contributing and reporting"). `tests/unit/test_community_files.py` checks the forms and the files.
- **`security.yml` can be started by hand (ticket #30, CA-7).** The workflow now also has a `workflow_dispatch` trigger with
  no inputs, so the gitleaks scan can be run on demand instead of only on Mondays. Nothing else about the workflow
  changed; the dependency review job still runs only for pull requests. `tests/unit/test_workflows.py` pins this.
- **Self-merging pull request, ready for the workflows that will need it.** The composite action `.github/actions/self-merging-pr` (the same file is in every HCW application repository) turns the files a job changed into one pull request on a fixed branch, opened with a short-lived GitHub App token scoped to this repository (Contents and Pull requests write), because `main` is protected by a ruleset that requires a pull request and a pull request opened with `GITHUB_TOKEN` neither is allowed here nor starts the required checks. It can turn on squash auto-merge and wait for the merge. `rehearse-self-merging-pr.yml` (Run workflow) rehearses it against a harmless file: by default it opens the pull request, turns on auto-merge, confirms the required checks start, and closes the pull request again; with `merge` ticked it really merges `.github/rehearsal.txt` once as the end-to-end proof. The credential is the repository-admin App (HCW Portfolio Admin) held by the `admin-ops` environment, an interim choice; `dependabot.yml` now also reads `.github/actions/*` so the action's pins stay current. **[VERIFY]** by running the rehearsal; it has not run yet.
- `.github/workflows/repository-admin.yml`: an owner-approved, manually started workflow (dry run unless "apply" is ticked, every run approved in the `admin-ops` environment, short-lived GitHub App token limited to this repository). Tasks: `show-plan`, `protect-main` (ruleset requiring a pull request and the lint, test, boundary, catalog-check, secret-scan, image and terraform checks; `pip-audit` is added once it is stable), `protect-release-tags`, `delete-merged-branches`. `tests/unit/test_workflows.py` lists it.
- `CLAUDE.md`: the working agreement for AI coding agents (commands, never-weaken list, documentation model, and a plain-language communication section for the owner). `scripts/check-docs-governance.py` now allow-lists it, and its test asserts a root `CLAUDE.md` passes while other stray markdown still fails.

### Changed
- **Release 0.3.0 prepared (ticket #33 policy; the first image publish).** The engine, the appliance and the image move together from `0.2.1` to `0.3.0` in `packages/cloud-assessor-core/pyproject.toml`, `pyproject.toml`, both `__version__` constants and `uv.lock` (only the two version lines changed; both `requirements*.lock.txt` exports are unchanged). `0.3.0` and not `0.2.2` because 0.x versions put new features in the minor number: this release adds caller authentication and new Terraform inputs, and a Terraform plan that used to succeed without them now stops by design (see Security below), which a patch number would hide. The tests that name the version follow. Tagging `v0.3.0` is the owner's step; it publishes the wheel, the GitHub Release and the first image, `docker.io/hybridcloudworks/img-ca-appliance-app`.
- **License and visibility decided; the documents now say so (ticket #31, owner decision R-003 recorded 2026-10-25).** The owner confirmed MIT and a public repository. `REVIEW.md` R-003 is marked resolved (open blockers 7 to 6), `NOTICE` and the `README.md` layout table drop the `[REVIEW REQUIRED]` marker on the license, the "Not production" note in `README.md` and `CLAUDE.md` now waits on R-005 and R-006 only, `TODO.md` T-002 is Done, `REFACTOR_APP.md` records the decision on its R-003 rows. (The stale `v0.1.0` comment in `publish-core.yml` was already fixed in #65.) No behaviour changed. Checked: `gh repo view` reports PUBLIC and MIT; `scripts/check-docs-governance.py` passes.
- **`repository-admin.yml` can no longer lower the live rules by accident** (2026-10-25). Its `protect-main` and `protect-release-tags` tasks replace the whole ruleset with a list kept in the file, and that list was out of date: the live `Protect main` ruleset now needs one approving review, a code-owner review, approval of the last push and resolved review threads, and the live `Protect release tags` ruleset also blocks creating a tag and lets repository admins bypass it, while the file still said zero reviews and none of the rest. Running either task with "apply" would have switched all of that off without a word. Now both tasks read the live ruleset first and print what the update would remove or weaken and what it would add or change. With "apply" ticked they stop with an error, and change nothing, if the update would remove a rule, a required check, a bypass actor or a tag pattern, lower a number, or switch a protection off, unless the new "allow_weakening" box is ticked as well (it is off by default, and so is "apply"). A broken `REQUIRED_CHECKS` list (empty, not a list, a repeated or empty name) stops the task before anything is sent. The two payloads in the file now equal the live rulesets read on 2026-10-25 (the same seven required checks as before), so an apply changes nothing today. New `tests/unit/test_repository_admin_required_checks.py` (51 tests): every required check must be a real job name in `ci.yml` or `security.yml` and equal an explicit list, the payloads must equal the live values, and the real step runs against a stand-in `gh` that answers from sample rulesets and records every call, including 16 one-setting-at-a-time weakenings that must each be refused. If you change the live ruleset, change `REQUIRED_CHECKS` and that test's lists in the same pull request. **Not verified: a real `protect-main` or `protect-release-tags` run (only the stand-in `gh` was used); after merging, run `show-plan` and `protect-main` without "apply" and check that both print "removes and weakens nothing".**
- **CodeRabbit can now approve pull requests** (2026-10-25). The new `.coderabbit.yaml` turns on `request_changes_workflow` and keeps `allow_author_approval` off, because the `Protect main` ruleset now requires one approving review (decision B1, https://github.com/saulpatinojr/HCW-HybridCloudWorks/issues/1373). CodeRabbit asks for changes while a finding is open and approves the head once every thread is resolved.
- **Version hygiene (ticket #33, CA-10).** The appliance moves from `0.1.0` to `0.2.1`, the version the engine and the
  `v0.2.1` tag already had, so `/api/health` (`version`), the `x-addon-version` header, `pyproject.toml`, `uv.lock` and the
  engine now say the same thing. Policy: one version for the engine, the appliance and the image; one tag publishes all
  three; the version is raised only in a release pull request (README "Releasing and versioning", an owner-confirmable
  decision). `release.yml` is now two jobs (`check` with read-only permissions, then `create` with write permission); its
  release notes come from the changelog section for the tag and a missing section fails instead of falling back to a
  generic line. `publish-core.yml` and `publish-images.yml` run the version guard before they build, attest, attach or
  push anything; `publish-core.yml` builds with `--no-create-gitignore` so only the wheel and the sdist are in `dist/`.
  The three workflows now check out the full history so the tagged commit can be compared with `main`. `uv.lock` changes
  only the appliance's version line; both `requirements*.lock.txt` exports are unchanged.
- **Community files and issue forms (ticket #32, CA-9).** `.github/SECURITY.md` now routes reports only through GitHub
  private vulnerability reporting and no longer names an e-mail address or an acknowledgement time, because neither
  could be verified from the repository (restore them in a pull request if the owner confirms them).
  `scripts/check-docs-governance.py` allow-lists `.github/CONTRIBUTING.md` and `.github/CODE_OF_CONDUCT.md`, and its
  fallback file walk now reports paths with `/` on every platform.
- **Appliance image name follows the owner's convention `img-<short name>-<job>-<type>` (2026-10-25):** `docker.io/hybridcloudworks/img-ca-appliance-app`. This replaces `hcw-cloudassessor` from the entry below. The image has never been published, so no image moves and nothing needs copying. The tag is now the full release tag (`v0.2.1`, not `0.2.1`); the `sha-` tag is unchanged. `publish-images.yml`, the Terraform `image_ref` description, validation pattern and example, the Dockerfile comment, the README and `tests/unit/test_workflows.py` follow. Terraform still accepts only an exact `@sha256:` digest. The Docker OIDC connection must allow this repository to push to `img-ca-appliance-app` before the next `v*` tag. The lab edition keeps its own image (`img-ca-lab-addon`) and is not affected.
- **Appliance image renamed** from `docker.io/hybridcloudworks/hcw-cloud-assessor-appliance` to `docker.io/hybridcloudworks/hcw-cloudassessor` (owner naming convention, 2026-10-25). The appliance image has not been published yet, so no image moves and nothing needs copying. `publish-images.yml` (`IMAGE` and the image title label), the Terraform `image_ref` description, validation pattern and example, the Dockerfile comment, the README and `tests/unit/test_workflows.py` follow. Terraform still accepts only an exact `@sha256:` digest. Local `:dev` build tags are unchanged. The Docker OIDC connection must allow this repository to push to the new Docker Hub repository before the next `v*` tag. The lab edition (`HCW-CloudAssessor_AddOn`) keeps its own image name and is not affected, so it needs no `docs/whats-new-upstream.md` entry.
- `pyproject.toml`: `pyjwt[crypto]==2.15.1` is now declared in the appliance-only `azure` extra. It was already locked as a dependency of `msal`; `uv.lock` and `requirements-azure.lock.txt` change only in how they record it, and `requirements.lock.txt` (the default set) is unchanged. `tests/packaging/test_lockfile.py` now lists `pyjwt` as a fourth member of that extra.
- `/api/health` now says when collection is not working (ticket #35, application part). Two new fields: `status` (`ok` or `degraded`) and `degradedReason` (`null`, `no_snapshot` before the first successful run, or the error code of the latest failed run: `collector_error`, `timeout` or `internal_error`). Every existing field is unchanged, and so are the HTTP status (still 200) and `ok: true`, because the Container Apps liveness and readiness probes, the Docker `HEALTHCHECK` and the pane all read them; a 503 would restart a replica that is only waiting on Azure. The body carries error codes only, never a message, subscription or resource identifier (tested). Owner decision recorded in the pull request: whether degraded should ever return 503 or get a separate readiness route. Appliance code only; it does not reach the lab edition. Still open on #35: the repository description (needs the owner).
- `.github/dependabot.yml` no longer proposes updates to the `python` base image. It is a pair with `infrastructure/docker/versions.env` (image and digest) that `scripts/check-versions.sh` enforces, so every Dependabot image pull request failed `lint` and `test` by design (#42, a 3.15.0 image, also conflicts with `requires-python >=3.14.6,<3.15`). The image is moved by hand, in one change, with its digest.
- Dependencies: `pydantic` 2.14.0 → 2.14.1 (the exact pin in `pyproject.toml`), with `pydantic-core` 2.50.0 → 2.50.1 and `starlette` 1.7.0 → 1.9.0 in `uv.lock` and both `requirements*.lock.txt` files. This replaces the open Dependabot pull requests #19, #20 and #22: #19 (`pydantic-core` alone) could not resolve because pydantic pins its core to one exact version. `.github/dependabot.yml` now groups `pydantic` and `pydantic-core` so they arrive in one pull request. The engine package's `pydantic>=2.14,<3` range is unchanged, so nothing reaches the lab edition. Verified: `make lint`, `make test` (195 passed, 1 skipped, coverage 95.83 %) and `make test-security` (16 passed).
- `.github/dependabot.yml`: the Python entry now uses the `uv` ecosystem (ticket #29). The old `pip` entry edited only the two `requirements*.lock.txt` files and never `uv.lock`, so every Dependabot Python pull request failed `uv lock --check`. The engine package is a `uv` workspace member, so its separate `pip` entry is removed (the root entry covers it); the `azure-sdk`, `dev` and `pydantic` groups and the `python` image ignore are unchanged. Dependabot does not regenerate the requirements exports, so run `make lock` on a Dependabot Python pull request. Not yet verified: how Dependabot behaves on its next weekly run.
- `.pre-commit-config.yaml` (ticket #35, pre-commit part only): `ruff-pre-commit` moves from v0.17.0 to v0.17.1 to match `ruff==0.17.1` in `pyproject.toml`, and the gitleaks hook is set to v8.24.3, the release `security.yml` runs in CI (the `[VERIFY]` marker is gone; the tag exists upstream, checked 2026-10-24). The `/api/health` degraded state and the repository description are not part of this change.
- **Versioning policy recorded as the owner's decision (ticket #33, CA-10).** The owner decided on one version for the engine, the appliance and the image, checked against the tag in `publish-core.yml`, `publish-images.yml` and `release.yml`, with `/api/health` reporting that version. The code for this was already in place (`scripts/check-release-version.py`, appliance at `0.2.1`); `README.md` no longer says the policy is waiting for the owner's confirmation. Checked on 2026-10-25: the guard refuses `v0.2.2`, `v0.1.0`, `0.2.1` and `v0.2.1-rc1` against version `0.2.1` (exit 1 each), and `tests/unit/test_release_guard.py` (35 tests) and the `/api/health` version test pass.
- **Security: `certifi` 2026.7.22 to 2026.10.23 (advisory PYSEC-2026-4320, fixed in 2026.10.19).** Only the Azure runtime lock carried it. `uv.lock` was also stale against `pyproject.toml` (`fastapi` 0.143.0 and `ruff` 0.17.0 against the pinned 0.143.3 and 0.17.1), so the same `uv lock --upgrade-package certifi` brought those in line; no other version moved. `requirements-azure.lock.txt` was re-exported with the commands in the `Makefile`. Verified: `uv lock --check`, `scripts/check-lockfiles.sh`, `pip-audit --strict` on both requirements locks (no known vulnerabilities), ruff, and 194 tests passing.
- Python base image `python:3.14.8-slim-trixie` by digest in `infrastructure/docker/versions.env` and every `FROM` of the Dockerfile together (Dependabot #12 moved only the Dockerfile, which `scripts/check-versions.sh` rejects as drift).
- **Documents brought in line with reality (tickets #31 and #33, docs only).** `README.md` now names the two releases that exist (`v0.2.0`, 2026-10-12, and `v0.2.1`, 2026-10-18), says that no `v0.1.0` tag exists here (`0.1.0` is the seed's version and the appliance's), gives an install command that works (the release wheel, tested with `pip` on Python 3.14; the old `git+https` pin at `@v0.1.0` pointed at a tag that does not exist), and says the lab edition has not adopted a release yet. `REVIEW.md` R-003 now states the verified facts (an MIT `LICENSE` is in place, the repository is public) and leaves the license and visibility decision with the owner. Two `TODO.md` notes that called the repository private are corrected. `CLAUDE.md` gains the rule to record changes that reach the lab edition in its `docs/whats-new-upstream.md`. This file now groups the old `[Unreleased]` pile under the release each entry shipped in (nothing was removed or reworded).

### Fixed
- **The real-tenant runbook now works from a fresh PowerShell window (steps 3, 4 and 6).** The owner ran it on 2026-10-25: step 1 passed and steps 3 and 4 did not. A new window starts in the home folder, where `uv run` finds no project (`No module named cloud_assessor_appliance`), so step 3 now opens the second window in the repository folder (`Start-Process (Get-Process -Id $PID).Path -WorkingDirectory (Get-Location).Path`, tried in PowerShell 7 and 5.1) and says the first `uv run --extra azure` installs packages and can take a minute. The appliance prints no "listening" line (its web server logs warnings only), so the runbook now shows what it does print: the `startup` line with `"authEnabled":true`, then `refresh_started`, and what `startup_refused` and a busy port 8080 look like. Step 4 starts with `az login --tenant ... --scope "api://$app/access_as_user"` so the token request cannot stop on consent; step 6 says to destroy from the first window (it holds the `TF_VAR_` values); the bash block gets the same sign-in line. Checked: step 3 started with a made-up tenant and no Azure sign-in (port 18080, an empty Azure CLI config, `az` not on the path) and step 4 lines 1, 2, 3 and 7 answered 200, 401, 401, 401 with `WWW-Authenticate: Bearer`; the same line from the home folder failed as described. **Not verified: `az login --scope` itself, lines 4 to 6 of step 4, and the real-tenant result; the owner's original error was not seen, so the cause is inferred from the code and from reproducing the wrong-folder failure.** Documentation only: it reaches neither the engine nor the lab edition.
- The PowerShell commands of the real-tenant verification runbook now put every `-target=...` in double quotes. PowerShell splits an unquoted `-target=azuread_application.api` at the dot, so the runbook's apply and destroy lines failed with `Too many command line arguments` and `Invalid target` (found by the owner on 2026-10-25 when running step 1).
- **The sign-in registration no longer uses one name for both its app role and its scope; the real-tenant check found it.** Running step 1 of the real-tenant runbook against a real Entra tenant failed at `plan` with `duplicate value found: "Assessment.Read"` on `azuread_application.api`. `auth.tf` gave the app role (the permission applications and assigned users hold) and the delegated scope (the permission a signed-in user's token carries) the same value, and Entra keeps the two in one shared namespace, so the `azuread` provider refuses the plan. The mock-provider `terraform test` runs could not catch it, because mock providers do not run the provider's checks. Nothing was created in the tenant. The one variable `auth_permission` is now two: `auth_role_value` (default `Assessment.Read`, unchanged) and `auth_scope_value` (default `access_as_user`, the scope name Microsoft's web API guide uses), and `auth_scope_value` refuses to equal `auth_role_value`. The appliance's defaults follow (`CA_AUTH_REQUIRED_ROLES=Assessment.Read`, `CA_AUTH_REQUIRED_SCOPES=access_as_user`; the check is unchanged: a token still needs the role in `roles` or the scope in `scp`), the pre-authorised Azure CLI client is given the new scope, and the runbook asks for `api://<app id>/access_as_user` and expects the two different names in step 2. New checks: `tests/security/test_terraform_auth_guard.py` parses `auth.tf` and fails if any app role value equals any scope value (it reports `Assessment.Read` for the previous `auth.tf`), and `caller_authentication.tftest.hcl` has a run that refuses equal values plus an assertion that the planned registration's roles and scopes do not overlap (16 runs now). Still not verified: a plan or apply against a real tenant, which stays the owner's check (ticket #26).
- **`terraform plan` no longer fails with the default `alert_emails = []` (ticket [#60](https://github.com/saulpatinojr/HCW-CloudAssessor_App/issues/60)).** `azurerm_consumption_budget_resource_group` requires at least one notification and every notification needs a recipient, so the documented default ("no notifications") could not be planned. The budget now has `count = length(var.alert_emails) > 0 ? 1 : 0`: with at least one address it is created exactly as before (80 and 100 percent, actual spend); with the default empty list nothing is created and the plan succeeds. Chosen over a required variable because a sandbox or a test plan should not need an address, and over a default recipient such as `contact_roles` because a budget that notifies an unchosen audience is a worse guard than an explicit opt-out. `alert_emails` entries are now validated (an email address, no blank entry, no repeat), and a new output `budget_notifications` states in words whether a budget exists and for how many recipients. New `infrastructure/terraform/appliance-azure/tests/budget_notifications.tftest.hcl` (7 plan-only runs with mock providers: empty, unset, one recipient, several, and the three refusals; CI runs it in the `terraform` job with the existing tests) and a static test in `tests/security/test_terraform_auth_guard.py`; `README.md` and `terraform.tfvars.example` state the behaviour. Also: the header comment of `publish-core.yml` named the non-existent `v0.1.0` wheel and now shows `vX.Y.Z` (ticket [#31](https://github.com/saulpatinojr/HCW-CloudAssessor_App/issues/31)). Appliance Terraform and a comment only: the engine and the lab edition are untouched (no entry needed in the lab edition's `docs/whats-new-upstream.md`). **Not verified: a plan or apply against a real subscription; the failure and the fix were shown with mock providers only.**
- `uv.lock` pinned `fastapi` 0.156.8 while `pyproject.toml` and both `requirements*.lock.txt` already said 0.157.0, because the Dependabot bump (#47) edited only the two requirements files. `uv lock --check` (and so `make lint` and CI) failed on `main`. `uv.lock` is regenerated with `make lock`; nothing else changes. The `uv` ecosystem entry added to `.github/dependabot.yml` in #48 is what stops this recurring; the next Dependabot Python pull request will show whether it does.
- `scripts/check-lockfiles.sh` (CI and `make lint`) now fails with a clear message when `uv.lock` is out of date with `pyproject.toml` (`uv lock --check`), and exports with `--locked` so it can no longer silently rewrite `uv.lock` before comparing (ticket #27). New test `test_check_lockfiles_fails_on_a_stale_uv_lock_without_rewriting_it`; it fails against the old script and passes against the new one. `ci.yml` still installs with `uv sync --frozen`; changing that to `--locked` is proposed in ticket #24 and not done here.

### Security
- **Terraform for caller authentication, and a plan that refuses an unauthenticated public appliance (ticket CA-3, closes the Terraform half of T-032).** `infrastructure/terraform/appliance-azure` now has `external_enabled` as a variable (default `true`, as before) and a `precondition` on the Container App: `terraform plan` fails with "Refusing to plan an externally reachable appliance without caller authentication" unless `auth_enabled = true`, or `external_enabled = false` (private ingress), or the deliberately named override `dangerously_allow_unauthenticated_external_ingress = true` is set (an owner decision to record in `REVIEW.md`; `terraform output caller_authentication` then starts with `NONE`). A second precondition mirrors the appliance's own startup refusal: `public_results = true` needs `auth_enabled = true`, and the override does not relax it. With `auth_enabled = true` the Container App receives every `CA_AUTH_*` setting the code reads (all but `CA_AUTH_JWKS_URL`, which is left to the code's default), and a new `auth.tf` creates the Entra registration with the `azuread` provider (`~> 3.0`, locked in `.terraform.lock.hcl` next to `azurerm` 4.81.0): a single-tenant application with v2 access tokens, an `Assessment.Read` app role and delegated scope, the `api://<client id>` identifier URI, and a service principal with `app_role_assignment_required = true` (only assigned users, groups or managed identities, `auth_assigned_object_ids`, can obtain a token). No client secret, certificate or password exists anywhere in the configuration or the state; an existing registration can be described instead (`auth_create_app_registration = false`, `auth_tenant_id`, `auth_audiences`). New outputs: `caller_authentication`, `appliance_auth_settings`, `auth_application_client_id`, `auth_scope`. Tests: `infrastructure/terraform/appliance-azure/tests/caller_authentication.tftest.hcl` (15 plan-only runs with mock providers; CI runs them as a new step of the `terraform` job) and `tests/security/test_terraform_auth_guard.py` (static checks). `README.md` explains the supported exposure, how to turn sign-in on, what is verified and what is not, and a copy-pasteable real-tenant verification runbook (the repository's documentation model has no `VALIDATION.md`; the section is in the README). **Not verified: anything against a real Entra tenant; no `apply` has ever run, and the runbook has not been executed.** Plans that omitted these inputs before now fail by design: add `auth_enabled = true` (README, Sign-in). Found on the way and not fixed: `alert_emails = []` (the default) makes a plan fail on the real `azurerm` provider because the budget needs at least one notification (README, Known gaps).
- **Microsoft Entra ID sign-in for the appliance (T-032; owner decision R-009 option b, 2026-10-24).** With `CA_AUTH_ENABLED=true` every route except `GET /api/health` needs `Authorization: Bearer <access token>`, otherwise `401 unauthorized` with `WWW-Authenticate: Bearer`. The token must have an RS256 signature from the tenant's published keys (`alg` none, HS*, other algorithms and an unknown `kid` are refused), a valid `iss` (v2.0 or v1.0 form of the configured tenant), a configured `aud`, `exp` and `nbf` (both required, 60 seconds of clock skew by default, at most 300), `tid` equal to the configured tenant, and an app role or scope named in `CA_AUTH_REQUIRED_ROLES` / `CA_AUTH_REQUIRED_SCOPES` (default `Assessment.Read`). New settings, all in `.env.example`: `CA_AUTH_ENABLED`, `CA_AUTH_TENANT_ID`, `CA_AUTH_AUDIENCE`, `CA_AUTH_AUTHORITY_HOST`, `CA_AUTH_JWKS_URL`, `CA_AUTH_CLOCK_SKEW_SECONDS`, `CA_AUTH_REQUIRED_ROLES`, `CA_AUTH_REQUIRED_SCOPES`. Off by default, so a deployment that does not set them behaves as before. The `CA_PUBLIC_RESULTS` gate is unchanged and stays off by default: a valid token with the gate off still gets `403 results_not_public`. New startup refusals: sign-in enabled without a tenant, audience or authority host, and `CA_PUBLIC_RESULTS=true` without sign-in. Logs carry a status and a numeric reason code only, never a token or a claim. Tested with a key pair generated at test time and a local key set; **not tested against a real Entra tenant**. Appliance code only: `packages/cloud-assessor-core` and the lab edition are untouched (no entry needed in the lab edition's `docs/whats-new-upstream.md`). Terraform plumbing (`CA_AUTH_*` app settings and an `azuread_application`) follows in the next entry; `REVIEW.md` R-006 (labelling results "client confidential") is still open.
- `release.yml` and `publish-images.yml`: the release tag, image digest and image version are now passed to their shell scripts through `env:` and quoted, instead of being pasted into the script text with `${{ }}` (ticket #34). No behaviour change; it removes a script-injection risk if a tag name were ever unusual. `tests/unit/test_workflows.py` (SHA-pinned actions, `ubuntu-26.04`, read-only permissions) still passes.
- `.gitleaks.toml` (ticket #30): a second, narrow allow-list pattern for SHA-pinned action references quoted in prose. The scheduled full-history scan reported nine `sourcegraph-access-token` findings, all in one old commit (`ed4ead3`, `REFACTOR_APP.md` lines 299 and 315), all of the form `owner/action@<40-hex> # vN`; the existing pattern needed a `uses:` prefix. The new pattern needs the `@<40-hex>` and the `# vN` comment, so a bare 40-hex string is still reported (checked with a negative control). Reproduced with gitleaks 8.24.3, the CI version: 9 findings before, none after. A real run of the `security` workflow is still needed to confirm CI.

## [0.2.1] - 2026-10-18

### Changed
- **Core 0.2.1: pydantic is a range, not an exact pin (#15).** `packages/cloud-assessor-core/pyproject.toml` declares
  `pydantic>=2.14,<3` instead of `pydantic==2.14.0`, the same range the AddOn's seed adopted in
  `HCW-CloudAssessor_AddOn` #17. The engine is a library: an exact pin in the wheel and another in the app that
  installs it can only move in lockstep, so a Dependabot bump of either could never resolve. The appliance keeps its
  exact `pydantic==2.14.0` and its hash-locked `uv.lock`, so the resolved set is unchanged (`uv.lock` records only the
  new specifier and the version; both `requirements*.lock.txt` exports are identical). `__version__` is `0.2.1`; the
  release `v0.2.1` attaches `cloud_assessor_core-0.2.1-py3-none-any.whl` for the AddOn to adopt. The packaging and
  boundary tests now assert the range (`Requires-Dist: pydantic<3,>=2.14`) and match any specifier operator in the
  core manifest rather than `==` alone.

## [0.2.0] - 2026-10-12

First release tag. Everything below, down to the repository initialization entry, shipped in it.

### Changed
- README: badges (ci, security, release, Python, licence, lab edition) and a "new here?" opener in plain words that says what the product does and where the free lab edition will appear.
- `publish-core.yml`: the header names the contract the AddOn actually uses, the release wheel pinned by URL and sha256 (its `core-update.yml` was changed on 2026-10-11 because a `git+https` pin cannot be verified by its image's `pip install --require-hashes`). Comment only.

### Added
- **Engine adopted (change set A).** `packages/cloud-assessor-core` copied verbatim from `HCW-CloudAssessor_AddOn`
  `main` (commit `d552c6c`, the AddOn's 0.1.0 seed; `git diff --no-index` empty at adoption) with its unit tests,
  `catalog/{criteria,schema,scoring}.json`, `scripts/check-catalog.py` and the fictional `samples/`. From this commit the
  engine is owned here: changes are made here, released as `v*` tags, and adopted downstream through the AddOn's
  `core-update` workflow (ADR-0001, ADR-0028, recorded in the AddOn repository until the wiki exists).
- **Core 0.2.0, catalog 1.1.0 (change set D).** Additive `CostEvidence` and `BudgetEvidence` models, the
  `cost-evidence` evaluator kind (`budgets-present`, `anomaly-alerts-present`, `untagged-share`), and
  `evaluate(resources, catalog, *, evidence=None)`. Evidence gating: without evidence a `cost-evidence` check is skipped
  and the criterion is judged from the export exactly as before (the lab edition's pinned sample results are
  unchanged); with evidence Cost Management supersedes the export-side proxy. `CA-FIN-002`, `CA-FIN-003` and
  `CA-FIN-007` gain the second check with `anyPass`. `Assessment` gains optional `edition` and `scope` (count plus
  hashed subscription ids); `MODEL_VERSION` stays 1 because `Resource` is unchanged. `redaction.ALLOWED_WORDS` gains the
  appliance's event and code names. The package README is unchanged and allow-listed by the governance check because
  the wheel metadata requires it.
- **Skeleton (change set B, T-001, T-013).** uv workspace (`pyproject.toml` with the `azure` extra as the only place a
  cloud SDK is named), `uv.lock`, hash-pinned `requirements.lock.txt` (14 packages, none Azure) and
  `requirements-azure.lock.txt` (33 packages) with `scripts/check-lockfiles.sh`, `.python-version` 3.14.6, `ruff.toml`,
  `Makefile`, `.env.example` (every key, no values), `.dockerignore`, `.pre-commit-config.yaml` (T-015).
- **Appliance edition (change set C, T-011, T-025, T-026, T-027 scope half, T-028).** `src/cloud_assessor_appliance`:
  `edition.py` (refuses to start without the `azure` extra, with a forbidden credential variable, or without a parsable
  `CA_SCOPES`), `identity.py` (managed identity only; `ManagedIdentityCredential(client_id=AZURE_CLIENT_ID)` or a
  narrowed `DefaultAzureCredential` for `az login`; `AZURE_CLIENT_SECRET`, `AZURE_CLIENT_CERTIFICATE_PATH`,
  `AZURE_USERNAME`, `AZURE_PASSWORD`, `AZURE_TENANT_ID` refused), `collectors/scope.py` (the allow-list, `kql_filter`,
  `assert_contains`), `collectors/resource_graph.py` (one paged query from the allow-list only, 429 backoff, `max_rows`
  warning, every returned id checked), `collectors/cost_management.py` (month-to-date cost by resource group and
  `costCenter` tag, budgets, `InsightAlert` scheduled actions as anomaly alerts, hourly cache, `None` on throttle or
  missing role), `refresh.py` (single-flight lock, global cooldown, startup-then-timer collection, previous snapshot
  kept on failure), `api.py` (the section 8 routes: flat `/api/health` with `edition:"appliance"`,
  `azureConnectivity:"managed-identity"`, `scope.count`, `lastRun`, `publicResults`; `/api/assessments/current` and its
  `report.md`, `report.json`, `bundle.zip` answering `503 no_snapshot` before the first run and
  `403 results_not_public` while `CA_PUBLIC_RESULTS` is not `true`; `POST /api/refresh` with the per-client bucket,
  the global cooldown, single-flight `202 running` and optional human verification; `POST /api/assessments` answering
  `405 edition_readonly`; no owner tokens, no `{id}` paths), the lab's security modules ported (exact-origin CORS,
  headers with `frame-ancestors` from env, token bucket, verification with the `cloud-assessment-refresh` action, the
  content-free log writer, now also silencing the SDK loggers), and the pane copied from the AddOn with the edition
  switch (`mode = health.edition === "appliance" ? "current" : "upload"`).
- **Image (change set E).** `infrastructure/docker/Dockerfile` with the `appliance` target (deployed) and the `lab`
  boundary-proof target (installs the core without the extra, copies no application, `CMD` asserts `azure` is absent;
  never pushed, never deployed), both on the digest in `versions.env` checked by `scripts/check-versions.sh`;
  `publish-images.yml` builds both, runs the proof, scans with Trivy and pushes only the appliance through the Docker
  OIDC connection; `publish-core.yml` builds and verifies the wheel, attaches it to the release and attests it, with
  PyPI trusted publishing gated on `PYPI_ENABLED`; `release.yml` creates the release from this file.
- **Terraform (change set F).** `infrastructure/terraform/appliance-azure`: resource group, user-assigned identity,
  `Reader` and `Cost Management Reader` per `scope_ids`, Log Analytics (30 days), Consumption environment, one
  Container App (`min_replicas = max_replicas = 1`, HTTP probes on `/api/health`, `CA_SCOPES`, `AZURE_CLIENT_ID`,
  `CA_PUBLIC_RESULTS` from `var.public_results` defaulting to `false`), a resource-group budget with 80 and 100 percent
  notifications, an optional custom domain. `image_ref` has no default and must be a digest.
- **Tests (change set G, T-014).** `tests/unit` (config, scope, identity, edition, collectors, refresher, API, static
  pane, security modules, content-free logs, workflows, scripts), `tests/security` (appliance boundary in both
  directions; no secrets), `tests/packaging` (the built wheel; both lockfiles), and `test_cost_evidence.py` beside the
  engine's suite. 187 tests; coverage 95 percent (gate 85).
- **Governance and repository files (change set H, T-003, T-004, T-005, T-007, T-009, T-010, T-016, T-017, T-018,
  T-019).** `ci.yml`, `security.yml`, `CODEOWNERS`, `SECURITY.md`, `dependabot.yml`, `PULL_REQUEST_TEMPLATE.md`,
  `ISSUE_TEMPLATE/{bug_report.md,config.yml}`, `scripts/check-docs-governance.py` (five root files, platform
  templates, the engine README; relative links resolve), `.qlty/qlty.toml` with `ruff` and `bandit`, `LICENSE` (MIT,
  `[REVIEW REQUIRED]` R-003), `NOTICE` (attribution, `[REVIEW REQUIRED]` R-005), the `REFACTOR_APP.md` row in the
  `README.md` documentation table, `TODO.md` T-032 and T-033, `REVIEW.md` R-001 resolved, R-006 proposed, R-009 added.

### Verification (2026-10-10, authoring container; no Docker daemon, no `terraform`, no `az`)

| Check | Result |
|---|---|
| `uv sync --all-packages --extra azure` | 68 packages resolved; CPython 3.14.6 (`uv` offers no 3.14.7 build; the image pins 3.14.7 by digest) |
| `uv run ruff check . && uv run ruff format --check .` | clean |
| `uv run pytest -q --cov=packages --cov=src` | 187 passed, 1 skipped (the no-extra identity test); coverage 95.46 percent of 2,583 statements |
| `uv run pytest tests/security tests/packaging -q` (with and without the extra) | 16 passed both ways; `azure` not importable on the default set |
| `uv run python scripts/check-catalog.py` | catalog 1.1.0, 25 criteria, 25 `[VERIFY]`, schema in sync |
| `scripts/check-docs-governance.py`, `check-versions.sh`, `check-lockfiles.sh` | clean |
| `uv run pip-audit -r requirements.lock.txt --strict` and `-r requirements-azure.lock.txt` | no known vulnerabilities |
| `python -m cloud_assessor_appliance` on the default set, and with `AZURE_CLIENT_SECRET` set, and without `CA_SCOPES` | exit 3 with one scrubbed `startup_refused` line each |
| Local run with the extra and no Azure session | `/api/health` 200 (`edition:"appliance"`, `azureConnectivity:"managed-identity"`, `scope.count:1`, `publicResults:false`, headers `X-Addon-*`, CSP `frame-ancestors 'none'`, `X-Frame-Options: DENY`, `Cache-Control: no-store`); `/api/assessments/current` 503 `no_snapshot`; `POST /api/assessments` 405 `edition_readonly`; `POST /api/refresh` 202; `/` 200; logs carried counts and codes only |
| Image build, both targets; Trivy; `terraform fmt`/`validate`; a `plan` | **not run here** (CI `image` and `terraform` jobs; the plan is an owner step after R-002) |
| Live collection against a subscription | **not run** (R-002) |

### Changed

- Security review of PR #6 (2026-10-10): the refresh route checks the global cooldown before the single-flight lock
  (deterministic `429`); both collectors run under `asyncio.wait_for` with `CA_COLLECT_TIMEOUT_SECONDS`, and the SDK
  clients get connection (10 s) and read (60 s) timeouts and `retry_total = 3`; `/api/health` gains `lastError`,
  `snapshotAgeSeconds` and `scope.{configured,observed}` beside `scope.count`; internal and unhandled errors log the
  exception class name only (collector errors keep their scrubbed, application-composed message); `CA_TRUST_PROXY=1`
  reads the last `X-Forwarded-For` entry (the one the trusted proxy appended), not the first; the queued refresh task is
  kept on the refresher with a done callback; human verification runs in a worker thread; `publish-images.yml` pushes
  only from a `v*` tag ref; `budget_start_date` is required and validated (no expiring default); scope ids are
  lower-cased before `toset`; the Dockerfile `HEALTHCHECK` honours `PORT`; `__main__` writes its refusal with
  `json.dumps`; `ATTEMPTS` is used in the throttling message and a status-less `ClientAuthenticationError` is named
  instead of `HTTP None`; the CodeQL pins name `v4.37.8`. T-034 (the provider lock file) is done: `infrastructure/terraform/appliance-azure/.terraform.lock.hcl` pins `hashicorp/azurerm` 4.81.0 with hashes for linux_amd64 and windows_amd64.
- `README.md` rewritten for the implemented state: editions, layout, the section 20 commands as the quick start, the
  five-file documentation table, engine-change conventions.
- `.gitignore` extended (T-004); `.qlty/qlty.toml` plugins (T-010).

### Known limitations

- Python 3.14.7 is the image's interpreter (by digest) while `.python-version` pins 3.14.6, the newest build `uv`
  can install here; both satisfy `requires-python >=3.14.6,<3.15`.
- Cost Management field names, the `InsightAlert` reading of anomaly alerts, the managed-certificate custom-domain
  flow and the base-image digest are `[VERIFY]` until the first live validation (R-002) and image build.
- `POST /api/refresh` is bounded globally first: inside the cooldown (which starts when the route queues a run, so it
  covers that run while it is in progress) the answer is `429 rate_limited` with `Retry-After`; only a timer-started
  run in progress answers `202 {queued:false, running:true}`. `REFACTOR_APP.md` sections 7.8 and 8 were updated to say
  so (section 8 had tabled `503 busy`).
- A collection that runs past `CA_COLLECT_TIMEOUT_SECONDS` (default 900) is abandoned: the single-flight lock is
  released, the previous snapshot stays current and `/api/health` reports `lastError: "timeout"`. The worker thread
  cannot be interrupted and finishes on its own; its result is dropped.

### Added (documentation governance, before the plan)

- Documentation governance model for the repository. Four root markdown files are now the
  only sanctioned in-repository documents: `README.md` (repository purpose), `CHANGELOG.md`
  (completed work), `REVIEW.md` (human-resolvable blockers), and `TODO.md` (engineering
  work queue). All other documentation is directed to the GitHub Wiki.
- `CHANGELOG.md` recording completed work.
- `REVIEW.md` recording blockers that require a human decision, each with problem
  statement, blocking rationale, required owner, required action, impact, references, and
  a recommended next step.
- qlty configuration at `.qlty/qlty.toml`, generated by `qlty init`. The qlty GitHub App
  was already installed on the repository but the repository had never been initialized
  for it, so the `qlty check` status errored with "Qlty must be set up in this repository"
  before analyzing anything. Auto-detection enabled the TruffleHog secret scanner; with the
  configuration committed, `qlty check --all` reports no issues. This is tool
  configuration, which is the sanctioned use of a dot-prefixed folder.
- `TODO.md` establishing the authoritative engineering backlog, organized into six
  implementation phases in dependency order, with per-item priority, description,
  dependencies, recommended action, status, and handoff notes.

### Changed (documentation governance, before the plan)

- **Narrowed the assessment scope to Azure only.** AWS, GCP, and OCI were removed as target
  platforms across all documentation; support for them is not planned. Azure remains the
  source of the Well-Architected Cost Optimization pillar and is now also the sole
  assessment target. This resolves the platform half of blocker R-001, which had flagged
  the contradiction between a description listing AWS, GCP, and OCI as targets and open
  issues proposing exclusively Azure integrations.

  Consequences recorded across the backlog: the three per-cloud collectors became an Azure
  decomposition along the planes Azure actually separates — ARM resources (T-025), Cost
  Management (T-026), and scope enumeration with Entra ID identity (T-027); the credential
  standard in T-011 is now Azure-specific and accounts for `Reader`, `Cost Management
  Reader`, and Microsoft Graph being three distinct permission grants; the access request
  in R-002 is now a single Azure subscription; and the data model in T-024 is explicitly
  scoped to Azure rather than provider-neutral.

- Rewrote `README.md`. The title now uses the project name rather than the
  `owner-repository` slug, and the file was expanded to cover project status, benchmark
  scope, repository layout, quick start, installation and configuration state,
  documentation navigation, and repository conventions. The pre-implementation status of
  the repository is now stated explicitly so the absence of build and run instructions is
  not mistaken for missing documentation.

## 2026-06-05 — Repository initialization

No version has been released and no git tag exists yet, so this entry is grouped by date
rather than by version number.

### Added

- Initial repository with project description covering the multi-cloud,
  container-focused Well-Architected Review scope across AWS, GCP, and OCI.
- Python `.gitignore` based on the GitHub Python template.
- Feature request issue template at `.github/ISSUE_TEMPLATE/feature_request.md`.
