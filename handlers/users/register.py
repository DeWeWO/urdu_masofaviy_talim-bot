import re
from aiogram import types, F, Router
from aiogram.types import ReplyKeyboardRemove, CallbackQuery
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from keyboards.inline.buttons import register_confirm
from keyboards.inline.checkPhone import PhoneCheckCallback, phone_check_kb_simple
from keyboards.reply.buttons import register_markup, share_contact
from states.RegisterState import RegisterState
from loader import db

router = Router()

@router.message(F.text == "👤 Ro'yxatdan o'tish")
async def start_register(message: types.Message, state: FSMContext):
    await message.answer(
        "<b>Familiya Ism Sharifingizni to'liq kiriting:</b>\n\n"
        "<i>Na'muna: Abdullayev Abdulla Abdulla o'g'li</i>",
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
    if not pnfl.isdigit() or len(pnfl) != 14:
        await message.answer("❌ JSHSHIR noto'g'ri. 14 raqamdan iborat bo'lishi shart.")
        return
    
    await state.update_data({"pnfl": pnfl})
    await message.answer("☎ Telegram telefon raqamingizni ulashing", reply_markup=share_contact())
    await state.set_state(RegisterState.tg_tel)

@router.message(StateFilter(RegisterState.tg_tel))
async def get_tg_tel(message: types.Message, state: FSMContext):
    if message.contact and message.contact.phone_number:
        tg_tel = message.contact.phone_number
        await state.update_data({"tg_tel": tg_tel})
        await message.answer("Bu siz ishlatadigan asosiy telefon raqammi?", reply_markup=phone_check_kb_simple())
    else:
        await message.answer("❌ Raqamingizni kontakt sifatida ulashing.", reply_markup=share_contact())

@router.callback_query(F.data.in_(['phone_check_yes', 'phone_check_no']))
async def handle_check_phone_simple(call: CallbackQuery, state: FSMContext):
    await call.answer()
    
    # State'ni tekshirish
    current_state = await state.get_state()
    if current_state != RegisterState.tg_tel:
        return
    
    # Xabarni o'chirish (ixtiyoriy)
    try:
        await call.message.delete()
    except:
        pass
    
    if call.data == 'phone_check_yes':
        await call.message.answer("👨‍👩‍👦 Ota-onangizni telefon raqamini kiriting:", reply_markup=ReplyKeyboardRemove())
        await state.set_state(RegisterState.parent_tel)
    else:
        await call.message.answer("📱 Iltimos o'zingiz doimiy foydalanadigan telefon raqamingizni kiriting:", reply_markup=ReplyKeyboardRemove())
        await state.set_state(RegisterState.tel)

@router.message(StateFilter(RegisterState.tel))
async def get_tel(message: types.Message, state: FSMContext):
    tel = message.text.strip()
    # +998 bilan boshlangan yoki 9 ta raqamdan iborat bo'lgan raqamlarni qabul qilish
    if not re.fullmatch(r'^(\+998[0-9]{9}|[0-9]{9})$', tel):
        await message.answer("❌ Raqamni to'g'ri formatda kiriting.\nMasalan: +998901234567 yoki 901234567")
        return
    
    # Agar +998 bo'lmasa, qo'shib qo'yamiz
    if not tel.startswith('+998'):
        tel = '+998' + tel
    
    await state.update_data({"tel": tel})
    await message.answer("👨‍👩‍👦 Ota-onangizni telefon raqamini kiriting:")
    await state.set_state(RegisterState.parent_tel)

@router.message(StateFilter(RegisterState.parent_tel))
async def get_parent_tel(message: types.Message, state: FSMContext):
    parent_tel = message.text.strip()
    # Telefon raqam formatini tekshirish
    if not re.fullmatch(r'^(\+998[0-9]{9}|[0-9]{9})$', parent_tel):
        await message.answer("❌ Raqamni to'g'ri formatda kiriting.\nMasalan: +998901234567 yoki 901234567")
        return
    
    # Agar +998 bo'lmasa, qo'shib qo'yamiz
    if not parent_tel.startswith('+998'):
        parent_tel = '+998' + parent_tel
        
    await state.update_data({"parent_tel": parent_tel})
    await message.answer(
        "📍 Manzilingizni to'liq kiriting.\n"
        "<i>Namuna: Xorazm viloyati Urganch shahar Mahalla MFY Ko'cha nomi uy raqami</i>"
    )
    await state.set_state(RegisterState.address)

@router.message(StateFilter(RegisterState.address))
async def get_address(message: types.Message, state: FSMContext):
    address = message.text.strip()
    if len(address) < 20:
        await message.answer("❌ Iltimos manzilingizni namunadagi kabi to'liq kiriting.")
        return
        
    await state.update_data({"address": address})
    data = await state.get_data()
    
    # Telefon raqamlarini to'plash
    phone_numbers = []
    if 'tg_tel' in data:
        phone_numbers.append(f"📱 Telegram: {data['tg_tel']}")
    if 'tel' in data and data['tel'] != data.get('tg_tel'):
        phone_numbers.append(f"📞 Asosiy: {data['tel']}")
    if 'parent_tel' in data:
        phone_numbers.append(f"👨‍👩‍👦 Ota-ona: {data['parent_tel']}")
    
    phone_list = "\n".join(phone_numbers)
    
    text = (
        f"Ushbu ma'lumotlaringiz to'g'riligini tasdiqlang:\n\n"
        f"<b>👤 F.I.Sh:</b> {data['fio']}\n"
        f"<b>🆔 JSHSHIR:</b> {data['pnfl']}\n"
        f"<b>📞 Telefon raqamlar:</b>\n{phone_list}\n"
        f"<b>📍 Manzil:</b> {data['address']}"
    )
    
    await message.answer(text, reply_markup=register_confirm)
    await state.set_state(RegisterState.confirm)