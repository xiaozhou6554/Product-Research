from __future__ import annotations

import json
from typing import Any, Callable

from app.infrastructure.llm import LLMClient


class ResearchAgent:
    """Evidence-grounded tool-calling agent for report Q&A.

    The model chooses read-only tools; deterministic calculations and source
    records stay outside the model. This keeps the Agent useful without
    allowing it to invent prices, margins, scores, or data sources.
    """

    def __init__(self, llm: LLMClient) -> None:
        self.llm = llm

    def answer(self, question: str, report: dict[str, Any]) -> dict[str, Any] | None:
        if not self.llm.enabled:
            return None

        tools: list[dict[str, Any]] = [
            {
                "type": "function",
                "function": {
                    "name": "read_profit",
                    "description": "读取已完成的利润计算结果和假设。",
                    "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "read_trend",
                    "description": "读取搜索趋势和关键词数据。",
                    "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "read_products",
                    "description": "读取候选商品、价格、评分和评论量。",
                    "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "read_risks",
                    "description": "读取风险、供应商和证据追溯信息。",
                    "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
                },
            },
        ]
        system = (
            "你是跨境电商选品研究 Agent。先判断用户问题是否需要研究数据；需要时自主选择一个或多个合适的研究工具，再回答。"
            "只能使用工具返回的事实；不得编造销量、平台排名、法律结论或外部来源。"
            "利润、评分和推荐等级是系统已计算结果，不要自行重算或修改。"
            "回答中文，直接回答用户问题，给出必要的数据和结论即可。不要单独输出依据、假设、验证建议等栏目。"
            "不要提及工具、工具名称、调用过程、内部实现或英文函数名，直接面向用户回答。"
        )
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system},
            {"role": "user", "content": question},
        ]
        citations: list[str] = []
        for step in range(3):
            response = self.llm.complete(messages, tools=tools, tool_choice="auto")
            if not response:
                return None
            message = response.get("choices", [{}])[0].get("message", {})
            tool_calls = message.get("tool_calls") or []
            if not tool_calls:
                content = message.get("content")
                if isinstance(content, str) and content.strip():
                    return {"answer": content.strip(), "citations": citations, "mode": "agent"}
                return None

            messages.append(message)
            for call in tool_calls:
                function = call.get("function", {})
                name = function.get("name", "")
                payload = self._tool_result(name, report)
                if payload is None:
                    return None
                citations.append(name)
                messages.append({"role": "tool", "tool_call_id": call.get("id", name), "name": name, "content": json.dumps(payload, ensure_ascii=False)})
        return None

    @staticmethod
    def _tool_result(name: str, report: dict[str, Any]) -> dict[str, Any] | None:
        tools: dict[str, Callable[[], dict[str, Any]]] = {
            "read_profit": lambda: {"profit": report.get("profit"), "assumptions": report.get("traceability", {}).get("assumptions", [])},
            "read_trend": lambda: {"trend": report.get("trend"), "keywords": report.get("keywords")},
            "read_products": lambda: {"products": report.get("products"), "comments": report.get("comments")},
            "read_risks": lambda: {"risks": report.get("risks"), "suppliers": report.get("suppliers"), "traceability": report.get("traceability")},
        }
        handler = tools.get(name)
        return handler() if handler else None
