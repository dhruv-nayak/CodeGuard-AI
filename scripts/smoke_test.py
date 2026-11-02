#!/usr/bin/env python3
"""Small post-deployment HTTP smoke test; not a security or load test."""
from __future__ import annotations

import sys
import urllib.error
import urllib.request


def check(url: str, expected_status: int = 200, contains: bytes | None = None) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": "CodeGuard-SmokeTest/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            body = response.read(1_000_000)
            if response.status != expected_status:
                raise RuntimeError(f"{url}: expected HTTP {expected_status}, got {response.status}")
            if contains and contains not in body:
                raise RuntimeError(f"{url}: expected response marker was not found")
            print(f"PASS {response.status} {url}")
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"{url}: HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"{url}: connection failed: {exc.reason}") from exc


def main() -> int:
    base = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000").rstrip("/")
    try:
        check(f"{base}/api/v1/health/live", contains=b'"status":"ok"')
        check(f"{base}/api/v1/health/ready", contains=b'"status":"ready"')
        check(base + "/", contains=b"CodeGuard AI")
    except RuntimeError as exc:
        print(f"FAIL {exc}", file=sys.stderr)
        return 1
    print("Smoke test passed. This does not replace authenticated workflow or security testing.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
