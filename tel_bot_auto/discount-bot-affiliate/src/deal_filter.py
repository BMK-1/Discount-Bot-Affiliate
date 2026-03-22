"""
Deal Filter — Applies configurable rules before posting.
"""

import logging
import os

logger = logging.getLogger(__name__)


class DealFilter:
    def __init__(self):
        self.min_discount = int(os.getenv("MIN_DISCOUNT_PERCENT", 20))
        self.min_price = float(os.getenv("MIN_PRICE", 0))
        self.max_price = float(os.getenv("MAX_PRICE", 0))
        self.min_savings = float(os.getenv("MIN_SAVINGS_AMOUNT", 100))
        self.block_keywords = [
            kw.strip().lower()
            for kw in os.getenv("BLOCK_KEYWORDS", "").split(",")
            if kw.strip()
        ]

    def filter(self, products: list[dict]) -> list[dict]:
        return [p for p in products if self._passes(p)]

    def _passes(self, p: dict) -> bool:
        if p.get("discount_percent", 0) < self.min_discount:
            return False
        if p.get("sale_price", 0) <= 0:
            return False
        if p.get("original_price", 0) <= p.get("sale_price", 0):
            return False
        if p.get("savings_amount", 0) < self.min_savings:
            return False
        if self.min_price > 0 and p.get("sale_price", 0) < self.min_price:
            return False
        if self.max_price > 0 and p.get("sale_price", 0) > self.max_price:
            return False
        name_lower = p.get("name", "").lower()
        for kw in self.block_keywords:
            if kw in name_lower:
                return False
        return True
