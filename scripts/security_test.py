"""Dependency-light authorization and tenant-isolation smoke test."""
from __future__ import annotations

import json
import os
import urllib.request


BASE = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")


def call(path: str, method: str = "GET", data: dict | None = None, token: str | None = None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(BASE + path, json.dumps(data).encode() if data else None, headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read())


status, auth = call("/api/v1/auth/login", "POST", {"email": "researcher@example.com", "password": "Research123!"})
assert status == 200
status, created = call("/api/v1/research-runs", "POST", {"keyword": "security fixture", "market": "US"}, auth["access_token"])
assert status == 202
other_status, _ = call(f"/api/v1/research-runs/{created['run_id']}", token=call("/api/v1/auth/login", "POST", {"email": "other@example.com", "password": "Other123!"})[1]["access_token"])
assert other_status == 404
print(json.dumps({"unauthenticated": call("/api/v1/research-runs/run_unknown")[0], "cross_tenant_read": other_status, "status": "passed"}))
