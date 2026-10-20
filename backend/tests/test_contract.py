from app.infrastructure.fixtures import fixture_analysis


def test_fixture_adapter_contract():
    result = fixture_analysis("travel organizer", "US")
    assert {"trend", "products", "comments", "keywords", "suppliers", "risks", "evidence"} <= result.keys()
    assert all(item["price"] > 0 for item in result["products"])
    assert all(0 <= item["confidence"] <= 1 for item in result["evidence"])
