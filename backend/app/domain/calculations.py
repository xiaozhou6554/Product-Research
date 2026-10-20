from __future__ import annotations

from .models import ProfitCalculation, ScoreResult


def calculate_profit(
    *,
    sale_price: float,
    purchase_cost: float,
    first_mile: float,
    platform_fee_rate: float,
    advertising_rate: float,
    tax_rate: float,
    return_rate: float,
    exchange_rate: float,
) -> ProfitCalculation:
    """Deterministic landed-cost calculation. Amounts are in CNY except sale_price."""
    if sale_price <= 0 or exchange_rate <= 0:
        raise ValueError("sale_price and exchange_rate must be positive")
    rates = (platform_fee_rate, advertising_rate, tax_rate, return_rate)
    if any(rate < 0 or rate > 1 for rate in rates):
        raise ValueError("cost rates must be between 0 and 1")
    revenue_cny = sale_price * exchange_rate
    platform_fee = revenue_cny * platform_fee_rate
    advertising_fee = revenue_cny * advertising_rate
    tax = (purchase_cost + first_mile) * tax_rate
    return_cost = revenue_cny * return_rate
    total_cost = purchase_cost + first_mile + platform_fee + advertising_fee + tax + return_cost
    gross_profit = revenue_cny - total_cost
    margin = gross_profit / revenue_cny
    variable_rate = platform_fee_rate + advertising_rate + return_rate
    fixed_cost = purchase_cost + first_mile + tax
    break_even = fixed_cost / max(1 - variable_rate, 0.0001) / exchange_rate
    return ProfitCalculation(
        sale_price=round(sale_price, 2),
        purchase_cost=round(purchase_cost, 2),
        first_mile=round(first_mile, 2),
        platform_fee=round(platform_fee, 2),
        advertising_fee=round(advertising_fee, 2),
        tax=round(tax, 2),
        return_cost=round(return_cost, 2),
        exchange_rate=round(exchange_rate, 4),
        revenue_cny=round(revenue_cny, 2),
        total_cost_cny=round(total_cost, 2),
        gross_profit_cny=round(gross_profit, 2),
        gross_margin=round(margin, 4),
        break_even_price=round(break_even, 2),
    )


def calculate_score(*, trend: float, competition: float, profit: float, risk: float, evidence: float) -> ScoreResult:
    """All inputs are normalized to 0..100. Higher risk input means more risk."""
    values = (trend, competition, profit, risk, evidence)
    if any(value < 0 or value > 100 for value in values):
        raise ValueError("score components must be between 0 and 100")
    total = trend * 0.25 + competition * 0.20 + profit * 0.30 + (100 - risk) * 0.15 + evidence * 0.10
    total = round(total, 2)
    if total >= 80:
        grade, recommendation = "A", "优先验证：需求与利润表现较好，主要风险可控"
    elif total >= 65:
        grade, recommendation = "B", "谨慎验证：存在机会，需补充数据或验证竞争风险"
    elif total >= 50:
        grade, recommendation = "C", "暂不优先：指标一般或证据不足"
    else:
        grade, recommendation = "D", "高风险：利润、合规或供应链风险明显"
    return ScoreResult(trend, competition, profit, risk, evidence, total, grade, recommendation)


def calculate_growth(values: list[float]) -> float:
    if len(values) < 2 or values[0] == 0:
        return 0.0
    return round((values[-1] - values[0]) / abs(values[0]), 4)
