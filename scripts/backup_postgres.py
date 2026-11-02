#!/usr/bin/env python3
"""Create a raw custom-format PostgreSQL dump from the Compose db service."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    output_dir = ROOT / "backups"
    output_dir.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    output = output_dir / f"codeguard_{stamp}.dump"
    command = [
        "docker", "compose", "exec", "-T", "db", "sh", "-c",
        'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc',
    ]
    try:
        with output.open("wb") as stream:
            subprocess.run(command, cwd=ROOT, stdout=stream, check=True)
        output.chmod(0o600)
    except (OSError, subprocess.CalledProcessError) as exc:
        output.unlink(missing_ok=True)
        print(f"Backup failed: {exc}", file=sys.stderr)
        return 1
    print(f"Backup created: {output.relative_to(ROOT)}")
    print("Store this file encrypted and verify a restore before relying on it.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
