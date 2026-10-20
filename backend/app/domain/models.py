from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Role(StrEnum):
    ADMIN = "admin"
    RESEARCHER = "researcher"
    VIEWER = "viewer"


class RunStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    PARTIAL_FAILED = "PARTIAL_FAILED"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class NodeStatus(StrEnum):
    NOT_STARTED = "NOT_STARTED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


@dataclass(frozen=True)
class ResearchInput:
    keyword: str
    market: str = "US"
    price_min: float | None = None
    price_max: float | None = None
    target_margin: float | None = None
    supply_requirements: str | None = None
    shipping_method: str = "sea"
    ad_rate: float | None = None
    return_rate: float | None = None
    depth: str = "standard"


@dataclass
class NodeResult:
    name: str
    status: NodeStatus = NodeStatus.NOT_STARTED
    started_at: str | None = None
    finished_at: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    retry_count: int = 0
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Evidence:
    evidence_id: str
    tenant_id: str
    source_type: str
    source_version: str
    marketplace: str
    fetched_at: str
    raw_record_hash: str
    excerpt: str
    confidence: float
    assumption: bool = False


@dataclass(frozen=True)
class ProfitCalculation:
    sale_price: float
    purchase_cost: float
    first_mile: float
    platform_fee: float
    advertising_fee: float
    tax: float
    return_cost: float
    exchange_rate: float
    revenue_cny: float
    total_cost_cny: float
    gross_profit_cny: float
    gross_margin: float
    break_even_price: float


@dataclass(frozen=True)
class ScoreResult:
    trend_score: float
    competition_score: float
    profit_score: float
    risk_score: float
    evidence_score: float
    total_score: float
    grade: str
    recommendation: str

