from aiogram import types, F, Router
from aiogram.filters import StateFilter
from utils.db.postgres import api_client
from keyboards.reply.buttons import update_info_markup, register_markup

router = Router()

@router.message(F.text == "👤 Mening ma'lumotlarim")
async def show_user_info(message: types.Message):
    """Foydalanuvchi ma'lumotlarini ko'rsatish"""
    telegram_id = message.from_user.id
    try:
        user_info = await api_client.get_user_full_info(telegram_id)
        if user_info and user_info.get('success'):
            data = user_info.get('data', {})
            print(f"Foydalanuvchi: {data.get('fio')}")
            print(f"Guruh: {data.get('register_group_name')}")
        
        data = user_info.get('data', {})
        
        # Ma'lumotlarni formatlash
        fio = data.get('fio', 'Kiritilmagan')
        pnfl = data.get('pnfl', 'Kiritilmagan')
        tg_tel = data.get('tg_tel', 'Kiritilmagan')
        tel = data.get('tel', 'Kiritilmagan') if data.get('tel') != data.get('tg_tel') else None
        parent_tel = data.get('parent_tel', 'Kiritilmagan')
        address = data.get('address', 'Kiritilmagan')
        is_active = "✅ Faol" if data.get('is_active') else "⏳ Kutilmoqda"
        
        # Telefon raqamlarni formatlash
        phone_info = f"📱 Telegram: {tg_tel}"
        if tel and tel != tg_tel:
            phone_info += f"\n📞 Asosiy: {tel}"
        phone_info += f"\n👨‍👩‍👦 Ota-ona: {parent_tel}"
        
        text = (
            f"👤 <b>Sizning ma'lumotlaringiz:</b>\n\n"
            f"<b>F.I.Sh:</b> {fio}\n"
            f"<b>JSHSHIR:</b> {pnfl}\n"
            f"<b>Telefon raqamlar:</b>\n{phone_info}\n"
            f"<b>Manzil:</b> {address}\n\n"
            f"<b>Status:</b> {is_active}\n"
        )
        
        await message.answer(text, reply_markup=update_info_markup())
        
    except Exception as e:
        print(f"Ma'lumotlarni olishda xatolik: {e}")
        await message.answer(
            "❌ Ma'lumotlarni olishda xatolik yuz berdi.",
            reply_markup=register_markup()
        )

@router.message(F.text == "📝 Ma'lumotlarni yangilash")
async def update_user_info(message: types.Message):
    """Ma'lumotlarni yangilash"""
    await message.answer(
        "📝 Ma'lumotlarni yangilash uchun qaytadan registratsiyadan o'ting.\n"
        "Yangi ma'lumotlaringiz eskisini almashtiradi:",
        reply_markup=register_markup()
    )
