from aiogram import Router
from aiogram.types import Message
from loader import db
import logging

logger = logging.getLogger(__name__)
router = Router()


@router.message()
async def forward_user_info(message: Message):
    # Forward qilingan xabar bo‘lishi kerak
    if not message.forward_date or not message.forward_from:
        return

    telegram_id = message.forward_from.id

    try:
        user_data = await db.get_user_info(telegram_id)
    except Exception as e:
        await message.answer("❌ Foydalanuvchi ma’lumotlarini olishda xatolik yuz berdi.")
        return

    if not user_data or "detail" in user_data:
        await message.answer("❗️ Rasmiy foydalanuvchi emas.")
        return

    # Register ma’lumotlari
    fio = user_data.get("fio") or user_data.get("username") or "Noma’lum"
    hemis_id = user_data.get("hemis_id") or "-"
    address = user_data.get("address") or "-"

    phones = user_data.get("phones", {})
    tg_tel = phones.get("tg_tel") or "-"
    tel = phones.get("tel") or "-"
    parent_tel = phones.get("parent_tel") or "-"

    # Hemis ma’lumotlari
    hemis = user_data.get("hemis") or {}
    course = hemis.get("course") or "-"
    student_group = hemis.get("student_group") or "-"
    passport = hemis.get("passport") or "-"

    text = (
        f"👤 {fio}\n"
        f"🆔 Hemis ID: {hemis_id}\n"
        f"📚 Kurs: {course}\n"
        f"👥 Guruh: {student_group}\n"
        f"🛂 Passport: {passport}\n\n"
        f"📱 Telegram tel: {tg_tel}\n"
        f"☎️ Telefon: {tel}\n"
        f"👨‍👩‍👦 Ota-ona tel: {parent_tel}\n"
        f"🏠 Manzil: {address}"
    )

    await message.answer(text)
