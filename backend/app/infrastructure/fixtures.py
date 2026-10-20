from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any


SOURCE_VERSION = "fixture-2026.10.13"


def evidence(source_type: str, marketplace: str, excerpt: str, *, assumption: bool = False, confidence: float = 0.85) -> dict[str, Any]:
    digest = hashlib.sha256(excerpt.encode("utf-8")).hexdigest()
    return {
        "source_type": source_type,
        "source_version": SOURCE_VERSION,
        "marketplace": marketplace,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "raw_record_hash": digest,
        "excerpt": excerpt,
        "confidence": confidence,
        "assumption": assumption,
    }


def fixture_analysis(keyword: str, market: str) -> dict[str, Any]:
    normalized = keyword.strip().lower()
    # This fixed dataset is deliberately small and versioned, so local tests are reproducible.
    catalog = [
        {"product_id": "P-100", "name": f"{keyword} travel organizer", "price": 29.99, "rating": 4.6, "reviews": 1820, "relevance": 0.96, "themes": ["compact", "durable"]},
        {"product_id": "P-101", "name": f"{keyword} cable pouch", "price": 21.50, "rating": 4.3, "reviews": 910, "relevance": 0.88, "themes": ["lightweight", "zipper"]},
        {"product_id": "P-102", "name": f"{keyword} tech case", "price": 35.00, "rating": 4.1, "reviews": 640, "relevance": 0.82, "themes": ["capacity", "organization"]},
    ]
    if normalized in {"wireless charger", "充电器", "charger"}:
        catalog = [
            {"product_id": "P-200", "name": f"{keyword} 3-in-1 dock", "price": 49.99, "rating": 4.4, "reviews": 2100, "relevance": 0.95, "themes": ["fast charging", "desk setup"]},
            {"product_id": "P-201", "name": f"{keyword} foldable pad", "price": 28.99, "rating": 4.2, "reviews": 1250, "relevance": 0.89, "themes": ["portable", "heat"]},
        ]
    trend_values = [42, 46, 44, 51, 58, 61, 64, 63, 70, 74, 77, 81]
    comments = [
        {"text": "The size is compact and the material feels durable.", "sentiment": "positive", "theme": "durability"},
        {"text": "The zipper is hard to open when the pouch is full.", "sentiment": "negative", "theme": "zipper"},
        {"text": "I would like one more internal pocket for a charger.", "sentiment": "negative", "theme": "capacity"},
        {"text": "Good organization for short business trips.", "sentiment": "positive", "theme": "organization"},
    ]
    keywords = [
        {"term": keyword, "group": "core", "trend": 81},
        {"term": f"{keyword} travel", "group": "use_case", "trend": 68},
        {"term": f"{keyword} compact", "group": "feature", "trend": 59},
        {"term": f"{keyword} organizer", "group": "feature", "trend": 54},
    ]
    suppliers = [
        {"supplier_id": "S-01", "name": "Shenzhen Sample Works", "purchase_cost": 42.0, "moq": 200, "lead_days": 18},
        {"supplier_id": "S-02", "name": "Ningbo Trade Lab", "purchase_cost": 38.5, "moq": 500, "lead_days": 25},
    ]
    return {"trend": {"values": trend_values, "growth": round((trend_values[-1] - trend_values[0]) / trend_values[0], 4), "peak_month": 12}, "products": catalog, "comments": comments, "keywords": keywords, "suppliers": suppliers, "risks": [{"type": "logistics", "level": "medium", "description": "Cross-border delivery time and dimensional weight need validation."}, {"type": "compliance", "level": "low", "description": "Confirm labeling and material claims before listing."}], "evidence": [evidence("google_trends_fixture", market, f"Fixed trend series for {keyword}; search interest is not sales."), evidence("amazon_esci_fixture", market, f"ESCI-like product records matched to {keyword}."), evidence("synthetic_supplier_csv", market, "Supplier cost, MOQ and lead time are synthetic assumptions.", assumption=True, confidence=0.55)], "source_version": SOURCE_VERSION, "data_notice": "固定 fixture 与 synthetic 数据，仅用于研究验证，不代表实时销量。"}
