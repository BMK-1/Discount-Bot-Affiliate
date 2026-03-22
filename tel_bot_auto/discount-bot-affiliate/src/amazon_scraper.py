"""
Amazon Scraper — Scrapes Amazon India deal pages WITHOUT needing PAAPI.
Works immediately. Just set your AMAZON_PARTNER_TAG in .env.

Scrapes these pages (configurable):
  - Amazon Today's Deals: https://www.amazon.in/deals
  - Amazon Sale pages by category

Your affiliate tag is automatically appended to every product link.
"""

import asyncio
import logging
import os
import re
import hashlib
import aiohttp
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Pages to scrape for deals
DEAL_PAGES = [
    "https://www.amazon.in/deals?ref=nav_cs_gb",
    "https://www.amazon.in/s?i=electronics&rh=n%3A976419031&s=featured-rank&deals-widget=%7B%22version%22%3A1%2C%22saleEvent%22%3Atrue%7D",
    "https://www.amazon.in/s?i=computers&rh=n%3A1375424031&s=featured-rank",
    "https://www.amazon.in/s?i=fashion&rh=n%3A1571271031&s=featured-rank",
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-IN,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
}


class AmazonScraper:
    def __init__(self):
        self.partner_tag = os.getenv("AMAZON_PARTNER_TAG", "")
        self.min_discount = int(os.getenv("MIN_DISCOUNT_PERCENT", 20))
        self.max_products = int(os.getenv("AMAZON_MAX_PRODUCTS", 30))
        self.enabled = os.getenv("ENABLE_AMAZON", "true").lower() == "true"

        # Extra pages from .env (comma-separated URLs)
        extra = os.getenv("AMAZON_EXTRA_PAGES", "")
        self.pages = DEAL_PAGES + [p.strip() for p in extra.split(",") if p.strip()]

    async def fetch_deals(self) -> list[dict]:
        if not self.enabled:
            return []

        if not self.partner_tag:
            logger.warning("AMAZON_PARTNER_TAG not set — affiliate links won't earn commission!")

        all_deals = []
        async with aiohttp.ClientSession(headers=HEADERS) as session:
            for page_url in self.pages:
                try:
                    deals = await self._scrape_page(session, page_url)
                    all_deals.extend(deals)
                    logger.info(f"Amazon scrape '{page_url[:60]}...' → {len(deals)} deals")
                    await asyncio.sleep(2)  # polite delay between pages
                except Exception as e:
                    logger.error(f"Scrape failed for {page_url[:60]}: {e}")

        # Deduplicate by ASIN
        seen = set()
        unique = []
        for d in all_deals:
            if d["id"] not in seen:
                seen.add(d["id"])
                unique.append(d)

        logger.info(f"Amazon: {len(unique)} unique deals scraped")
        return unique[: self.max_products]

    async def _scrape_page(self, session: aiohttp.ClientSession, url: str) -> list[dict]:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=20)) as resp:
            if resp.status != 200:
                logger.warning(f"HTTP {resp.status} from Amazon")
                return []
            html = await resp.text()

        soup = BeautifulSoup(html, "lxml")
        deals = []

        # Amazon uses multiple layouts — try all known selectors
        product_containers = (
            soup.select("div[data-asin]")           # Standard search/deals grid
            or soup.select(".a-section.a-spacing-base")
            or soup.select("[data-component-type='s-search-result']")
        )

        for container in product_containers:
            deal = self._parse_container(container)
            if deal and deal["discount_percent"] >= self.min_discount:
                deals.append(deal)

        return deals

    def _parse_container(self, el) -> dict | None:
        try:
            # Get ASIN
            asin = el.get("data-asin", "").strip()
            if not asin or len(asin) != 10:
                return None

            # Product name
            name_el = (
                el.select_one("h2 a span")
                or el.select_one(".a-size-medium.a-color-base.a-text-normal")
                or el.select_one(".a-size-base-plus")
                or el.select_one("h2 span")
            )
            if not name_el:
                return None
            name = name_el.get_text(strip=True)
            if not name or len(name) < 5:
                return None

            # Sale price
            sale_el = (
                el.select_one(".a-price .a-offscreen")
                or el.select_one("span.a-price span.a-offscreen")
            )
            sale_price = self._parse_price(sale_el.get_text() if sale_el else "")

            # Original / strikethrough price
            orig_el = (
                el.select_one(".a-price.a-text-price .a-offscreen")
                or el.select_one("span[data-a-strike='true'] .a-offscreen")
                or el.select_one(".a-text-price .a-offscreen")
            )
            orig_price = self._parse_price(orig_el.get_text() if orig_el else "")

            # Discount badge (Amazon sometimes shows "X% off" directly)
            badge_el = (
                el.select_one(".a-badge-text")
                or el.select_one("span.s-coupon-highlight-color")
                or el.select_one(".a-color-price")
            )
            badge_text = badge_el.get_text(strip=True) if badge_el else ""
            badge_pct = self._extract_pct(badge_text)

            # Calculate discount
            if orig_price > 0 and sale_price > 0 and sale_price < orig_price:
                discount_pct = round((1 - sale_price / orig_price) * 100)
            elif badge_pct > 0:
                discount_pct = badge_pct
                if sale_price > 0 and orig_price == 0:
                    orig_price = round(sale_price / (1 - badge_pct / 100))
            else:
                return None  # can't determine discount

            if sale_price <= 0:
                return None

            savings = orig_price - sale_price

            # Product image
            img_el = el.select_one("img.s-image") or el.select_one("img[data-image-latency]")
            image_url = img_el.get("src", "") if img_el else ""

            # Build affiliate URL
            base_url = f"https://www.amazon.in/dp/{asin}"
            if self.partner_tag:
                product_url = f"{base_url}?tag={self.partner_tag}"
            else:
                product_url = base_url

            return {
                "id": f"amz_{asin}",
                "platform": "Amazon",
                "platform_emoji": "🛒",
                "name": name,
                "category": "Amazon Deals",
                "original_price": orig_price,
                "sale_price": sale_price,
                "discount_percent": discount_pct,
                "savings_amount": savings,
                "currency": "₹",
                "image_url": image_url,
                "product_url": product_url,
                "score": discount_pct + (savings / 100),
            }

        except Exception as e:
            logger.debug(f"Parse error: {e}")
            return None

    def _parse_price(self, text: str) -> float:
        if not text:
            return 0.0
        cleaned = re.sub(r"[^\d.]", "", text.replace(",", ""))
        try:
            return float(cleaned)
        except ValueError:
            return 0.0

    def _extract_pct(self, text: str) -> int:
        match = re.search(r"(\d+)\s*%", text)
        return int(match.group(1)) if match else 0
