from aiogram import types, F, Router
from aiogram.enums import ChatType, ChatMemberStatus
from keyboards.inline.buttons import inine_add_group
from loader import db, bot
from data.config import ADMINS
from utils.db.postgres import api_client
from utils.telethon_client import telethon_client

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
        error_text = f"❗️❗️ Botni guruhga qo'shishda xatolik bo'ldi.\nQaytadan urinib ko'ring"
        
        try:
            # 1. Adminlarga xabar yuborish
            for admin_id in admin_ids:
                try:
                    await bot.send_message(chat_id=admin_id, text=accept_text)
                except Exception as e:
                    print(f"Admin {admin_id} ga xabar yuborilmadi: {e}")
            
            # 2. Guruhni API orqali backendga yuborish
            resp = await api_client.add_group(title, group_id)
            if not resp or resp.get("success") is False:
                print(f"Backendga yozishda xatolik: {resp}")
                if admin_ids:
                    await bot.send_message(chat_id=admin_ids[0], text=error_text)

            # 3. Telethon orqali guruh a'zolarini olish
            members = []
            async for user in telethon_client.iter_participants(group_id):
                members.append({
                    "id": user.id,
                    "full_name": f"{user.first_name or ''} {user.last_name or ''}".strip(),
                    "username": user.username
                })

            # 4. Adminlarga qismini yuborish
            preview = "\n".join([
                f"{m['id']} | {m['full_name']} | @{m['username'] or ''}"
                for m in members[:40]
            ])

            info_text = (
                f"✅ Guruhdan jami <b>{len(members)}</b> ta a'zo olindi.\n\n"
                f"<b>Misol (40 ta):</b>\n<code>{preview}</code>"
            )

            for admin_id in admin_ids:
                try:
                    await bot.send_message(chat_id=admin_id, text=info_text)
                except Exception as e:
                    print(f"Admin {admin_id} ga preview yuborilmadi: {e}")

        except Exception as e:
            print(f"Xatolik: {e}")
            if admin_ids:
                await bot.send_message(chat_id=admin_ids[0], text=error_text)


@router.chat_member()
async def new_member_added(event: types.ChatMemberUpdated):
    if event.chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
        return
    
    if event.new_chat_member.user.id == (await bot.get_me()).id:
        return
    
    if (event.old_chat_member.status in [ChatMemberStatus.LEFT, ChatMemberStatus.KICKED] and 
        event.new_chat_member.status in [ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR]):
        
        user = event.new_chat_member.user
        group_id = event.chat.id
        group_title = event.chat.title
        
        user_data = {
            "id": user.id,
            "full_name": f"{user.first_name or ''} {user.last_name or ''}".strip(),
            "username": user.username
        }
        
        try:            
            member_text = (
                f"👤 Yangi a'zo qo'shildi!\n\n"
                f"📋 Guruh: {group_title}\n"
                f"🆔 Guruh ID: {group_id}\n\n"
                f"👤 A'zo: {user_data['full_name']}\n"
                f"🆔 ID: {user_data['id']}\n"
                f"📱 Username: @{user_data['username'] or 'mavjud emas'}"
            )
            
            for admin_id in ADMINS:
                try:
                    await bot.send_message(chat_id=admin_id, text=member_text)
                except Exception as e:
                    print(f"Admin {admin_id} ga yangi a'zo haqida xabar yuborilmadi: {e}")
                    
        except Exception as e:
            print(f"Yangi a'zoni qayta ishlashda xatolik: {e}")