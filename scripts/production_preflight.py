"""Fail-fast production readiness checks that do not print secrets."""

from __future__ import annotations

import os
import shutil
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.settings import Settings
from dotenv import dotenv_values
from pydantic import ValidationError


def main() -> None:
    file_values = dotenv_values(".env")
    domain = file_values.get("DOMAIN") or os.environ.get("DOMAIN")
    if domain:
        os.environ.setdefault("FRONTEND_ORIGINS", f"https://{domain}")
        os.environ.setdefault("FRONTEND_URL", f"https://{domain}")
        os.environ.setdefault("ALLOWED_HOSTS", domain)
    os.environ["ENVIRONMENT"] = "production"
    os.environ.setdefault("DATABASE_URL", "sqlite:////app/data/cropsense.db")
    os.environ.setdefault("REDIS_USE_RATE_LIMITING", "true")
    try:
        settings = Settings()
    except ValidationError as exc:
        for error in exc.errors(include_url=False, include_input=False):
            location = ".".join(str(part) for part in error["loc"]) or "configuration"
            print(f"FAIL: {location}: {error['msg']}")
        raise SystemExit(1) from None
    errors: list[str] = []

    if not Path(settings.model_path).is_file():
        errors.append(f"model file is missing: {settings.model_path}")
    if shutil.which("docker") is None:
        errors.append("Docker CLI is not installed")

    local_db = Path("cropsense.db")
    if local_db.exists():
        with sqlite3.connect(f"file:{local_db.resolve()}?mode=ro", uri=True) as conn:
            if conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                errors.append("local SQLite integrity check failed")

    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        raise SystemExit(1)
    print("Production preflight passed (secrets were not displayed).")


if __name__ == "__main__":
    main()
