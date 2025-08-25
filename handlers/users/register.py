from aiogram import types, F, Router
from aiogram.types import ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext
from keyboards.inline.buttons import register_confirm
from keyboards.reply.buttons import register_markup
from states.RegisterState import RegisterState
from loader import db

router = Router()
@router.message(F.text == "👤 Ro'yxatdan o'tish")
async def start_register(message: types.Message, state: FSMContext):
    await message.answer("Sallom)")