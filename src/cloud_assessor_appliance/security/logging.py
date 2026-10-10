"""JSON lines to stderr through one guarded writer. Counts, durations, flags and allowed words only.

The Azure SDK logs through the standard `logging` module (credential chains, HTTP policies); those records can carry
scope ids and endpoint details, so `configure()` silences every `azure`/`msal`/`urllib3` logger. The guarded writer
below is the only path to stderr.
"""

from __future__ import annotations

import json
import logging
import sys
import time
from typing import Any

from cloud_assessor_core.redaction import assert_no_visitor_data, scrub

SDK_LOGGERS = ("azure", "msal", "msrest", "urllib3", "uvicorn", "uvicorn.error", "uvicorn.access")

_silent = False


def configure(*, silent: bool) -> None:
    global _silent
    _silent = silent
    for name in SDK_LOGGERS:
        logger = logging.getLogger(name)
        logger.handlers = [logging.NullHandler()]
        logger.propagate = False
        logger.setLevel(logging.CRITICAL + 1)


def _write(event: dict[str, Any]) -> None:
    scrubbed = event.pop("scrubbed", None)
    assert_no_visitor_data(event)
    if scrubbed is not None:
        event["scrubbed"] = scrub(str(scrubbed))
    if _silent:
        return
    sys.stderr.write(json.dumps(event, separators=(",", ":"), default=str) + "\n")
    sys.stderr.flush()


def log_event(event: str, **fields: Any) -> None:
    _write({"ts": round(time.time(), 3), "event": event, **fields})


def log_exception(event: str, exc: BaseException, **fields: Any) -> None:
    _write(
        {
            "ts": round(time.time(), 3),
            "event": event,
            "error": True,
            **fields,
            "scrubbed": f"{type(exc).__name__}: {exc}",
        }
    )
