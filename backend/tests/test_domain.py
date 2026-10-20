from app.domain.calculations import calculate_growth, calculate_profit, calculate_score
from app.domain.models import RunStatus
from app.domain.state_machine import assert_transition


def test_profit_includes_all_configured_costs():
    result = calculate_profit(sale_price=50, purchase_cost=20, first_mile=5, platform_fee_rate=.15, advertising_rate=.1, tax_rate=.06, return_rate=.05, exchange_rate=7.2)
    assert result.revenue_cny == 360
    assert result.platform_fee == 54
    assert result.advertising_fee == 36
    assert result.return_cost == 18
    assert result.gross_profit_cny == 225.5


def test_growth_and_score_grade_are_deterministic():
    assert calculate_growth([10, 12, 15]) == .5
    assert calculate_score(trend=90, competition=80, profit=90, risk=10, evidence=90).grade == "A"
    assert calculate_score(trend=20, competition=20, profit=10, risk=90, evidence=20).grade == "D"


def test_state_machine_rejects_terminal_transition():
    assert_transition(RunStatus.PENDING, RunStatus.RUNNING)
    try:
        assert_transition(RunStatus.SUCCEEDED, RunStatus.RUNNING)
    except ValueError:
        pass
    else:
        raise AssertionError("terminal transition should fail")
