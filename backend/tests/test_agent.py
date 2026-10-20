from app.application.agent import ResearchAgent


class FakeLLM:
    enabled = True

    def __init__(self):
        self.calls = 0

    def complete(self, messages, tools=None, tool_choice=None):
        self.calls += 1
        if self.calls == 1:
            assert tool_choice == "auto"
            return {"choices": [{"message": {"role": "assistant", "tool_calls": [{"id": "call-1", "function": {"name": "read_profit", "arguments": "{}"}}]}}]}
        return {"choices": [{"message": {"role": "assistant", "content": "基于利润工具结果，先验证供应商成本和广告费假设。"}}]}


def test_agent_selects_read_only_tool_before_answering():
    report = {"profit": {"gross_margin": 0.42}, "traceability": {"assumptions": ["synthetic supplier"]}}
    result = ResearchAgent(FakeLLM()).answer("利润空间怎么样？", report)
    assert result["mode"] == "agent"
    assert "read_profit" in result["citations"]
    assert "供应商成本" in result["answer"]
