"""
Flipkart Fetcher — Uses the Flipkart Affiliate API to find discounted products.

Requirements:
  - Flipkart Affiliate account: https://affiliate.flipkart.com
  - Get your Tracking ID and Token from the affiliate dashboard
  - Set FLIPKART_AFFILIATE_ID and FLIPKART_AFFILIATE_TOKEN in .env

API Docs: https://affiliate.flipkart.com/api-docs/
"""

import asyncio
import logging
import os
import aiohttp

logger = logging.getLogger(__name__)

FLIPKART_API_BASE = "https://affiliate-api.flipkart.io/affiliate"


class FlipkartFetcher:
    def __init__(self):
        self.affiliate_id = os.getenv("FLIPKART_AFFILIATE_ID", "")
        self.affiliate_token = os.getenv("FLIPKART_AFFILIATE_TOKEN", "")
        self.categories = [
            c.strip()
            for c in os.getenv(
                "FLIPKART_CATEGORIES",
                "mobiles,laptops,televisions,audio,cameras",
            ).split(",")
            if c.strip()
        ]
        self.min_discount = int(os.getenv("MIN_DISCOUNT_PERCENT", 20))
        self.enabled = bool(self.affiliate_id and self.affiliate_token)

    async def fetch_deals(self) -> list[dict]:
        if not self.enabled:
            logger.warning(
                "Flipkart credentials not set. Using demo Flipkart deals."
            )
            return self._demo_deals()

        deals = []
        for category in self.categories:
            try:
                batch = await self._fetch_category(category)
                deals.extend(batch)
                await asyncio.sleep(0.5)
            except Exception as e:
                logger.error(f"Flipkart category '{category}' failed: {e}")

        logger.info(f"Flipkart: fetched {len(deals)} deals")
        return deals

    async def _fetch_category(self, category: str) -> list[dict]:
        """Fetch top deals for a Flipkart category."""
        url = f"{FLIPKART_API_BASE}/offers/v1/deals"
        headers = {
            "Fk-Affiliate-Id": self.affiliate_id,
            "Fk-Affiliate-Token": self.affiliate_token,
        }
        params = {
            "category": category,
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(
                url,
                headers=headers,
                params=params,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    logger.warning(f"Flipkart API {resp.status} for {category}: {text[:200]}")
                    return []
                data = await resp.json()

        products = data.get("products", data.get("docList", []))
        normalized = []
        for item in products:
            deal = self._normalize(item, category)
            if deal and deal["discount_percent"] >= self.min_discount:
                normalized.append(deal)

        return normalized

    def _normalize(self, item: dict, category: str) -> dict | None:
        try:
            # Flipkart API fields (vary slightly by endpoint version)
            product_id = item.get("productId") or item.get("fsn", "")
            title = item.get("productName") or item.get("title", "Product")
            mrp = float(item.get("mrp") or item.get("maximumRetailPrice", 0))
            selling = float(
                item.get("discountedPrice")
                or item.get("currentPrice")
                or item.get("flipkartSellingPrice", mrp)
            )
            discount_pct = round((1 - selling / mrp) * 100) if mrp > 0 else 0
            image = (
                item.get("imageUrl")
                or item.get("image")
                or item.get("imageUrls", {}).get("400x400", "")
            )
            product_url = item.get("productUrl") or item.get("url") or item.get("affiliateUrl", "")

            # Append affiliate tracking ID if missing
            if self.affiliate_id and "affid=" not in product_url:
                sep = "&" if "?" in product_url else "?"
                product_url = f"{product_url}{sep}affid={self.affiliate_id}"

            return {
                "id": f"fk_{product_id}",
                "platform": "Flipkart",
                "platform_emoji": "🛍️",
                "name": title,
                "category": category,
                "original_price": mrp,
                "sale_price": selling,
                "discount_percent": discount_pct,
                "savings_amount": mrp - selling,
                "currency": "₹",
                "image_url": image,
                "product_url": product_url,
                "score": discount_pct + ((mrp - selling) / 100),
            }
        except Exception as e:
            logger.debug(f"Normalize error: {e}")
            return None

    def _demo_deals(self) -> list[dict]:
        """Realistic demo Flipkart India deals for testing."""
        return [
            {
                "id": "fk_MOBGTAGPKHGPPHAM",
                "platform": "Flipkart",
                "platform_emoji": "🛍️",
                "name": "POCO X6 Pro 5G (Spectre Black, 12GB RAM, 256GB)",
                "category": "mobiles",
                "original_price": 26999,
                "sale_price": 19999,
                "discount_percent": 26,
                "savings_amount": 7000,
                "currency": "₹",
                "image_url": "https://images.unsplash.com/photo-1598327105666-5b89351aff97?w=600",
                "product_url": "https://www.flipkart.com/poco-x6-pro/p/itmXXX?affid=yourafid",
                "score": 26 + 70,
            },
            {
                "id": "fk_TVSG7NWGHFZYMQXH",
                "platform": "Flipkart",
                "platform_emoji": "🛍️",
                "name": 'Sony Bravia 55" 4K OLED Smart TV (XR-55A80L)',
                "category": "televisions",
                "original_price": 199990,
                "sale_price": 134990,
                "discount_percent": 32,
                "savings_amount": 65000,
                "currency": "₹",
                "image_url": "https://images.unsplash.com/photo-1593784991095-a205069470b6?w=600",
                "product_url": "https://www.flipkart.com/sony-bravia/p/itmXXX?affid=yourafid",
                "score": 32 + 650,
            },
            {
                "id": "fk_LAPFZPYHEBUJBQH4",
                "platform": "Flipkart",
                "platform_emoji": "🛍️",
                "name": "ASUS VivoBook 15 (Intel Core i5-13th Gen, 16GB, 512GB SSD)",
                "category": "laptops",
                "original_price": 74990,
                "sale_price": 44990,
                "discount_percent": 40,
                "savings_amount": 30000,
                "currency": "₹",
                "image_url": "https://images.unsplash.com/photo-1496181133206-80ce9b88a853?w=600",
                "product_url": "https://www.flipkart.com/asus-vivobook/p/itmXXX?affid=yourafid",
                "score": 40 + 300,
            },
        ]
