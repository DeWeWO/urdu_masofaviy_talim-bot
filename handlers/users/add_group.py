import asyncio
import logging
from datetime import datetime
from aiogram import types, F, Router
from aiogram.enums import ChatType, ChatMemberStatus
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters.callback_data import CallbackData
from keyboards.inline.buttons import inine_add_group
from loader import bot
from utils.db.postgres import api_client
from utils.telethon_client import telethon_client

router = Router()

# Callback data class
class GroupTypeCallback(CallbackData, prefix="group_type"):
    action: str
    group_id: int

# Guruh turlarini saqlash uchun (xotirada)
pending_teacher_groups = set()
group_types = {}  # group_id: is_teacher_group

async def send_to_all_admins(message: str):
    """Barcha adminlarga xabar yuborish"""
    try:
        async with api_client as client:
            # Barcha adminlarni olish
            all_users = await client.get_all_users_basic_info()
            
            if not all_users or not all_users.get("success") or not all_users.get("data"):
                logging.warning("Could not fetch admin list")
                return
            
            admin_count = 0
            for user_data in all_users["data"]:
                try:
                    telegram_id = user_data.get("telegram_id")
                    if not telegram_id:
                        continue
                    
                    # Har bir foydalanuvchi uchun admin ekanligini tekshirish
                    admin_check = await client.check_admin(telegram_id)
                    if admin_check and admin_check.get("is_admin"):
                        await bot.send_message(
                            chat_id=telegram_id,
                            text=message,
                            parse_mode="HTML"
                        )
                        admin_count += 1
                        
                        # Rate limiting - adminlar orasida kichik pauza
                        await asyncio.sleep(0.1)
                        
                except Exception as e:
                    logging.warning(f"Failed to send message to admin {telegram_id}: {e}")
                    continue
                    
            logging.info(f"Message sent to {admin_count} admins")
            
    except Exception as e:
        logging.error(f"Error sending message to admins: {e}")

@router.message(F.text == "👥 Guruhga qo'shish")
async def start_teacher_register(message: types.Message):
    telegram_id = message.from_user.id
    
    try:
        async with api_client as client:
            admin_data = await client.check_admin(telegram_id)
        
        if not admin_data or not admin_data.get("is_admin"):
            await message.answer("❌ Sizda admin huquqi yo'q.")
            return
        
        # O'qituvchi rejimini yoqish
        pending_teacher_groups.add(telegram_id)
        
        await message.answer(
            "Botni guruhga qo'shgandan keyin 👨‍🎓 Talabalr yoki 👨‍🏫 O'qituvchilar guruhi ekanligini tanlashingiz kerak bo'ladi.",
            reply_markup=inine_add_group,
            parse_mode="HTML"
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
        
        # Guruh turini so'rash
        await _ask_group_type(event.chat)

async def _ask_group_type(chat):
    """Admin dan guruh turini so'rash"""
    group_id = chat.id
    title = chat.title or "No title"
    
    type_action = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="👨‍🎓 Talabalar guruhi", 
                callback_data=GroupTypeCallback(action="student", group_id=group_id).pack()
            )
        ],
        [
            InlineKeyboardButton(
                text="👨‍🏫 O'qituvchilar guruhi", 
                callback_data=GroupTypeCallback(action="teacher", group_id=group_id).pack()
            )
        ]
    ])
    
    message_text = (
        f"🎉 Bot yangi guruhga qo'shildi!\n\n"
        f"📋 Guruh: {title}\n"
        f"🆔 ID: {group_id}\n\n"
        f"❓ Bu qanday guruh?"
    )
    
    # Barcha adminlarga xabar yuborish (inline keyboard bilan)
    try:
        async with api_client as client:
            # Barcha adminlarni olish
            all_users = await client.get_all_users_basic_info()
            
            if not all_users or not all_users.get("success") or not all_users.get("data"):
                logging.warning("Could not fetch admin list")
                return
            
            admin_count = 0
            for user_data in all_users["data"]:
                try:
                    telegram_id = user_data.get("telegram_id")
                    if not telegram_id:
                        continue
                    
                    # Har bir foydalanuvchi uchun admin ekanligini tekshirish
                    admin_check = await client.check_admin(telegram_id)
                    if admin_check and admin_check.get("is_admin"):
                        await bot.send_message(
                            chat_id=telegram_id,
                            text=message_text,
                            reply_markup=type_action,
                            parse_mode="HTML"
                        )
                        admin_count += 1
                        
                        # Rate limiting
                        await asyncio.sleep(0.1)
                        
                except Exception as e:
                    logging.warning(f"Failed to send group type selection to admin {telegram_id}: {e}")
                    continue
                    
            logging.info(f"Group type selection sent to {admin_count} admins")
            
    except Exception as e:
        logging.error(f"Error sending group type selection to admins: {e}")

@router.callback_query(GroupTypeCallback.filter())
async def handle_group_type_selection(callback: types.CallbackQuery, callback_data: GroupTypeCallback):
    group_id = callback_data.group_id
    is_teacher_group = callback_data.action == "teacher"
    group_type = "o'qituvchilar" if is_teacher_group else "talabalar"
    
    try:
        # Guruh turini saqlash
        group_types[group_id] = is_teacher_group
        
        # Callback ni javoblash
        await callback.answer(f"✅ {group_type.title()} guruhi sifatida belgilandi!")
        
        # Xabarni yangilash
        await callback.message.edit_text(
            f"✅ Guruh {group_type} guruhi sifatida belgilandi!\n\n"
            f"📋 Guruh ID: {group_id}\n\n"
            f"🔄 A'zolarni qayta ishlamoqda..."
        )
        
        # Guruhni va a'zolarni qayta ishlash
        chat = await bot.get_chat(group_id)
        await _handle_bot_added(chat, is_teacher_group)
        
    except Exception as e:
        logging.error(f"Group type selection error: {e}")
        await callback.answer("❌ Xatolik yuz berdi!", show_alert=True)

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
        # Guruhning o'qituvchi guruhi ekanligini tekshirish
        is_teacher_group = group_types.get(group_id, False)
        
        # A'zo qo'shildi
        if (old_status in (ChatMemberStatus.LEFT, ChatMemberStatus.KICKED) and 
            new_status in (ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR)):
            await _handle_member_join(user_data, group_id, event.chat.title, event.date, is_teacher_group)
        
        # A'zo chiqdi/chiqarildi
        elif (old_status in (ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR) and 
              new_status in (ChatMemberStatus.LEFT, ChatMemberStatus.KICKED)):
            await _handle_member_leave(user_data, group_id, event.chat.title, event, new_status)
            
    except Exception as e:
        logging.error(f"Member change handling error: {e}")
        await send_to_all_admins(f"⚠️ A'zo o'zgarishlarini qayta ishlashda xatolik: {str(e)}")

async def _check_if_teacher_group(group_id: int) -> bool:
    """Guruhning o'qituvchi guruhi ekanligini tekshirish"""
    return group_types.get(group_id, False)

async def _handle_bot_added(chat, is_teacher_group: bool = False):
    """Bot guruhga qo'shilganda"""
    title = chat.title or "No title"
    group_id = chat.id
    group_type = "o'qituvchilar" if is_teacher_group else "talabalar"
    
    try:
        # Guruhni bazaga qo'shish
        async with api_client as client:
            result = await client.add_group_with_type(title, group_id, is_teacher_group)
            
            if not _is_success_response(result):
                error_msg = _get_error_message(result)
                logging.error(f"Group add error: {error_msg}")
                await send_to_all_admins(f"⚠️ Guruhni bazaga qo'shishda xatolik: {error_msg}")
                return
        
        logging.info(f"Group {group_id} ({title}) successfully added as {group_type} group")
        
        # A'zolarni yig'ish va qo'shish
        await _process_group_members(group_id, is_teacher_group)
        
    except Exception as e:
        logging.error(f"Bot added handler error: {e}")
        await send_to_all_admins("⚠️ Botni guruhga qo'shishda xatolik yuz berdi.")

async def _process_group_members(group_id: int, is_teacher_group: bool = False):
    """Guruh a'zolarini yig'ish va bazaga qo'shish"""
    try:
        # A'zolarni yig'ish
        members = []
        async for user in telethon_client.iter_participants(group_id):
            if not getattr(user, "bot", False):
                members.append(_format_user_data(user))
        
        if not members:
            await send_to_all_admins("⚠️ Guruhda foydalanuvchilar topilmadi.")
            return
        
        success_count = 0
        failed_count = 0
        group_type = "O'qituvchilar" if is_teacher_group else "Talabalar"
        
        # A'zolarni bazaga qo'shish
        async with api_client as client:
            for i, member in enumerate(members, start=1):
                try:
                    success = await _add_user_to_group(client, member, group_id, is_teacher_group)
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
            f"📊 {group_type} guruhi a'zolari qayta ishlandi:\n\n"
            f"✅ Muvaffaqiyatli: {success_count}\n"
            f"❌ Xatolik: {failed_count}\n"
            f"📋 Jami: {len(members)}"
        )
        await send_to_all_admins(result_text)
        
    except Exception as e:
        logging.error(f"Process group members error: {e}")
        await send_to_all_admins("⚠️ Guruh a'zolarini qayta ishlashda xatolik yuz berdi.")

async def _add_user_to_group(client, user_data: dict, group_id: int, is_teacher: bool = False) -> bool:
    """Foydalanuvchini guruhga qo'shish"""
    try:
        result = await client.safe_add_register(
            telegram_id=user_data["id"],
            data={
                "username": user_data["username"],
                "first_name": user_data["full_name"],
                "register_groups": [group_id],
                "is_teacher": is_teacher
            }
        )
        
        return _is_success_response(result)
        
    except Exception as e:
        logging.error(f"Add user to group error: {e}")
        return False

async def _handle_member_join(user_data: dict, group_id: int, group_title: str, event_date, is_teacher_group: bool = False):
    """Yangi a'zo qo'shilganda"""
    try:
        user_type = "o'qituvchi" if is_teacher_group else "talaba"
        
        # Adminlarga xabar
        join_text = (
            f"🟢 Yangi {user_type} qo'shildi!\n\n"
            f"👤 {user_data['full_name'] or f'User {user_data["id"]}'}\n"
            f"🆔 @{user_data['username'] or user_data['id']}\n"
            f"💬 {group_title}\n"
            f"🆔 Guruh ID: {group_id}"
        )
        await send_to_all_admins(join_text)
        
        # Foydalanuvchini bazaga qo'shish
        async with api_client as client:
            success = await _add_user_to_group(client, user_data, group_id, is_teacher_group)
            
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
        await send_to_all_admins(leave_text)
        
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

# Eski _notify_admins funksiyasi o'rniga send_to_all_admins ishlatiladi
async def _notify_admins(message: str):
    """Deprecated: Use send_to_all_admins instead"""
    await send_to_all_admins(message)