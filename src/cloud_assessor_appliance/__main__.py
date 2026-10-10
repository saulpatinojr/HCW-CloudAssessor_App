"""`python -m cloud_assessor_appliance`: uvicorn on 0.0.0.0:$PORT, no access log, no proxy headers, SIGTERM graceful."""

from __future__ import annotations

import sys


def main() -> int:
    try:
        from cloud_assessor_appliance.api import create_app
        from cloud_assessor_appliance.config import Settings
        from cloud_assessor_appliance.edition import assert_appliance_ready

        assert_appliance_ready()
        settings = Settings.from_env()
        app = create_app(settings)
    except Exception as exc:  # noqa: BLE001 - startup refusal is the point; the reason is printed once, scrubbed
        from cloud_assessor_core.redaction import scrub

        reason = scrub(f"{type(exc).__name__}: {exc}").replace('"', "'")
        sys.stderr.write(f'{{"event":"startup_refused","reason":"{reason}"}}\n')
        return 3
    import uvicorn

    uvicorn.run(
        app,
        host="0.0.0.0",  # noqa: S104 - the Container Apps ingress is the only listener in front of this port
        port=settings.port,
        access_log=False,
        proxy_headers=False,
        server_header=False,
        log_level="warning",
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
