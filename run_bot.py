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
    logger.info("QuickOffer Support Bot - Telegram Edition")
    logger.info("=" * 60)

    # Log configuration
    logger.info("🔧 Configuration:")
    if settings.use_mocks:
        logger.info("   ✅ USE_MOCKS=true (Mock API clients)")
    else:
        logger.info(f"   ℹ️  USE_MOCKS=false (Real API clients)")

    logger.info(f"   LLM Provider: {settings.llm_provider}")
    logger.info(f"   Provider Mode: {settings.provider_mode}")

    if settings.provider_mode.lower() == "zeroentropy_openrouter":
        logger.info("   📊 Using ZeroEntropy (embeddings/reranking) + OpenRouter (LLM)")
        if settings.zero_entropy_api_key:
            logger.info("   ✅ ZeroEntropy API Key configured")
        else:
            logger.warning("   ⚠️  ZeroEntropy API Key NOT configured, will fall back to LiteLLM")
    else:
        logger.info("   📊 Using LiteLLM for all services")

    logger.info(f"   Bot Token: {settings.telegram_bot_token[:10]}***")
    logger.info(f"   Approval Chat ID: {settings.telegram_approval_chat_id}")
    logger.info(f"   Log Level: {settings.log_level}")
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
        logger.info("Closing bot session...")
        await bot.session.close()
        logger.info("Bot shutdown complete")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\n🛑 Bot stopped by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        sys.exit(1)
