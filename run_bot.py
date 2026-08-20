#!/usr/bin/env python3set_bot_commands
"""Quick start script for running the QuickOffer Support Bot in mock mode."""

import asyncio
import logging
import sys
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand
from aiogram.client.session.aiohttp import AiohttpSession

from src.core.config import settings
from src.presentation.telegram import router, referral_router, review_router

# Set up logging
logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def set_bot_commands(bot: Bot) -> None:
    """Set up bot commands.

    Args:
        bot: Bot instance.
    """
    commands = [
        BotCommand(command="refund", description="Request refund"),
        BotCommand(command="archive_job", description="Request job archival"),
        BotCommand(command="start", description="Start the bot"),
        BotCommand(command="help", description="Show help"),
    ]
    await bot.set_my_commands(commands)


async def main() -> None:
    """Main entry point for the bot."""
    logger.info("=" * 60)
    logger.info("QuickOffer Support Bot - Demo Mode")
    logger.info("=" * 60)

    # Log configuration
    if settings.use_mocks:
        logger.info("✅ Running in MOCK MODE (USE_MOCKS=true)")
        logger.info("   - FuckHR API: Mock client")
        logger.info("   - Jobs API: Mock client")
        logger.info("   - Database: SQLite (local)")
    else:
        logger.info("⚠️  Running in PRODUCTION MODE")
        logger.info(f"   - FuckHR API: {settings.fuckhr_api_base_url}")
        logger.info(f"   - Jobs API: {settings.jobs_api_base_url}")
        logger.info(f"   - Database: {settings.database_url}")

    logger.info(f"Bot Token: {settings.telegram_bot_token[:10]}***")
    logger.info(f"Approval Chat ID: {settings.telegram_approval_chat_id}")
    logger.info("=" * 60)

    # Initialize database
    logger.info("Initializing database...")
    try:
        logger.info("✅ Database initialized successfully")
    except Exception as e:
        logger.error(f"❌ Failed to initialize database: {e}")
        sys.exit(1)

    # Initialize bot and dispatcher
    try:
        session = AiohttpSession(proxy="http://kzalm-swp.nestlesoft.net:2270")
        bot = Bot(token=settings.telegram_bot_token, session=session)
        dp = Dispatcher()

        # Include routers
        dp.include_router(router)
        dp.include_router(referral_router)
        dp.include_router(review_router)

        # Set bot commands
        await set_bot_commands(bot)

        # Log startup info
        logger.info("=" * 60)
        logger.info("🚀 Bot is ready!")
        logger.info("Starting polling...")
        logger.info("=" * 60)

        # Start polling
        try:
            await dp.start_polling(bot)
        except Exception as e:
            logger.error(f"Error during polling: {e}")
            raise

    except Exception as e:
        logger.error(f"❌ Failed to start bot: {e}")
        sys.exit(1)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)
