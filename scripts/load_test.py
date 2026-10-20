"""Small repeatable concurrency probe for local development, not a production capacity claim."""
from __future__ import annotations

import json
import os
import statistics
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor


BASE = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")


def request(method: str, path: str, data: dict | None = None, token: str | None = None) -> tuple[int, dict]:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(BASE + path, body, headers, method=method)
    with urllib.request.urlopen(req, timeout=10) as response:
        return response.status, json.load(response)


_, auth = request("POST", "/api/v1/auth/login", {"email": "researcher@example.com", "password": "Research123!"})
token = auth["access_token"]


def create(i: int) -> float:
    started = time.perf_counter()
    status, _ = request("POST", "/api/v1/research-runs", {"keyword": f"travel organizer {i}", "market": "US"}, token)
    if status != 202:
        raise RuntimeError(f"unexpected status {status}")
    return time.perf_counter() - started


count = int(os.getenv("LOAD_COUNT", "20"))
with ThreadPoolExecutor(max_workers=min(count, 10)) as pool:
    timings = list(pool.map(create, range(count)))
print(json.dumps({"requests": count, "success": count, "avg_ms": round(statistics.mean(timings) * 1000, 2), "p95_ms": round(sorted(timings)[max(0, int(count * .95) - 1)] * 1000, 2)}, ensure_ascii=False))
