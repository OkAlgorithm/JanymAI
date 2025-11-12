import asyncio
import requests
from aiogram import F
from src.core.bot import bot, dp, redis_storage
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.types import Update, update  # ← For type hinting
from src.handlers.commands import router as commands_router
from src.handlers.messages import router as messages_router
from src.handlers.callbacks import router as callbacks_router
from src.services.redis_service import clear_user_state  # Example import
from src.utils.logger import logger
import src.config.settings as settings
from aiogram.types import BotCommand

@dp.error()
async def error_handler(event, exception):
    """
    Global error handler for the bot
    """
    logger.error(f"❌ Error occurred: {exception}", exc_info=True)

    # Specific handling for common Telegram errors
    if isinstance(exception, TelegramBadRequest):
        if "query is too old" in str(exception):
            logger.warning(f"⚠️ Ignored old callback query: {exception}")
            return True
        elif "message is not modified" in str(exception):
            logger.debug(f"⚠️ Ignored duplicate edit: {exception}")
            return True
    elif isinstance(exception, TelegramForbiddenError):
        logger.warning(f"⚠️ Bot blocked by user: {exception}")
        return True

    # Try to notify user if possible (avoid re-raising)
    try:
        if update.message:
            await update.message.answer(
                "❌ Произошла ошибка. Попробуйте начать заново с /start"
            )
        elif update.callback_query:
            # Answer callback if not already (prevents "old query" loops)
            if not update.callback_query.message:
                return True
            await update.callback_query.message.answer(
                "❌ Произошла ошибка. Попробуйте начать заново с /start"
            )
    except Exception as notify_error:
        logger.error(f"Failed to send error message: {notify_error}")

    return True  # Mark as handled (suppresses Aiogram's default)

# Include routers
dp.include_router(commands_router)
dp.include_router(messages_router)
dp.include_router(callbacks_router)

async def on_startup():
    """Actions on bot startup"""
    logger.info("🚀 Starting FlirtAI bot...")

    # NEW: Set bot commands menu
    commands = [
        BotCommand(command="start", description="🚀 Начать анализ профиля"),
        BotCommand(command="price", description="💰 Узнать цену"),
        BotCommand(command="end", description="🛑 Завершить анализ"),
        BotCommand(command="balance", description="💳 Проверить баланс"),  # ← NEW: For /balance
        BotCommand(command="topup", description="💰 Пополнить баланс")
    ]
    await bot.set_my_commands(commands)
    logger.info("✅ Bot commands menu set")

    # NEW: Init DB
    from src.database import init_db
    await asyncio.to_thread(init_db)  # Wrap sync init in thread

    # Test Redis connection
    try:
        from aiogram.fsm.storage.base import StorageKey
        test_key = StorageKey(bot_id=bot.id, chat_id=0, user_id=0)
        await redis_storage.set_data(key=test_key, data={"test": "connection"})
        await redis_storage.get_data(key=test_key)
        logger.info("✅ Redis connection successful")
    except Exception as e:
        logger.error(f"❌ Redis connection failed: {e}")
        raise

    # Test Ollama connection
    try:
        response = requests.get(f"{settings.OLLAMA_API_URL}/api/tags", timeout=5)
        if response.status_code == 200:
            logger.info("✅ Ollama connection successful")
        else:
            logger.warning(f"⚠️ Ollama returned status {response.status_code}")
    except Exception as e:
        logger.warning(f"⚠️ Ollama connection failed: {e}")

    logger.info(f"✅ Bot started successfully")
    logger.info(f"📊 Admin ID: {settings.ADMIN_ID}")
    logger.info(f"💰 Payment amount: {settings.PAYMENT_AMOUNT} ₸")
    logger.info(f"🔑 Kaspi API enabled: {settings.USE_KASPI_API}")

async def on_shutdown():
    """Actions on bot shutdown"""
    logger.info("🛑 Shutting down bot...")

    # Close Redis connection
    try:
        await redis_storage.close()
        logger.info("✅ Redis connection closed")
    except Exception as e:
        logger.error(f"❌ Error closing Redis: {e}")

    # Close bot session
    try:
        await bot.session.close()
        logger.info("✅ Bot session closed")
    except Exception as e:
        logger.error(f"❌ Error closing bot session: {e}")

async def main():
    """Start the bot"""
    try:
        await on_startup()
        await dp.start_polling(
            bot,
            allowed_updates=dp.resolve_used_update_types(),
            drop_pending_updates=True  # Skip pending updates on restart
        )
    except KeyboardInterrupt:
        logger.info("🛑 Bot stopped by user")
    except Exception as e:
        logger.error(f"❌ Bot startup error: {e}", exc_info=True)
    finally:
        await on_shutdown()

if __name__ == "__main__":
    asyncio.run(main())