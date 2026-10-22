"""Production image entrypoint; test harnesses are not part of this runtime."""

import argparse
import os
import re


def validate_runtime_environment():
    if os.environ.get("FLA_ENVIRONMENT") != "production":
        raise ValueError("Production image requires the production environment")
    if not re.fullmatch(r"[0-9a-f]{40}", os.environ.get("FLA_RELEASE_SHA", "")):
        raise ValueError("Production image requires an exact release identity")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["serve", "migrate"])
    args = parser.parse_args()
    try:
        validate_runtime_environment()
        if args.action == "migrate":
            from urllib.parse import parse_qs, urlsplit

            from alembic import command
            from alembic.config import Config

            from app.core.config import Settings

            settings = Settings()
            if settings.database_url is None or parse_qs(
                urlsplit(settings.database_url.unicode_string()).query
            ).get("sslmode") != ["verify-full"]:
                raise ValueError("Migration job requires verified database TLS")
            command.upgrade(Config("alembic.ini"), "head")
        else:
            import uvicorn

            from app.core.logging import production_log_config

            uvicorn.run(
                "app.main:app",
                host="0.0.0.0",
                port=8000,
                proxy_headers=False,
                access_log=False,
                log_config=production_log_config(),
                workers=1,
                timeout_graceful_shutdown=35,
                limit_concurrency=100,
            )
    except Exception:
        # Do not serialize credentials, database errors, originals or traceback chains.
        parser.exit(1, "Runtime preflight/action failed; inspect safe readiness reason codes\n")


if __name__ == "__main__":
    main()
