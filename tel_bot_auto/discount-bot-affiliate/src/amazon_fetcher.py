"""
Amazon Fetcher — Uses the Amazon Product Advertising API 5.0 (PAAPI)
to find discounted products across configured categories.

Requirements:
  - Amazon Associates account: https://affiliate-program.amazon.in
  - PAAPI access (request from Associates dashboard after 3+ qualifying sales)
  - Set AMAZON_ACCESS_KEY, AMAZON_SECRET_KEY, AMAZON_PARTNER_TAG in .env

PAAPI Docs: https://webservices.amazon.com/paapi5/documentation/
"""

import hashlib
import hmac
import json
import logging
import os
import time
from datetime import datetime, timezone
from urllib.parse import quote
import aiohttp

logger = logging.getLogger(__name__)

# Amazon PAAPI endpoints by marketplace
ENDPOINTS = {
    "IN": "webservices.amazon.in",   # India (default)
    "US": "webservices.amazon.com",
    "UK": "webservices.amazon.co.uk",
    "DE": "webservices.amazon.de",
}

CURRENCIES = {
    "IN": "₹",
    "US": "$",
    "UK": "£",
    "DE": "€",
}

STORE_URLS = {
    "IN": "https://www.amazon.in/dp/",
    "US": "https://www.amazon.com/dp/",
    "UK": "https://www.amazon.co.uk/dp/",
    "DE": "https://www.amazon.de/dp/",
}


class AmazonFetcher:
    def __init__(self):
        self.access_key = os.getenv("AMAZON_ACCESS_KEY", "")
        self.secret_key = os.getenv("AMAZON_SECRET_KEY", "")
        self.partner_tag = os.getenv("AMAZON_PARTNER_TAG", "")  # e.g. mytag-21
        self.marketplace = os.getenv("AMAZON_MARKETPLACE", "IN").upper()
        self.categories = [
            c.strip()
            for c in os.getenv(
                "AMAZON_CATEGORIES",
                "Electronics,Computers,HomeAndKitchen,Fashion,Sports",
            ).split(",")
            if c.strip()
        ]
        self.min_discount = int(os.getenv("MIN_DISCOUNT_PERCENT", 20))
        self.host = ENDPOINTS.get(self.marketplace, ENDPOINTS["IN"])
        self.currency = CURRENCIES.get(self.marketplace, "₹")
        self.store_url = STORE_URLS.get(self.marketplace, STORE_URLS["IN"])
        self.enabled = bool(self.access_key and self.secret_key and self.partner_tag)

    async def fetch_deals(self) -> list[dict]:
        if not self.enabled:
            logger.warning(
                "Amazon PAAPI credentials not set. Using demo Amazon deals."
            )
            return self._demo_deals()

        deals = []
        for category in self.categories:
            try:
                batch = await self._search_category(category)
                deals.extend(batch)
                await asyncio.sleep(1)  # PAAPI rate limit: 1 req/sec
            except Exception as e:
                logger.error(f"Amazon category '{category}' failed: {e}")

        logger.info(f"Amazon: fetched {len(deals)} deals")
        return deals

    async def _search_category(self, category: str) -> list[dict]:
        """Search a category for items on sale using SearchItems API."""
        path = "/paapi5/searchitems"
        payload = {
            "PartnerTag": self.partner_tag,
            "PartnerType": "Associates",
            "Marketplace": f"www.amazon.{self.marketplace.lower()}",
            "SearchIndex": category,
            "Resources": [
                "Images.Primary.Large",
                "ItemInfo.Title",
                "Offers.Listings.Price",
                "Offers.Listings.SavingBasis",
                "Offers.Listings.Promotions",
                "Offers.Summaries.LowestPrice",
            ],
            "MinSavingPercent": self.min_discount,
            "SortBy": "Featured",
            "ItemCount": 10,
        }

        headers, signed_payload = self._sign_request("POST", path, payload)

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"https://{self.host}{path}",
                headers=headers,
                data=signed_payload,
                timeout=aiohttp.ClientTimeout(total=20),
            ) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    logger.warning(f"Amazon API {resp.status}: {text[:300]}")
                    return []
                data = await resp.json()

        items = data.get("SearchResult", {}).get("Items", [])
        return [self._normalize(item, category) for item in items if self._has_discount(item)]

    def _has_discount(self, item: dict) -> bool:
        listings = item.get("Offers", {}).get("Listings", [])
        if not listings:
            return False
        listing = listings[0]
        saving = listing.get("SavingBasis", {})
        return bool(saving.get("Amount"))

    def _normalize(self, item: dict, category: str) -> dict:
        asin = item.get("ASIN", "")
        title = item.get("ItemInfo", {}).get("Title", {}).get("DisplayValue", "Product")

        listings = item.get("Offers", {}).get("Listings", [])
        listing = listings[0] if listings else {}
        price_data = listing.get("Price", {})
        saving_data = listing.get("SavingBasis", {})

        sale_price = price_data.get("Amount", 0)
        orig_price = saving_data.get("Amount", sale_price)
        discount_pct = round((1 - sale_price / orig_price) * 100) if orig_price > 0 else 0

        image = (
            item.get("Images", {})
            .get("Primary", {})
            .get("Large", {})
            .get("URL", "")
        )

        # Build affiliate URL
        affiliate_url = (
            f"{self.store_url}{asin}?tag={self.partner_tag}"
            if self.partner_tag else f"{self.store_url}{asin}"
        )

        savings_amount = orig_price - sale_price

        return {
            "id": f"amz_{asin}",
            "platform": "Amazon",
            "platform_emoji": "🛒",
            "name": title,
            "category": category,
            "original_price": orig_price,
            "sale_price": sale_price,
            "discount_percent": discount_pct,
            "savings_amount": savings_amount,
            "currency": self.currency,
            "image_url": image,
            "product_url": affiliate_url,
            "score": discount_pct + (savings_amount / 100),  # rank by value
        }

    def _sign_request(self, method: str, path: str, payload: dict):
        """AWS Signature Version 4 signing for PAAPI 5.0."""
        region = "us-east-1"
        service = "ProductAdvertisingAPI"
        amz_target = "com.amazon.paapi5.v1.ProductAdvertisingAPIv1.SearchItems"

        now = datetime.now(timezone.utc)
        amz_date = now.strftime("%Y%m%dT%H%M%SZ")
        date_stamp = now.strftime("%Y%m%d")

        payload_str = json.dumps(payload, separators=(",", ":"))
        payload_hash = hashlib.sha256(payload_str.encode()).hexdigest()

        headers_to_sign = {
            "content-encoding": "amz-1.0",
            "content-type": "application/json; charset=utf-8",
            "host": self.host,
            "x-amz-date": amz_date,
            "x-amz-target": amz_target,
        }

        canonical_headers = "".join(
            f"{k}:{v}\n" for k, v in sorted(headers_to_sign.items())
        )
        signed_headers = ";".join(sorted(headers_to_sign.keys()))

        canonical_request = "\n".join([
            method,
            path,
            "",  # query string
            canonical_headers,
            signed_headers,
            payload_hash,
        ])

        credential_scope = f"{date_stamp}/{region}/{service}/aws4_request"
        string_to_sign = "\n".join([
            "AWS4-HMAC-SHA256",
            amz_date,
            credential_scope,
            hashlib.sha256(canonical_request.encode()).hexdigest(),
        ])

        def sign(key, msg):
            return hmac.new(key, msg.encode(), hashlib.sha256).digest()

        signing_key = sign(
            sign(
                sign(
                    sign(f"AWS4{self.secret_key}".encode(), date_stamp),
                    region,
                ),
                service,
            ),
            "aws4_request",
        )

        signature = hmac.new(signing_key, string_to_sign.encode(), hashlib.sha256).hexdigest()
        auth = (
            f"AWS4-HMAC-SHA256 Credential={self.access_key}/{credential_scope}, "
            f"SignedHeaders={signed_headers}, Signature={signature}"
        )

        final_headers = {**headers_to_sign, "Authorization": auth}
        return final_headers, payload_str

    def _demo_deals(self) -> list[dict]:
        """Realistic demo Amazon India deals for testing."""
        return [
            {
                "id": "amz_B0CHX3QBCH",
                "platform": "Amazon",
                "platform_emoji": "🛒",
                "name": "Samsung Galaxy S23 FE 5G (128GB, Cream)",
                "category": "Electronics",
                "original_price": 54999,
                "sale_price": 34999,
                "discount_percent": 36,
                "savings_amount": 20000,
                "currency": "₹",
                "image_url": "https://images.unsplash.com/photo-1610945265064-0e34e5519bbf?w=600",
                "product_url": "https://www.amazon.in/dp/B0CHX3QBCH?tag=yourtag-21",
                "score": 36 + 200,
            },
            {
                "id": "amz_B09G9HD6PD",
                "platform": "Amazon",
                "platform_emoji": "🛒",
                "name": "boAt Rockerz 450 Bluetooth Headphone (Navy Blue)",
                "category": "Electronics",
                "original_price": 3490,
                "sale_price": 999,
                "discount_percent": 71,
                "savings_amount": 2491,
                "currency": "₹",
                "image_url": "https://images.unsplash.com/photo-1583394838336-acd977736f90?w=600",
                "product_url": "https://www.amazon.in/dp/B09G9HD6PD?tag=yourtag-21",
                "score": 71 + 24,
            },
            {
                "id": "amz_B0BX58XK7G",
                "platform": "Amazon",
                "platform_emoji": "🛒",
                "name": "Redmi Note 13 Pro 5G (Aurora Purple, 8GB RAM, 256GB)",
                "category": "Electronics",
                "original_price": 31999,
                "sale_price": 22999,
                "discount_percent": 28,
                "savings_amount": 9000,
                "currency": "₹",
                "image_url": "https://images.unsplash.com/photo-1511707171634-5f897ff02aa9?w=600",
                "product_url": "https://www.amazon.in/dp/B0BX58XK7G?tag=yourtag-21",
                "score": 28 + 90,
            },
        ]


# Fix missing asyncio import used in fetch_deals
import asyncio
