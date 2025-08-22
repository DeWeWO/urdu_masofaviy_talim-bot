from aiogram import Router, types
from aiogram.filters import CommandStart
from aiogram.enums.parse_mode import ParseMode
from aiogram.client.session.middlewares.request_logging import logger
from loader import db, bot
from data.config import ADMINS
from utils.extra_datas import make_title
from keyboards.reply.buttons import add_group

router = Router()


@router.message(CommandStart())
async def do_start(message: types.Message):
    full_name = message.from_user.full_name
    await message.answer(f"Assalomu alaykum {make_title(full_name)}!", reply_markup=add_group())
