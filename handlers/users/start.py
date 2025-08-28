from aiogram import Router, types
from aiogram.filters import CommandStart
from aiogram.types import ReplyKeyboardRemove
from aiogram.enums.parse_mode import ParseMode
from aiogram.client.session.middlewares.request_logging import logger
from loader import db, bot
from data.config import ADMINS
from utils.extra_datas import make_title
from keyboards.reply.buttons import add_group, register_markup, update_info_markup
from utils.db.postgres import api_client


router = Router()

def make_title(name: str) -> str:
    return name.title() if name else "Foydalanuvchi"

@router.message(CommandStart())
async def do_start(message: types.Message):
    full_name = message.from_user.full_name
    telegram_id = message.from_user.id
    
    try:
        # Foydalanuvchi holatini tekshirish
        user_status = await api_client.check_user_status(telegram_id)
        
        if not user_status or not user_status.get('success'):
            # API xatoligi bo'lsa
            await message.answer(
                f"Assalomu alaykum {make_title(full_name)}!\n\n"
                "❌ Serverda muammo yuz berdi. Iltimos, keyinroq qaytadan urinib ko'ring.",
                reply_markup=register_markup()
            )
            return
        
        status = user_status.get('status')
        user_data = user_status.get('user_data', {})
        
        if status == 'incomplete_registration':
            # Telegram ID bor, lekin PNFL yo'q (yarim registratsiya)
            fio = user_data.get('fio', full_name)
            await message.answer(
                f"Assalomu alaykum {make_title(fio)}!\n\n"
                "⚠️ Sizning registratsiyangiz yakunlanmagan.\n"
                "📝 Iltimos, ma'lumotlaringizni to'ldirishni yakunlang:",
                reply_markup=register_markup()
            )
        
        elif status == 'registered':
            # To'liq ro'yxatdan o'tgan foydalanuvchi
            fio = user_data.get('fio', full_name)
            is_active = user_data.get('is_active', False)
            
            # Status xabari
            status_msg = ""
            if not is_active:
                status_msg = "⏳ Sizning hisobingiz hali tasdiqlanmagan.\nAdmin tomonidan ko'rib chiqilmoqda."
            else:
                status_msg = "✅ Sizning hisobingiz tasdiqlangan."
            
            await message.answer(
                f"Assalomu alaykum {make_title(fio)}!\n\n"
                f"🤖 Botimizga xush kelibsiz!\n\n"
                f"{status_msg}\n\n"
                "📝 Kerakli bo'lsa, ma'lumotlaringizni yangilashingiz mumkin:",
                reply_markup=update_info_markup() if is_active else register_markup()
            )
        
        else:
            await message.answer(
                f"Assalomu alaykum {make_title(fio)}!"
                f"❌ Bu bot siz uchun ishlamaydi.",
                reply_markup=ReplyKeyboardRemove()
            )
    
    except Exception as e:
        print(f"Start handlerda xatolik: {e}")
        await message.answer(
            f"Assalomu alaykum {make_title(full_name)}!\n\n"
            "❌ Kechirasiz, Bu bot siz uchun ishlamaydi.",
            reply_markup=ReplyKeyboardRemove()
        )