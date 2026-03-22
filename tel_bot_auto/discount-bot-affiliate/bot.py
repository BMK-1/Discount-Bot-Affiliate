"""
Amazon & Flipkart Affiliate Discount Bot
Automatically posts the best deals to your Telegram channel every hour.
"""

import asyncio
import logging
import os
from dotenv import load_dotenv
from src.scheduler import BotScheduler

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler("logs/bot.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


async def main():
    logger.info("🚀 Affiliate Discount Bot starting...")

    required = ["TELEGRAM_BOT_TOKEN", "TELEGRAM_CHANNEL_ID"]
    missing = [v for v in required if not os.getenv(v)]
    if missing:
        logger.error(f"❌ Missing required env vars: {missing}")
        logger.error("Copy .env.example → .env and fill in your values.")
        return

    scheduler = BotScheduler()
    await scheduler.start()


if __name__ == "__main__":
    asyncio.run(main())
