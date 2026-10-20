from app.infrastructure.marketplace import EbayBrowseClient


def test_ebay_item_is_normalized_without_inventing_reviews():
    product = EbayBrowseClient._normalize_item(
        {
            "itemId": "v1|123|0",
            "title": "Travel organizer",
            "price": {"value": "29.99", "currency": "USD"},
            "condition": "NEW",
            "buyingOptions": ["FIXED_PRICE"],
            "seller": {"feedbackPercentage": "99.8"},
            "itemWebUrl": "https://www.ebay.com/itm/123",
        },
        "travel organizer",
    )
    assert product is not None
    assert product["platform"] == "ebay"
    assert product["price"] == 29.99
    assert product["reviews"] == 0
    assert product["url"].endswith("/123")
