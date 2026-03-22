"""
Telegram Poster — Sends beautifully formatted affiliate deal posts.
Includes: product image, original vs sale price, discount %, savings, and buy link.
"""

import logging
import os
import aiohttp

logger = logging.getLogger(__name__)

BOT_API = "https://api.telegram.org/bot{token}/{method}"


class TelegramPoster:
    def __init__(self):
        self.token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.channel_id = os.getenv("TELEGRAM_CHANNEL_ID", "")
        self.channel_name = os.getenv("TELEGRAM_CHANNEL_NAME", "Deals Channel")
        self.show_savings = os.getenv("SHOW_SAVINGS_AMOUNT", "true").lower() == "true"
        self.hashtags = os.getenv("POST_HASHTAGS", "#Deals #Sale #Discount")

    def _api(self, method: str) -> str:
        return BOT_API.format(token=self.token, method=method)

    def _fmt_price(self, amount: float, currency: str) -> str:
        if currency == "₹":
            return f"₹{amount:,.0f}"
        elif currency == "$":
            return f"${amount:,.2f}"
        elif currency == "£":
            return f"£{amount:,.2f}"
        elif currency == "€":
            return f"€{amount:,.2f}"
        return f"{currency}{amount:,.2f}"

    def _discount_badge(self, pct: int) -> str:
        if pct >= 70:
            return "🔥🔥🔥 MEGA DEAL"
        elif pct >= 50:
            return "🔥🔥 HOT DEAL"
        elif pct >= 30:
            return "🔥 GREAT DEAL"
        else:
            return "💸 ON SALE"

    def _build_caption(self, deal: dict) -> str:
        name = deal.get("name", "Product")
        platform = deal.get("platform", "Store")
        platform_emoji = deal.get("platform_emoji", "🛒")
        orig = deal.get("original_price", 0)
        sale = deal.get("sale_price", 0)
        pct = deal.get("discount_percent", 0)
        saved = deal.get("savings_amount", orig - sale)
        currency = deal.get("currency", "₹")
        url = deal.get("product_url", "")

        orig_str = self._fmt_price(orig, currency)
        sale_str = self._fmt_price(sale, currency)
        saved_str = self._fmt_price(saved, currency)
        badge = self._discount_badge(pct)

        lines = [
            f"*{badge}* {platform_emoji} *{platform}*",
            "",
            f"🏷️ *{self._esc(name)}*",
            "",
            f"💰 *Sale Price:* *{sale_str}*",
            f"🏪 MRP: ~{orig_str}~",
            f"📉 *{pct}% OFF*",
        ]

        if self.show_savings:
            lines.append(f"💵 You Save: *{saved_str}*")

        lines += [
            "",
            f"⚡ [👉 BUY NOW on {platform}]({url})",
            "",
            "━━━━━━━━━━━━━━━━━",
            f"🔔 {self.hashtags}",
            f"📢 Join \\→ {self._esc(self.channel_name)} for hourly deals\\!",
        ]

        return "\n".join(lines)

    def _esc(self, text: str) -> str:
        """Escape for MarkdownV2."""
        special = r"_*[]()~`>#+-=|{}.!"
        return "".join(f"\\{c}" if c in special else c for c in str(text))

    async def post_deal(self, deal: dict) -> bool:
        caption = self._build_caption(deal)
        image_url = deal.get("image_url", "")

        async with aiohttp.ClientSession() as session:
            if image_url:
                ok = await self._send_photo(session, image_url, caption)
                if not ok:
                    ok = await self._send_message(session, caption)
            else:
                ok = await self._send_message(session, caption)

        if ok:
            logger.info(
                f"✅ [{deal.get('platform')}] {deal['name'][:60]} — {deal['discount_percent']}% off"
            )
        else:
            logger.error(f"❌ Failed: {deal.get('name', '')[:60]}")
        return ok

    async def _send_photo(self, session, photo_url: str, caption: str) -> bool:
        payload = {
            "chat_id": self.channel_id,
            "photo": photo_url,
            "caption": caption,
            "parse_mode": "MarkdownV2",
        }
        try:
            async with session.post(
                self._api("sendPhoto"), json=payload, timeout=aiohttp.ClientTimeout(total=15)
            ) as r:
                data = await r.json()
                if not data.get("ok"):
                    logger.debug(f"sendPhoto error: {data.get('description')}")
                return data.get("ok", False)
        except Exception as e:
            logger.warning(f"sendPhoto exception: {e}")
            return False

    async def _send_message(self, session, text: str) -> bool:
        payload = {
            "chat_id": self.channel_id,
            "text": text,
            "parse_mode": "MarkdownV2",
            "disable_web_page_preview": False,
        }
        try:
            async with session.post(
                self._api("sendMessage"), json=payload, timeout=aiohttp.ClientTimeout(total=15)
            ) as r:
                data = await r.json()
                if not data.get("ok"):
                    logger.debug(f"sendMessage error: {data.get('description')}")
                return data.get("ok", False)
        except Exception as e:
            logger.warning(f"sendMessage exception: {e}")
            return False
