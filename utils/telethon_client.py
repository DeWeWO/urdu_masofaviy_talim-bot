from telethon import TelegramClient
from data import config

telethon_client = TelegramClient(
    config.SESSION_NAME,
    config.API_ID,
    config.API_HASH
)
