#!/usr/bin/env python3
"""Restore a custom-format dump into the Compose database (destructive)."""
from __future__ import annotations

from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python scripts/restore_postgres.py path/to/backup.dump", file=sys.stderr)
        return 2
    backup = Path(sys.argv[1]).expanduser().resolve()
    if not backup.is_file():
        print(f"Backup file not found: {backup}", file=sys.stderr)
        return 2
    print("WARNING: this replaces the current CodeGuard PostgreSQL database.")
    if input("Type RESTORE_CODEGUARD to continue: ") != "RESTORE_CODEGUARD":
        print("Restore cancelled.")
        return 1
    recreate = [
        "docker", "compose", "exec", "-T", "db", "sh", "-c",
        'dropdb -U "$POSTGRES_USER" --if-exists "$POSTGRES_DB" && '
        'createdb -U "$POSTGRES_USER" "$POSTGRES_DB"',
    ]
    restore = [
        "docker", "compose", "exec", "-T", "db", "sh", "-c",
        'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --no-owner --clean --if-exists',
    ]
    try:
        subprocess.run(recreate, cwd=ROOT, check=True)
        with backup.open("rb") as stream:
            subprocess.run(restore, cwd=ROOT, stdin=stream, check=True)
    except (OSError, subprocess.CalledProcessError) as exc:
        print(f"Restore failed: {exc}", file=sys.stderr)
        return 1
    print("Restore completed. Run the deployment smoke test and verify application workflows.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
