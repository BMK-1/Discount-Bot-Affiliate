"""
Scheduler — Runs a full deal-fetch-and-post cycle every hour automatically.
"""

import asyncio
import logging
import os
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from src.amazon_scraper import AmazonScraper as AmazonFetcher
from src.flipkart_fetcher import FlipkartFetcher
from src.deal_filter import DealFilter
from src.telegram_poster import TelegramPoster
from src.posted_tracker import PostedTracker

logger = logging.getLogger(__name__)


class BotScheduler:
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.amazon = AmazonFetcher()
        self.flipkart = FlipkartFetcher()
        self.deal_filter = DealFilter()
        self.poster = TelegramPoster()
        self.tracker = PostedTracker()

        self.interval_hours = int(os.getenv("POST_INTERVAL_HOURS", 1))
        self.max_posts_per_cycle = int(os.getenv("MAX_POSTS_PER_CYCLE", 5))

        # Which platforms to enable
        self.use_amazon = os.getenv("ENABLE_AMAZON", "true").lower() == "true"
        self.use_flipkart = os.getenv("ENABLE_FLIPKART", "true").lower() == "true"

    async def run_cycle(self):
        """Full cycle: fetch → filter → rank → post."""
        logger.info("⏰ Starting hourly deal cycle...")
        all_products = []

        # Fetch from enabled platforms concurrently
        tasks = []
        if self.use_amazon:
            tasks.append(self.amazon.fetch_deals())
        if self.use_flipkart:
            tasks.append(self.flipkart.fetch_deals())

        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for result in results:
                if isinstance(result, Exception):
                    logger.error(f"Fetch error: {result}")
                else:
                    all_products.extend(result)

        logger.info(f"📦 Total fetched: {len(all_products)} products")

        # Filter qualifying deals
        deals = self.deal_filter.filter(all_products)
        logger.info(f"🏷️  Qualifying deals: {len(deals)}")

        # Remove already posted
        new_deals = [d for d in deals if not self.tracker.already_posted(d["id"])]
        logger.info(f"🆕 New (not posted): {len(new_deals)}")

        # Sort by score: discount% weighted + high savings amount
        new_deals.sort(key=lambda d: d.get("score", 0), reverse=True)

        # Post top deals
        posted = 0
        for deal in new_deals[: self.max_posts_per_cycle]:
            success = await self.poster.post_deal(deal)
            if success:
                self.tracker.mark_posted(deal["id"])
                posted += 1
                await asyncio.sleep(3)  # Telegram rate limit safe gap

        logger.info(f"✅ Posted {posted} deals this cycle.")

    async def start(self):
        # Run immediately on startup
        await self.run_cycle()

        self.scheduler.add_job(
            self.run_cycle,
            trigger=IntervalTrigger(hours=self.interval_hours),
            id="deal_cycle",
            replace_existing=True,
        )
        self.scheduler.start()
        logger.info(f"🕐 Scheduler active — running every {self.interval_hours} hour(s)")

        try:
            while True:
                await asyncio.sleep(60)
        except (KeyboardInterrupt, SystemExit):
            logger.info("🛑 Shutting down bot...")
            self.scheduler.shutdown()
