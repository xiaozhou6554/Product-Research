from __future__ import annotations

import base64
import hashlib
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


MARKETPLACE_COUNTRIES = {
    "US": "US",
    "GB": "GB",
    "DE": "DE",
    "AU": "AU",
}


class EbayBrowseClient:
    """Small eBay Browse API adapter used by the research data layer.

    The API credentials are optional so the local fixture mode remains runnable.
    When configured, product candidates come from the live eBay marketplace.
    """

    def __init__(self) -> None:
        self.client_id = os.getenv("EBAY_CLIENT_ID", "").strip()
        self.client_secret = os.getenv("EBAY_CLIENT_SECRET", "").strip()
        self.environment = os.getenv("EBAY_ENV", "production").strip().lower()
        self._access_token: str | None = None
        self._token_expires_at = 0.0

    @property
    def enabled(self) -> bool:
        return bool(self.client_id and self.client_secret)

    def search_products(self, keyword: str, market: str, limit: int = 10) -> dict[str, Any] | None:
        if not self.enabled:
            return None
        try:
            token = self._get_access_token()
            country = MARKETPLACE_COUNTRIES.get(market.upper(), "US")
            query = urllib.parse.urlencode(
                {"q": keyword, "limit": min(max(limit, 1), 50), "filter": f"deliveryCountry:{country}"}
            )
            body = self._request_json(
                f"{self._api_base}/buy/browse/v1/item_summary/search?{query}",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/json",
                    "X-EBAY-C-MARKETPLACE-ID": f"EBAY_{country}",
                },
            )
            products = [self._normalize_item(item, keyword) for item in body.get("itemSummaries", [])]
            products = [product for product in products if product is not None]
            if not products:
                return None
            fetched_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            raw_record_hash = hashlib.sha256(json.dumps(body, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
            return {
                "products": products,
                "comments": [],
                "evidence": [
                    {
                        "source_type": "ebay_browse_api",
                        "source_version": "ebay-browse-v1",
                        "marketplace": country,
                        "fetched_at": fetched_at,
                        "raw_record_hash": raw_record_hash,
                        "excerpt": f"Live eBay Browse API product search for {keyword}.",
                        "confidence": 0.9,
                        "assumption": False,
                    }
                ],
                "source_version": "ebay-browse-v1",
                "data_notice": "商品候选、价格和链接来自 eBay Browse API；平台未返回的评分、评论与供应商成本不作推断。",
            }
        except (OSError, ValueError, KeyError, urllib.error.HTTPError, json.JSONDecodeError):
            # The research run remains locally reproducible when the optional connector is unavailable.
            return None

    @property
    def _api_base(self) -> str:
        if self.environment == "sandbox":
            return "https://api.sandbox.ebay.com"
        return "https://api.ebay.com"

    def _get_access_token(self) -> str:
        if self._access_token and time.time() < self._token_expires_at:
            return self._access_token
        credentials = base64.b64encode(f"{self.client_id}:{self.client_secret}".encode()).decode()
        body = urllib.parse.urlencode(
            {"grant_type": "client_credentials", "scope": "https://api.ebay.com/oauth/api_scope"}
        ).encode()
        response = self._request_json(
            f"{self._api_base}/identity/v1/oauth2/token",
            data=body,
            headers={
                "Authorization": f"Basic {credentials}",
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
            },
        )
        self._access_token = response["access_token"]
        self._token_expires_at = time.time() + max(60, int(response.get("expires_in", 7200)) - 60)
        return self._access_token

    @staticmethod
    def _normalize_item(item: dict[str, Any], keyword: str) -> dict[str, Any] | None:
        price = item.get("price") or {}
        try:
            price_value = float(price.get("value"))
        except (TypeError, ValueError):
            return None
        title = str(item.get("title") or keyword).strip()
        themes = [str(item.get("condition") or "")]
        themes.extend(str(value) for value in item.get("buyingOptions", [])[:2])
        themes = [theme.replace("_", " ").lower() for theme in themes if theme]
        seller = item.get("seller") or {}
        return {
            "product_id": f"EBAY-{item.get('itemId', title)}",
            "name": title,
            "price": round(price_value, 2),
            "currency": price.get("currency", "USD"),
            "rating": 0,
            "reviews": 0,
            "relevance": 0.0,
            "themes": themes or ["eBay listing"],
            "platform": "ebay",
            "url": item.get("itemWebUrl"),
            "seller_feedback_percentage": seller.get("feedbackPercentage"),
        }

    @staticmethod
    def _request_json(url: str, *, headers: dict[str, str], data: bytes | None = None) -> dict[str, Any]:
        request = urllib.request.Request(url, data=data, headers=headers, method="POST" if data else "GET")
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(request, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("unexpected API response")
        return payload
