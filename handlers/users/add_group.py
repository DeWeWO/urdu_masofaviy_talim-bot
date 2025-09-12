import asyncio
import logging
from datetime import datetime
from aiogram import types, F, Router
from aiogram.enums import ChatType, ChatMemberStatus
from keyboards.inline.buttons import inine_add_group
from loader import bot
from data.config import ADMINS
from utils.db.postgres import api_client
from utils.telethon_client import telethon_client

router = Router()

@router.message(F.text == "👥 Guruhga qo'shish")
async def start_register(message: types.Message):
    telegram_id = message.from_user.id
    
    try:
        async with api_client as client:
            admin_data = await client.check_admin(telegram_id)
        
        if not admin_data or not admin_data.get("is_admin"):
            await message.answer("❌ Sizda admin huquqi yo'q.")
            return
        
        await message.answer(
            "Guruhga qo'shish uchun pastdagi tugmani bosib guruh tanlang!",
            reply_markup=inine_add_group
        )
    except Exception as e:
        logging.error(f"Admin check error: {e}")
        await message.answer("❌ Xatolik yuz berdi. Qaytadan urinib ko'ring.")

@router.my_chat_member()
async def bot_added_to_group(event: types.ChatMemberUpdated):
    if event.chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        return

    me = await bot.get_me()
    if event.new_chat_member.user.id != me.id:
        return

    # Bot guruhga qo'shildi
    if (event.old_chat_member.status in (ChatMemberStatus.LEFT, ChatMemberStatus.KICKED) and 
        event.new_chat_member.status in (ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR)):
        
        await _handle_bot_added(event.chat)

@router.chat_member()
async def handle_member_changes(event: types.ChatMemberUpdated):
    if event.chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        return

    me = await bot.get_me()
    if event.new_chat_member.user.id == me.id:
        return

    user = event.new_chat_member.user
    old_status = event.old_chat_member.status
    new_status = event.new_chat_member.status
    group_id = event.chat.id
    
    user_data = _format_user_data(user)

    try:
        # A'zo qo'shildi
        if (old_status in (ChatMemberStatus.LEFT, ChatMemberStatus.KICKED) and 
            new_status in (ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR)):
            await _handle_member_join(user_data, group_id, event.chat.title, event.date)
        
        # A'zo chiqdi/chiqarildi
        elif (old_status in (ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR) and 
              new_status in (ChatMemberStatus.LEFT, ChatMemberStatus.KICKED)):
            await _handle_member_leave(user_data, group_id, event.chat.title, event, new_status)
            
    except Exception as e:
        logging.error(f"Member change handling error: {e}")
        await _notify_admins(f"⚠️ A'zo o'zgarishlarini qayta ishlashda xatolik: {str(e)}")

async def _handle_bot_added(chat):
    """Bot guruhga qo'shilganda"""
    title = chat.title or "No title"
    group_id = chat.id
    
    try:
        # Adminlarga xabar
        await _notify_admins(f"🎉 Bot yangi guruhga qo'shildi!\n\n📋 Guruh: {title}\n🆔 ID: {group_id}")
        
        # Guruhni bazaga qo'shish
        async with api_client as client:
            result = await client.add_group(title, group_id)
            
            if not _is_success_response(result):
                error_msg = _get_error_message(result)
                logging.error(f"Group add error: {error_msg}")
                await _notify_admins(f"⚠️ Guruhni bazaga qo'shishda xatolik: {error_msg}")
                return
        
        logging.info(f"Group {group_id} ({title}) successfully added")
        
        # A'zolarni yig'ish va qo'shish
        await _process_group_members(group_id)
        
    except Exception as e:
        logging.error(f"Bot added handler error: {e}")
        await _notify_admins("⚠️ Botni guruhga qo'shishda xatolik yuz berdi.")

async def _process_group_members(group_id: int):
    """Guruh a'zolarini yig'ish va bazaga qo'shish"""
    try:
        # A'zolarni yig'ish
        members = []
        async for user in telethon_client.iter_participants(group_id):
            if not getattr(user, "bot", False):
                members.append(_format_user_data(user))
        
        if not members:
            await _notify_admins("⚠️ Guruhda foydalanuvchilar topilmadi.")
            return
        
        success_count = 0
        failed_count = 0
        
        # A'zolarni bazaga qo'shish
        async with api_client as client:
            for i, member in enumerate(members, start=1):
                try:
                    success = await _add_user_to_group(client, member, group_id)
                    if success:
                        success_count += 1
                    else:
                        failed_count += 1
                        
                    # Rate limiting
                    if i % 10 == 0:
                        await asyncio.sleep(0.2)
                        
                except Exception as e:
                    logging.error(f"Member processing error for {member['id']}: {e}")
                    failed_count += 1
        
        # Natija haqida xabar
        result_text = (
            f"📊 Guruh a'zolari qayta ishlandi:\n\n"
            f"✅ Muvaffaqiyatli: {success_count}\n"
            f"❌ Xatolik: {failed_count}\n"
            f"📋 Jami: {len(members)}"
        )
        await _notify_admins(result_text)
        
    except Exception as e:
        logging.error(f"Process group members error: {e}")
        await _notify_admins("⚠️ Guruh a'zolarini qayta ishlashda xatolik yuz berdi.")

async def _add_user_to_group(client, user_data: dict, group_id: int) -> bool:
    """Foydalanuvchini guruhga qo'shish"""
    try:
        result = await client.safe_add_register(
            telegram_id=user_data["id"],
            data={
                "username": user_data["username"],
                "first_name": user_data["full_name"],
                "register_groups": [group_id]
            }
        )
        
        return _is_success_response(result)
        
    except Exception as e:
        logging.error(f"Add user to group error: {e}")
        return False

async def _handle_member_join(user_data: dict, group_id: int, group_title: str, event_date):
    """Yangi a'zo qo'shilganda"""
    try:
        # Adminlarga xabar
        join_text = (
            f"🟢 Yangi a'zo qo'shildi!\n\n"
            f"👤 {user_data['full_name'] or f'User {user_data["id"]}'}\n"
            f"🆔 @{user_data['username'] or user_data['id']}\n"
            f"💬 {group_title}\n"
            f"🆔 Guruh ID: {group_id}"
        )
        await _notify_admins(join_text)
        
        # Foydalanuvchini bazaga qo'shish
        async with api_client as client:
            success = await _add_user_to_group(client, user_data, group_id)
            
            if success:
                # Faoliyat yozuvi
                await _add_activity_log(
                    client, user_data["id"], group_id, 
                    'join', 'system', event_date.isoformat()
                )
                
    except Exception as e:
        logging.error(f"Handle member join error: {e}")

async def _handle_member_leave(user_data: dict, group_id: int, group_title: str, event, leave_status):
    """A'zo chiqganda/chiqarilganda"""
    try:
        action = "chiqarildi" if leave_status == ChatMemberStatus.KICKED else "chiqdi"
        emoji = "🚫" if leave_status == ChatMemberStatus.KICKED else "🔴"
        
        # Admin ma'lumotlari
        admin_info = {}
        from_user = event.from_user
        
        if from_user and from_user.id != user_data["id"]:
            by_whom = f"👨‍💼 Kim: {from_user.full_name or 'Noma\'lum'} (@{from_user.username or from_user.id})"
            admin_info = {
                "admin_telegram_id": from_user.id,
                "admin_name": from_user.full_name,
                "admin_username": from_user.username
            }
        else:
            by_whom = "📝 O'zi chiqdi"
        
        # Adminlarga xabar
        leave_text = (
            f"{emoji} A'zo {action}!\n\n"
            f"👤 {user_data['full_name'] or f'User {user_data["id"]}'}\n"
            f"🆔 @{user_data['username'] or user_data['id']}\n"
            f"{by_whom}\n"
            f"💬 {group_title}"
        )
        await _notify_admins(leave_text)
        
        # Guruhdan o'chirish
        async with api_client as client:
            await _remove_user_from_group(client, user_data, group_id)
            
            # Faoliyat yozuvi
            activity_type = 'leave' if leave_status == ChatMemberStatus.LEFT else 'kicked'
            action_by = 'self' if not admin_info else 'admin'
            
            await _add_activity_log(
                client, user_data["id"], group_id,
                activity_type, action_by, event.date.isoformat(),
                **admin_info
            )
            
    except Exception as e:
        logging.error(f"Handle member leave error: {e}")

async def _remove_user_from_group(client, user_data: dict, group_id: int):
    """Foydalanuvchini guruhdan o'chirish"""
    try:
        # Avval foydalanuvchining guruhlarini olish
        existing_user = await client.get_user_full_info(user_data["id"])
        
        if _is_success_response(existing_user) and existing_user.get("data"):
            existing_groups = [g["group_id"] for g in existing_user["data"].get("register_groups", [])]
            remaining_groups = [g for g in existing_groups if g != group_id]
            
            # Foydalanuvchini yangi guruhlar ro'yxati bilan yangilash
            await client.safe_add_register(
                telegram_id=user_data["id"],
                data={
                    "username": user_data["username"],
                    "first_name": user_data["full_name"],
                    "register_groups": remaining_groups
                }
            )
            
    except Exception as e:
        logging.error(f"Remove user from group error: {e}")

async def _add_activity_log(client, telegram_id: int, group_id: int, activity_type: str, 
                          action_by: str, activity_time: str, **kwargs):
    """Faoliyat yozuvini qo'shish"""
    try:
        await client.add_member_activity(
            telegram_id=telegram_id,
            group_id=group_id,
            activity_type=activity_type,
            action_by=action_by,
            activity_time=activity_time,
            **kwargs
        )
    except Exception as e:
        logging.warning(f"Activity log error: {e}")

def _format_user_data(user) -> dict:
    """Foydalanuvchi ma'lumotlarini formatlash"""
    full_name = " ".join(filter(None, [
        getattr(user, 'first_name', None), 
        getattr(user, 'last_name', None)
    ])).strip() or None
    
    return {
        "id": user.id,
        "full_name": full_name,
        "username": getattr(user, 'username', None),
    }

def _is_success_response(response) -> bool:
    """API response ni tekshirish"""
    if not response:
        return False
    
    # Agar response dict bo'lsa va success false bo'lsa
    if isinstance(response, dict):
        if "success" in response:
            return response["success"] is not False
        # Agar success maydoni yo'q bo'lsa, error tekshiramiz
        if "error" in response:
            return False
    
    return True

def _get_error_message(response) -> str:
    """Xatolik xabarini olish"""
    if isinstance(response, dict):
        if response.get("error"):
            return str(response["error"])
        if response.get("message"):
            return str(response["message"])
    return "Noma'lum xatolik"

async def _notify_admins(message: str):
    """Adminlarga xabar yuborish"""
    admin_ids = ADMINS if isinstance(ADMINS, (list, tuple)) else [ADMINS]
    
    for admin_id in admin_ids:
        try:
            async with api_client as client:
                admin_data = await client.check_admin(admin_id)
                if admin_data and admin_data.get("is_admin"):
                    await bot.send_message(
                        chat_id=admin_id, 
                        text=message, 
                        parse_mode="HTML"
                    )
                    break  # Birinchi adminga yuborib to'xtatish
        except Exception as e:
            logging.warning(f"Admin notification error for {admin_id}: {e}")
            continue