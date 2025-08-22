from aiogram import types, F, Router
from aiogram.enums import ChatType, ChatMemberStatus
from keyboards.inline.buttons import inine_add_group
from loader import db, bot
from data.config import ADMINS
from utils.db.postgres import api_client

router = Router()

@router.message(F.text == "👥 Guruhga qo'shish")
async def start_register(message: types.Message):
    text = "Guruhga qo'shish uchun pastdagi tugmani bosib guruh tanlang!"
    await message.answer(text=text, reply_markup=inine_add_group)
    

@router.my_chat_member()
async def bot_added_to_group(event: types.ChatMemberUpdated):
    if event.chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
        return
    
    if event.new_chat_member.user.id != (await bot.get_me()).id:
        return
    
    if (event.old_chat_member.status in [ChatMemberStatus.LEFT, ChatMemberStatus.KICKED] and 
        event.new_chat_member.status in [ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR]):
        
        title = event.chat.title
        group_id = event.chat.id
        
        admin_ids = ADMINS
        
        accept_text = f"🎉 Bot yangi guruhga qo'shildi!\n\n📋 Guruh: {title}\n🆔 ID: {group_id}"
        error_text = f"❗️❗️ Botni guruhga qo'shishda xatolik bo‘ldi.\nQaytadan urinib ko‘ring"
        
        try:
            # Har bir admin foydalanuvchiga xabar yuborish
            for admin_id in admin_ids:
                try:
                    await bot.send_message(chat_id=admin_id, text=accept_text)
                except Exception as e:
                    print(f"Admin {admin_id} ga xabar yuborilmadi: {e}")
                        
            # Guruhni API orqali backendga yuborish
            resp = await api_client.add_group(title, group_id)
            if not resp or resp.get("success") is False:
                print(f"Backendga yozishda xatolik: {resp}")
                if admin_ids:
                    await bot.send_message(chat_id=admin_ids[0], text=error_text)

        except Exception as e:
            print(f"Xatolik: {e}")
            if admin_ids:
                await bot.send_message(chat_id=admin_ids[0], text=error_text)
