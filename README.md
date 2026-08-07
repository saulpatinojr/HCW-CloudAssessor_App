# Work-Complete Cloud Assessment

A multi-cloud, container-focused Well-Architected Review assessment benchmarking
infrastructure against the FinOps Foundation Framework, the Azure Cost Optimization
pillar, and Zero Trust security principles across AWS, GCP, and OCI.

## Project status

This repository is at the **pre-implementation stage**. It currently contains repository
scaffolding and governance documentation only — no assessment code, packaging, tests, or
CI automation has been committed yet.

Because of that, the "Quick start", "Installation", and "Configuration" sections below
describe what exists today rather than a working tool. They will be filled in as the
implementation lands.

Planned engineering work is tracked in [TODO.md](TODO.md). Decisions that must be made by
a human before implementation can proceed are tracked in [REVIEW.md](REVIEW.md).

## Overview

The assessment is intended to evaluate container-hosting cloud infrastructure against
three benchmark sources:

| Benchmark source | Focus |
|------------------|-------|
| FinOps Foundation Framework | Cost visibility, allocation, optimization, and operating-model maturity |
| Azure Well-Architected Framework — Cost Optimization pillar | Cost-focused architectural review criteria |
| Zero Trust security principles | Identity, device, network, and workload security posture |

Target platforms are AWS, GCP, and OCI. The concrete deliverable format (CLI, report
generator, dashboard, or infrastructure-as-code module) has not been decided yet — see
[REVIEW.md](REVIEW.md).

## Repository layout

```text
.
├── .github/
│   └── ISSUE_TEMPLATE/
│       └── feature_request.md   GitHub issue template
├── .qlty/
│   └── qlty.toml                qlty code quality configuration
├── .gitignore                   Python ignore rules
├── CHANGELOG.md                 Completed work
├── README.md                    This file
├── REVIEW.md                    Blockers requiring a human decision
└── TODO.md                      Engineering work queue
```

## Quick start

```bash
git clone https://github.com/saulpatinojr/Work-Complete_Cloud_Assessment.git
cd Work-Complete_Cloud_Assessment
```

There is nothing to build or run yet. Start with [TODO.md](TODO.md) to see what needs
doing, and [REVIEW.md](REVIEW.md) to see what is blocked.

## Installation

No installable artifact exists yet. The `.gitignore` is a Python template, which reflects
the current intent to implement in Python, but no language, runtime version, or dependency
manager has been committed. Tracked as a Phase 1 item in [TODO.md](TODO.md).

## Configuration

No configuration surface exists yet. Cloud credentials, tenant scoping, and benchmark
selection will all need configuration once collectors are implemented; the credential
handling approach is tracked in [TODO.md](TODO.md) and the provisioning of read-only
access to assessment targets is tracked in [REVIEW.md](REVIEW.md).

## Documentation

This repository uses a deliberately small documentation model. Only four markdown files
live in the repository, each with a single purpose:

| Document | Contains |
|----------|----------|
| [README.md](README.md) | Repository purpose, overview, setup, and navigation |
| [CHANGELOG.md](CHANGELOG.md) | Completed work only |
| [REVIEW.md](REVIEW.md) | Blockers that require a human decision or external input |
| [TODO.md](TODO.md) | The authoritative engineering backlog |

All other documentation — architecture, design, ADRs, roadmaps, runbooks, troubleshooting
guides, research, and knowledge transfer material — belongs in the
[GitHub Wiki](https://github.com/saulpatinojr/Work-Complete_Cloud_Assessment/wiki).

The wiki is enabled but not yet populated. Proposed wiki pages are listed in the
Phase 6 section of [TODO.md](TODO.md).

## Repository conventions

- **Documentation destination is determined by content, not filename.** Repository purpose
  goes in `README.md`; completed work in `CHANGELOG.md`; human-resolvable blockers in
  `REVIEW.md`; all actionable engineering work in `TODO.md`; everything else in the wiki.
- **No documentation in dot-prefixed folders.** `.github/`, `.vscode/`, and similar
  directories hold tool and platform configuration only. The sole exceptions are markdown
  files the platform itself requires, such as issue and pull request templates.
- **No non-root README files.** A `README.md` outside the repository root is documentation
  and belongs in the wiki.
- **There must never be competing sources of truth.** Before adding a document, check
  whether an existing one already owns that content.
- **Issues** are used for feature and integration proposals. Work accepted from an issue
  should be reflected in `TODO.md` so an engineer can resume without rediscovering it.
