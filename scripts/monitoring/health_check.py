#!/usr/bin/env python3
"""Health monitoring script — checks all system endpoints and dependencies."""

from __future__ import annotations

import sys
import time
from typing import Any, Dict, List

try:
    import httpx
except ImportError:
    print("httpx not installed — install with: pip install httpx")
    sys.exit(1)

BASE_URL = "http://localhost:8000"
TIMEOUT = 10.0


def check_endpoint(url: str, name: str) -> Dict[str, Any]:
    """Perform a GET check against *url*."""
    try:
        start = time.monotonic()
        resp = httpx.get(url, timeout=TIMEOUT)
        elapsed = time.monotonic() - start
        return {
            "name": name,
            "url": url,
            "status": "healthy" if resp.status_code == 200 else "degraded",
            "status_code": resp.status_code,
            "latency_ms": round(elapsed * 1000, 2),
        }
    except Exception as exc:  # noqa: BLE001
        return {"name": name, "url": url, "status": "unhealthy", "error": str(exc)}


def main() -> None:
    checks: List[Dict[str, Any]] = [
        check_endpoint(f"{BASE_URL}/health", "basic_health"),
        check_endpoint(f"{BASE_URL}/health/detailed", "detailed_health"),
        check_endpoint(f"{BASE_URL}/api/v1/agents/", "agents_list"),
    ]

    all_healthy = all(c["status"] == "healthy" for c in checks)

    print("\n=== AGI System Health Report ===")
    for check in checks:
        icon = "✓" if check["status"] == "healthy" else "✗"
        latency = check.get("latency_ms", "N/A")
        print(f"  {icon} {check['name']}: {check['status']} ({latency}ms)")
    print(f"\nOverall: {'HEALTHY' if all_healthy else 'DEGRADED'}")

    sys.exit(0 if all_healthy else 1)


if __name__ == "__main__":
    main()
