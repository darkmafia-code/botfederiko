import asyncio
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from loguru import logger
import traceback
import sys

from bot import config
from bot.database import init_db
from bot.handlers import commands, events, admin, game


async def main():
    # Setup logging
    logger.add("bot.log", rotation="1 MB", level="INFO")
    # also show debug logs in console to help testing
    logger.add(sys.stderr, level="DEBUG")
    logger.info("🤖 Bot starting up...")
    
    try:
        # Initialize database
        await init_db()
        logger.info("✅ Database initialized")
        
        # Create bot with proper properties
        default_properties = DefaultBotProperties(
            parse_mode=ParseMode.HTML
        )
        bot = Bot(
            token=config.BOT_TOKEN,
            default=default_properties
        )
        
        # Create dispatcher
        dp = Dispatcher()
        
        # Register routers (admin before generic event handlers)
        dp.include_router(commands.router)
        dp.include_router(admin.router)
        dp.include_router(events.router)
        dp.include_router(game.router)
        
        logger.info("✅ Routers registered")
        logger.info("🟢 Bot is polling Telegram...")
        
        # Start polling
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
        
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        logger.error(traceback.format_exc())
        raise
    finally:
        logger.info("Bot shut down")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("⚠️  Bot interrupted by user")
    except Exception as e:
        logger.critical(f"Critical error: {e}")
        logger.critical(traceback.format_exc())
