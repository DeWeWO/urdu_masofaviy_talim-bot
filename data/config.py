from environs import Env

env = Env()
env.read_env()

BOT_TOKEN = env.str("BOT_TOKEN")
ADMINS = env.list("ADMINS")
API_BASE_URL = env.str("API_BASE_URL")
BOT = env.str("BOT")