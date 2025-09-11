from aiogram import Router, types
from aiogram.filters import CommandStart
from aiogram.types import ReplyKeyboardRemove
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
        async with api_client as client:
            # Foydalanuvchi holatini tekshirish
            user_status = await client.check_user_status(telegram_id)
            
            if not user_status or not user_status.get('success'):
                await message.answer(
                    f"Assalomu alaykum {make_title(full_name)}!\n\n"
                    "❌ Serverda muammo yuz berdi. Keyinroq urinib ko'ring.",
                    reply_markup=register_markup()
                )
                return
            
            status = user_status.get('status')
            user_data = user_status.get('user_data', {})
            fio = user_data.get('fio', full_name)
            
            if status == 'incomplete_registration':
                await message.answer(
                    f"Assalomu alaykum {make_title(fio)}!\n\n"
                    "⚠️ Registratsiyangiz yakunlanmagan.\n"
                    "📝 Ma'lumotlaringizni to'ldirishni yakunlang:",
                    reply_markup=register_markup()
                )
            
            elif status == 'registered':
                is_active = user_data.get('is_active', False)
                
                # Admin tekshirish
                admin_data = await client.check_admin(telegram_id)
                
                # Klaviatura tanlash
                if admin_data and admin_data.get("is_admin"):
                    reply_kb = add_group()
                elif is_active:
                    reply_kb = update_info_markup()
                else:
                    reply_kb = register_markup()
                
                # Status xabari
                status_text = ""
                if not is_active:
                    status_text = "\n⏳ Hisobingiz tasdiqlanmagan. Admin ko'rib chiqmoqda."
                else:
                    status_text = "\n✅ Hisobingiz tasdiqlangan."
                
                await message.answer(
                    f"Assalomu alaykum {make_title(fio)}!",
                    reply_markup=reply_kb
                )
            
            else:
                await message.answer(
                    f"Assalomu alaykum {make_title(full_name)}!\n\n"
                    "❌ Bu bot siz uchun ishlamaydi.",
                    reply_markup=ReplyKeyboardRemove()
                )
    
    except Exception as e:
        print(f"Start handler xatoligi: {e}")
        await message.answer(
            f"Assalomu alaykum {make_title(full_name)}!\n\n"
            "❌ Bu bot siz uchun ishlamaydi.",
            reply_markup=ReplyKeyboardRemove()
        )