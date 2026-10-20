"""Dependency-light smoke check for a running local API."""
from __future__ import annotations

import json
import os
import sys
import urllib.request


base = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")
payload = json.dumps({"email": "researcher@example.com", "password": "Research123!"}).encode()
request = urllib.request.Request(base + "/api/v1/auth/login", payload, {"Content-Type": "application/json"}, method="POST")
with urllib.request.urlopen(request, timeout=5) as response:
    login = json.load(response)
token = login["access_token"]
headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
body = json.dumps({"keyword": "travel organizer", "market": "US"}).encode()
request = urllib.request.Request(base + "/api/v1/research-runs", body, headers, method="POST")
with urllib.request.urlopen(request, timeout=5) as response:
    run = json.load(response)
print(json.dumps({"health": "ok", "run_id": run["run_id"], "status": run["status"]}, ensure_ascii=False))
