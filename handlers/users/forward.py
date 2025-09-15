from aiogram import Router, types
from loader import db

router = Router()

@router.message()
async def handle_forwarded_message(message: types.Message):
    # Agar forward qilingan xabar bo'lmasa, return qil
    if not (message.forward_from or message.forward_from_chat or message.forward_date):
        return
    
    telegram_id = message.from_user.id
    
    # Admin tekshirish
    try:
        async with db as client:
            admin_data = await client.check_admin(telegram_id)
    except:
        await message.answer("❌ Noto'g'ri format.")
        return
    
    if not (admin_data and admin_data.get("is_admin")):
        await message.answer("❌ Noto'g'ri format.")
        return
    
    # Forward qilingan foydalanuvchi ma'lumotlari tekshirish
    forwarded_user = message.forward_from
    
    # Agar foydalanuvchi ma'lumotlari yo'q bo'lsa (har qanday sababga ko'ra)
    if not forwarded_user:
        await message.answer("❌ Foydalanuvchi ma'lumotlari yopiq.")
        return
    
    # Foydalanuvchi ma'lumotlarini olish
    try:
        async with db as client:
            user_data = await client.get_user_info(forwarded_user.id)
    except:
        await message.answer("❌ Noto'g'ri format.")
        return
    
    if not user_data:
        await message.answer("❗ Rasmiy foydalanuvchi emas.")
        return
    
    # Ma'lumotlarni formatlash
    hemis = user_data.get("hemis", {}) or {}
    phones = user_data.get("phones", {}) or {}
    
    text = (
        f"👤 {user_data.get('fio', '-')}\n"
        f"🆔 Hemis ID: {user_data.get('hemis_id', '-')}\n"
        f"📚 Kurs: {hemis.get('course', '-')}\n"
        f"👥 Guruh: {hemis.get('student_group', '-')}\n"
        f"🛂 Passport: {hemis.get('passport', '-')}\n"
        f"📱 Telegram: {phones.get('tg_tel', '-')}\n"
        f"☎️ Telefon: {phones.get('tel', '-')}\n"
        f"👨‍👩‍👦 Ota-ona: {phones.get('parent_tel', '-')}\n"
        f"🏠 Manzil: {user_data.get('address', '-')}"
    )
    
    await message.answer(text)