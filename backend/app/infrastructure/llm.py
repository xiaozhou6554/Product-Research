from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from typing import Any


class LLMClient:
    """OpenAI-compatible DeepSeek transport used by the real ResearchAgent."""

    def __init__(self) -> None:
        # Accept the project's generic name and the common system variable
        # name used by the user's DeepSeek installation. Never log this value.
        self.api_key = (os.getenv("LLM_API_KEY", "").strip() or os.getenv("DEEPSEEK_API_KEY", "").strip())
        self.base_url = (os.getenv("LLM_BASE_URL", "").strip() or os.getenv("DEEPSEEK_BASE_URL", "").strip() or "https://api.deepseek.com").rstrip("/")
        self.model = os.getenv("LLM_MODEL", "").strip() or os.getenv("DEEPSEEK_MODEL", "").strip() or "deepseek-flash"
        self.proxy = os.getenv("LLM_PROXY", "").strip()
        self.timeout = float(os.getenv("LLM_TIMEOUT_SECONDS", "15"))
        self.last_error: str | None = None

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    def answer(self, question: str, report: dict[str, Any]) -> str | None:
        if not self.enabled:
            return None
        context = json.dumps({
            "overview": report.get("overview"),
            "trend": report.get("trend"),
            "products": report.get("products"),
            "profit": report.get("profit"),
            "risks": report.get("risks"),
            "traceability": report.get("traceability"),
        }, ensure_ascii=False)
        prompt = f"""你是跨境电商选品研究 Agent。只根据给定报告回答问题，不得编造实时销量、来源或法律结论。回答使用中文，直接回答用户问题，给出必要的数据和结论即可。不要单独输出依据、假设、验证建议、工具或内部实现等栏目，也不要提及英文函数名。\n\n报告上下文：{context}\n\n用户问题：{question}"""
        body = json.dumps({"model": self.model, "temperature": 0.2, "max_tokens": 800, "messages": [{"role": "system", "content": "你是一个严谨、可追溯的研究助理。"}, {"role": "user", "content": prompt}]}, ensure_ascii=False).encode("utf-8")
        payload = self._request(body)
        if payload is None:
            return None
        try:
            content = payload["choices"][0]["message"]["content"]
            return content.strip() if isinstance(content, str) and content.strip() else None
        except (KeyError, IndexError, TypeError):
            return None

    def complete(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None = None, tool_choice: str | dict[str, Any] | None = None) -> dict[str, Any] | None:
        if not self.enabled:
            return None
        request_body: dict[str, Any] = {"model": self.model, "temperature": 0.2, "max_tokens": 800, "messages": messages}
        if tools:
            request_body["tools"] = tools
            request_body["tool_choice"] = tool_choice or "auto"
        return self._request(json.dumps(request_body, ensure_ascii=False).encode("utf-8"))

    def _request(self, body: bytes) -> dict[str, Any] | None:
        self.last_error = None
        request = urllib.request.Request(f"{self.base_url}/chat/completions", data=body, headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}, method="POST")
        try:
            # Do not inherit stale HTTP(S)_PROXY values from desktop proxy tools.
            # An explicit LLM_PROXY remains available when a proxy is actually needed.
            proxy_handler = urllib.request.ProxyHandler({"http": self.proxy, "https": self.proxy}) if self.proxy else urllib.request.ProxyHandler({})
            opener = urllib.request.build_opener(proxy_handler)
            with opener.open(request, timeout=self.timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")[:300]
            self.last_error = f"HTTP {error.code}: {detail}"
        except (urllib.error.URLError, TimeoutError) as error:
            self.last_error = f"{type(error).__name__}: {error}"
        except json.JSONDecodeError as error:
            self.last_error = f"Invalid JSON response: {error}"
        if self.last_error:
            print(f"LLM request failed ({self.model}): {self.last_error}", file=sys.stderr)
            return None
