import re
from aiogram import types, F, Router
from aiogram.types import ReplyKeyboardRemove, CallbackQuery
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from keyboards.inline.buttons import register_confirm
from keyboards.inline.checkPhone import PhoneCheckCallback, phone_check_kb
from keyboards.reply.buttons import register_markup, share_contact
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
        await message.answer("☎ Telegram telefon raqamingizni ulashing", reply_markup=share_contact())
        await state.set_state(RegisterState.tg_tel)

@router.message(StateFilter(RegisterState.tg_tel))
async def get_tg_tel(message: types.Message, state: FSMContext):
    if message.contact and message.contact.phone_number:
        tg_tel = message.text.strip()
        await state.update_data({"tg_tel": tg_tel})
        await message.answer("Bu siz ishlatadigan asosiy telefon raqammi??", reply_markup=phone_check_kb())
    else:
        await message.answer("❌ Raqamingizni kontakt sifatida ulashing.", reply_markup=share_contact())

@router.message(PhoneCheckCallback.filter(), RegisterState.tg_tel)
async def handle_check_phone(call: CallbackQuery, callback_data: PhoneCheckCallback, state: FSMContext):
    await call.answer()
    if callback_data.is_actual:
        await call.message.answer("👨‍👩‍👦 Ota-onangizni telefon raqamini kiriting:", reply_markup=ReplyKeyboardRemove())
        await state.set_state(RegisterState.parent_tel)
    else:
        await call.message.answer("Iltimos o'zingiz doimiy foydalanadigan telefon raqamingizni kiriting:", reply_markup=ReplyKeyboardRemove())
        await state.set_state(RegisterState.tel)

@round.message(StateFilter(RegisterState.tel))
async def get_tel(message: types.Message, state: FSMContext):
    tel = message.text.strip()
    if not re.fullmatch(r'^(\+998)?\d{9}$', tel):
        await message.answer("❌ Raqamni to'g'ri formatda kiriting.\nMasalan: +998901234567")
        return
    await state.update_data({"tel": tel})
    await message.answer("👨‍👩‍👦 Ota-onangizni telefon raqamini kiriting:")
    await state.set_state(RegisterState.parent_tel)

@router.message(StateFilter(RegisterState.parent_tel))
async def get_parent_tel(message: types.Message, state: FSMContext):
    parent_tel = message.text.strip()
    if not re.fullmatch(r'^(\+998)?\d{9}$', parent_tel):
        await message.answer("❌ Raqamni to'g'ri formatda kiriting.\nMasalan: +998901234567")
        return
    await state.update_data({"parent_tel": parent_tel})
    data = await state.get_data()
    phone_numbers = []
    for key in ['phone1', 'phone2', 'phone3']:
        if key in data:
            phone_numbers.append(data[key])
    await state.update_data({"phones": phone_numbers})
    await message.answer("📍 Manzilingizni to'liq kiriting.\n<i>Namuma: Xorazm viloyati Urganch shahar Mahalla MFY Ko'cha nomi uy</i>")