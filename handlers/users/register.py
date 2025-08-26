from aiogram import types, F, Router
from aiogram.types import ReplyKeyboardRemove
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from keyboards.inline.buttons import register_confirm
from keyboards.reply.buttons import register_markup, phone
from states.RegisterState import RegisterState
from loader import db

router = Router()
@router.message(F.text == "👤 Ro'yxatdan o'tish")
async def start_register(message: types.Message, state: FSMContext):
    await message.answer("<b>Familiya Ism Sharifingizni to'liq kiriting:</b>\n\n<i>Na'muna: Abdullayev Abdulla Abdulla o'g'li</i>",
                        reply_markup=ReplyKeyboardRemove()
    )
    await state.set_state(RegisterState.fio)

@router.message(StateFilter(RegisterState.fio))
async def get_fio(message: types.Message, state: FSMContext):
    fio = message.text.strip()
    words = fio.split()
    if len(words) <= 2:
        await message.answer("❌ F.I.Sh ni to'liq kirtmadingiz.")
        return
    await state.update_data({"fio": fio})
    await message.answer("JSHSHIR ingizni kiriting.\n14 raqamdan iborat bo'lishi shart.")
    await state.set_state(RegisterState.pnfl)

@router.message(StateFilter(RegisterState.pnfl))
async def get_pnfl(message: types.Message, state: FSMContext):
    pnfl = message.text.strip()
    if len(pnfl) != 14:
        await message.answer("❌ JSHSHIR noto'g'ri. 14 raqamdan iborat bo'lishi shart.")
        return
    if len(pnfl) == 14:
        await state.update_data({"pnfl": pnfl})
        await message.answer("☎ Telegram telefon raqamingizni ulashing", reply_markup=phone.as_markup(resize_keyboard=True))
        await state.set_state(RegisterState.tg_tel)