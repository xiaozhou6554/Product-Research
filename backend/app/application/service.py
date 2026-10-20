from __future__ import annotations

import csv
import io
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any

from app.domain.calculations import calculate_profit, calculate_score
from app.domain.models import NodeStatus, RunStatus
from app.domain.state_machine import assert_transition
from app.infrastructure.fixtures import fixture_analysis
from app.infrastructure.marketplace import EbayBrowseClient
from app.infrastructure.repository import ResearchRepository


NODE_ORDER = ("trend", "products", "comments", "keywords", "suppliers", "risks")
executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="research")


class ResearchService:
    def __init__(self, repo: ResearchRepository) -> None:
        self.repo = repo
        self.cancelled: set[str] = set()
        self.lock = threading.Lock()
        self.marketplace = EbayBrowseClient()

    def create(self, *, tenant_id: str, user_id: str, input_data: dict[str, Any], idempotency_key: str | None) -> dict[str, Any]:
        run = self.repo.create_run(tenant_id=tenant_id, created_by=user_id, input_data=input_data, idempotency_key=idempotency_key)
        if run["status"] == RunStatus.PENDING:
            executor.submit(self.execute, run["id"], tenant_id)
        return run

    def execute(self, run_id: str, tenant_id: str, only_nodes: set[str] | None = None) -> None:
        run = self.repo.get_run(run_id, tenant_id)
        if not run or run["status"] == RunStatus.CANCELLED:
            return
        if run["status"] not in (RunStatus.PENDING, RunStatus.PARTIAL_FAILED, RunStatus.FAILED):
            return
        nodes = run["nodes"]
        if run["status"] == RunStatus.PENDING:
            self.repo.update_run(run_id, tenant_id, status=RunStatus.RUNNING.value)
        analysis = run.get("analysis") or {}
        data = fixture_analysis(run["input"]["keyword"], run["input"]["market"])
        live_products = self.marketplace.search_products(run["input"]["keyword"], run["input"]["market"])
        if live_products:
            data.update(live_products)
            data["data_source"] = "ebay_browse_api"
        else:
            data["data_source"] = "fixture"
        failures: list[str] = []
        for node in NODE_ORDER:
            if only_nodes and node not in only_nodes:
                continue
            if not only_nodes and nodes[node]["status"] == NodeStatus.SUCCEEDED.value:
                continue
            if run_id in self.cancelled:
                self.repo.update_run(run_id, tenant_id, status=RunStatus.CANCELLED.value, nodes=nodes)
                return
            nodes[node]["status"] = NodeStatus.RUNNING.value
            nodes[node]["started_at"] = datetime.now(timezone.utc).isoformat()
            self.repo.update_run(run_id, tenant_id, nodes=nodes)
            try:
                payload = data[node]
                nodes[node]["payload"] = payload
                nodes[node]["status"] = NodeStatus.SUCCEEDED.value
            except Exception as exc:  # noqa: BLE001 - node isolation is intentional
                nodes[node]["status"] = NodeStatus.FAILED.value
                nodes[node]["error_code"] = "NODE_EXECUTION_ERROR"
                nodes[node]["error_message"] = str(exc)
                nodes[node]["retry_count"] = nodes[node].get("retry_count", 0) + 1
                failures.append(node)
            nodes[node]["finished_at"] = datetime.now(timezone.utc).isoformat()
            self.repo.update_run(run_id, tenant_id, nodes=nodes)
        if any(nodes[node]["status"] != NodeStatus.SUCCEEDED.value for node in NODE_ORDER):
            self.repo.update_run(run_id, tenant_id, status=RunStatus.PARTIAL_FAILED.value, nodes=nodes, error={"failed_nodes": failures})
            return
        products = data["products"]
        assumptions = run["input"]
        sale_price = assumptions.get("price_max") or products[0]["price"]
        profit = calculate_profit(sale_price=sale_price, purchase_cost=data["suppliers"][0]["purchase_cost"], first_mile=12.0, platform_fee_rate=0.15, advertising_rate=assumptions.get("ad_rate") or 0.08, tax_rate=0.06, return_rate=assumptions.get("return_rate") or 0.05, exchange_rate=7.2)
        analysis["profit"] = profit.__dict__
        nodes["profit"].update(status=NodeStatus.SUCCEEDED.value, payload=analysis["profit"])
        score = calculate_score(trend=min(100, data["trend"]["growth"] * 100 + 50), competition=72, profit=min(100, max(0, profit.gross_margin * 200)), risk=35, evidence=82)
        analysis["score"] = score.__dict__
        nodes["score"].update(status=NodeStatus.SUCCEEDED.value, payload=analysis["score"])
        self.repo.save_evidence(run_id, tenant_id, data["evidence"])
        nodes["evidence"].update(status=NodeStatus.SUCCEEDED.value, payload={"count": len(data["evidence"])})
        report = self._build_report(run, data, analysis)
        analysis["report"] = report
        nodes["report"].update(status=NodeStatus.SUCCEEDED.value, payload={"version": report["version"]})
        self.repo.save_report(run_id, tenant_id, report)
        self.repo.update_run(run_id, tenant_id, status=RunStatus.SUCCEEDED.value, nodes=nodes, analysis=analysis)

    def _build_report(self, run: dict[str, Any], data: dict[str, Any], analysis: dict[str, Any]) -> dict[str, Any]:
        notice = data.get("data_notice", "固定 fixture 与 synthetic 数据，仅用于研究验证，不代表实时销量。")
        if data.get("data_source") == "ebay_browse_api":
            notice = f"{notice} 供应商成本、头程和税率仍为 synthetic 假设。"
        return {"version": 1, "run_id": run["id"], "generated_at": datetime.now(timezone.utc).isoformat(), "scope": {"keyword": run["input"]["keyword"], "market": run["input"]["market"], "data_notice": notice}, "overview": {"headline": f"{run['input']['keyword']} 在 {run['input']['market']} 的机会初筛", "recommendation": analysis["score"]["recommendation"], "grade": analysis["score"]["grade"]}, "trend": data["trend"], "products": data["products"], "comments": data["comments"], "keywords": data["keywords"], "suppliers": data["suppliers"], "risks": data["risks"], "profit": analysis["profit"], "score": analysis["score"], "traceability": {"evidence_count": len(data["evidence"]), "source_version": data.get("source_version", "fixture-2026.10.13"), "data_source": data.get("data_source", "fixture"), "assumptions": ["供应商成本、头程和税率来自 synthetic 假设", "搜索兴趣不等于销量", "利润使用固定汇率 7.2 CNY/USD"]}}

    def get(self, run_id: str, tenant_id: str) -> dict[str, Any] | None:
        return self.repo.get_run(run_id, tenant_id)

    def retry(self, run_id: str, tenant_id: str) -> dict[str, Any]:
        run = self.repo.get_run(run_id, tenant_id)
        if not run:
            raise KeyError("run not found")
        if run["status"] not in (RunStatus.PARTIAL_FAILED.value, RunStatus.FAILED.value):
            raise ValueError("only failed or partial-failed runs can be retried")
        failed = {key for key, value in run["nodes"].items() if value["status"] == NodeStatus.FAILED.value}
        self.repo.update_run(run_id, tenant_id, status=RunStatus.RUNNING.value)
        executor.submit(self.execute, run_id, tenant_id, failed or None)
        return self.repo.get_run(run_id, tenant_id)

    def cancel(self, run_id: str, tenant_id: str) -> dict[str, Any]:
        run = self.repo.get_run(run_id, tenant_id)
        if not run:
            raise KeyError("run not found")
        if run["status"] in (RunStatus.SUCCEEDED.value, RunStatus.CANCELLED.value):
            raise ValueError("run is already terminal")
        self.cancelled.add(run_id)
        self.repo.update_run(run_id, tenant_id, status=RunStatus.CANCELLED.value)
        return self.repo.get_run(run_id, tenant_id)

    def export_csv(self, run_id: str, tenant_id: str) -> str:
        report = self.repo.get_report(run_id, tenant_id)
        if not report:
            raise KeyError("report not found")
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["section", "metric", "value", "traceability"])
        for section in ("overview", "trend", "profit", "score"):
            for key, value in report.get(section, {}).items():
                writer.writerow([section, key, value, report["traceability"]["source_version"]])
        return output.getvalue()
