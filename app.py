import sys
import asyncio
import logging
from aiogram import Bot, Dispatcher
from utils.telethon_client import telethon_client


# --- Logger Setup ---
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Log format
formatter = logging.Formatter(
    fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

# Faylga yozuvchi handler
file_handler = logging.FileHandler("bot.log", encoding="utf-8")
file_handler.setFormatter(formatter)

# Konsolga chiqaruvchi handler
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(formatter)

# Handlerlarni biriktiramiz
logger.addHandler(file_handler)
logger.addHandler(console_handler)

# Aiogram loglarini ham shu handlerlarga bog‘lash
logging.getLogger("aiogram").handlers = [file_handler, console_handler]
logging.getLogger("aiogram").setLevel(logging.INFO)


def setup_handlers(dispatcher: Dispatcher) -> None:
    """HANDLERS"""
    from handlers import setup_routers
    dispatcher.include_router(setup_routers())


def setup_middlewares(dispatcher: Dispatcher, bot: Bot) -> None:
    """MIDDLEWARE"""
    from middlewares.throttling import ThrottlingMiddleware
    dispatcher.message.middleware(ThrottlingMiddleware(slow_mode_delay=0.5))


def setup_filters(dispatcher: Dispatcher) -> None:
    """FILTERS"""
    from filters import ChatPrivateFilter
    dispatcher.message.filter(ChatPrivateFilter(chat_type=["private"]))


async def setup_aiogram(dispatcher: Dispatcher, bot: Bot) -> None:
    logger.info("Configuring aiogram")
    setup_handlers(dispatcher=dispatcher)
    setup_middlewares(dispatcher=dispatcher, bot=bot)
    setup_filters(dispatcher=dispatcher)
    logger.info("Configured aiogram")


async def database_connected():
    try:
        from utils.db.postgres import api_client
        await api_client.health_check()
        logger.info("Database connected")
    except Exception as e:
        logger.error(f"Database connection failed: {e}")


async def aiogram_on_startup_polling(dispatcher: Dispatcher, bot: Bot) -> None:
    from utils.set_bot_commands import set_default_commands
    from utils.notify_admins import on_startup_notify

    await database_connected()

    logger.info("Starting polling")
    await bot.delete_webhook(drop_pending_updates=True)
    await setup_aiogram(bot=bot, dispatcher=dispatcher)
    await on_startup_notify(bot=bot)
    await set_default_commands(bot=bot)

    logger.info("Telethon clientga ulanmoqda...")
    await telethon_client.start()
    logger.info("Telethon client ishga tushdi!")


async def aiogram_on_shutdown_polling(dispatcher: Dispatcher, bot: Bot):
    logger.info("Stopping polling")
    await bot.session.close()
    await dispatcher.storage.close()


def main():
    """CONFIG"""
    from data.config import BOT_TOKEN
    from aiogram.enums import ParseMode
    from aiogram.fsm.storage.memory import MemoryStorage
    from aiogram.client.default import DefaultBotProperties

    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    storage = MemoryStorage()
    dispatcher = Dispatcher(storage=storage)

    dispatcher.startup.register(aiogram_on_startup_polling)
    dispatcher.shutdown.register(aiogram_on_shutdown_polling)

    asyncio.run(dispatcher.start_polling(
        bot,
        close_bot_session=True,
        allowed_updates=['message', 'chat_member', 'my_chat_member', 'callback_query']
    ))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Bot stopped by user!")
