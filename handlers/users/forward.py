import asyncio
import logging
from datetime import datetime
from aiogram import types, F, Router
from aiogram.enums import ChatType, ChatMemberStatus
from keyboards.inline.buttons import inine_add_group
from loader import bot
from utils.db.postgres import api_client
from utils.telethon_client import telethon_client

router = Router()

@router.message(F.text == "👥 Guruhga qo'shish")
async def start_register(message: types.Message):
    telegram_id = message.from_user.id
    
    # Admin tekshirish
    async with api_client as client:
        admin_data = await client.check_admin(telegram_id)
    
    if not (admin_data and admin_data.get("is_admin")):
        await message.answer("❌ Noto'g'ri format.")
        return
    
    await message.answer(
        "Guruhga qo'shish uchun pastdagi tugmani bosib guruh tanlang!",
        reply_markup=inine_add_group
    )

@router.my_chat_member()
async def bot_added_to_group(event: types.ChatMemberUpdated):
    if event.chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        return

    me = await bot.get_me()
    if event.new_chat_member.user.id != me.id:
        return

    if (event.old_chat_member.status in (ChatMemberStatus.LEFT, ChatMemberStatus.KICKED)
        and event.new_chat_member.status in (ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR)):
        
        title = event.chat.title or "No title"
        group_id = event.chat.id

        try:
            # Adminlarga xabar
            accept_text = f"🎉 Bot yangi guruhga qo'shildi!\n\n📋 Guruh: {title}\n🆔 ID: {group_id}"
            await _send_to_admins(accept_text)

            # Guruhni backendga yozish
            async with api_client as client:
                resp = await client.add_group(title, group_id)
                if not resp or (isinstance(resp, dict) and resp.get("success") is False):
                    logging.error(f"Backendga guruhni yozishda xatolik: {resp}")
                    await _send_error_to_admin("⚠️ Botni guruhga qo'shishda xatolik bo'ldi.")
                    return

            # A'zolarni yig'ish va yozish
            await _process_group_members(group_id)

        except Exception as e:
            logging.exception(f"bot_added_to_group xatolik: {e}")
            await _send_error_to_admin("⚠️ Guruh a'zolarini yozishda xatolik bo'ldi.")

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
    group_title = event.chat.title or "Guruh"
    
    full_name = " ".join(filter(None, [user.first_name, user.last_name])).strip() or None
    user_data = {
        "id": user.id,
        "full_name": full_name,
        "username": user.username,
    }

    try:
        # A'zo qo'shildi
        if (old_status in (ChatMemberStatus.LEFT, ChatMemberStatus.KICKED) and 
            new_status in (ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR)):
            await _handle_member_join(user_data, group_id, group_title, event.date)
            
        # A'zo chiqdi/chiqarildi
        elif (old_status in (ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR) and 
              new_status in (ChatMemberStatus.LEFT, ChatMemberStatus.KICKED)):
            await _handle_member_leave(user_data, group_id, group_title, event, new_status)
            
    except Exception as e:
        logging.exception(f"handle_member_changes xatolik: {e}")
        await _send_error_to_admin("A'zo o'zgarishlarini qayta ishlashda xatolik")

async def _process_group_members(group_id: int):
    """Guruh a'zolarini yig'ish va bazaga yozish"""
    members = []
    async for user in telethon_client.iter_participants(group_id):
        if getattr(user, "bot", False):
            continue
        full_name = " ".join(filter(None, [user.first_name, user.last_name])).strip() or None
        members.append({
            "id": user.id,
            "username": user.username or None,
            "full_name": full_name
        })

    success_count = 0
    async with api_client as client:
        for i, m in enumerate(members, start=1):
            try:
                # Mavjud foydalanuvchini tekshirish
                existing_user = await client.get_user_full_info(m["id"])
                existing_groups = []
                
                if existing_user and existing_user.get("success") and existing_user.get("data"):
                    existing_groups = [g["group_id"] for g in existing_user["data"].get("register_groups", [])]
                
                all_groups = list(set(existing_groups + [group_id]))
                
                if existing_groups:
                    reg = await client.update_register(
                        telegram_id=m["id"],
                        username=m["username"],
                        fio=m["full_name"],
                        group_ids=all_groups
                    )
                else:
                    reg = await client.add_register(
                        telegram_id=m["id"],
                        group_ids=[group_id],
                        username=m["username"],
                        fio=m["full_name"],
                        is_active=False,
                        is_teacher=False
                    )
                
                if reg and not (isinstance(reg, dict) and reg.get("success") is False):
                    success_count += 1
                elif isinstance(reg, dict) and reg.get("success") is False:
                    # Agar user allaqachon mavjud bo'lsa, uni yangilashga harakat qiling
                    error_msg = reg.get("error", "")
                    if "already exists" in str(error_msg):
                        try:
                            reg = await client.update_register(
                                telegram_id=m["id"],
                                username=m["username"],
                                fio=m["full_name"],
                                group_ids=all_groups
                            )
                            if reg and not (isinstance(reg, dict) and reg.get("success") is False):
                                success_count += 1
                        except Exception as update_e:
                            logging.warning(f"Update register xatolik {m.get('id')}: {update_e}")
                    
            except Exception as e:
                logging.exception(f"Member register xatolik {m.get('id')}: {e}")

            if i % 15 == 0:
                await asyncio.sleep(0.1)

    info_text = f"✅ Guruhdan jami <b>{success_count}</b> ta a'zo bazaga yozildi."
    await _send_to_admins(info_text)

async def _handle_member_join(user_data: dict, group_id: int, group_title: str, event_date):
    """Yangi a'zo qo'shilganida ishlov berish"""
    # Adminlarga xabar
    member_text = (
        f"🟢 <b>Yangi a'zo qo'shildi!</b>\n\n"
        f"👤 <b>Ism:</b> {user_data['full_name'] or f"User {user_data['id']}"}\n"
        f"🆔 <b>User:</b> @{user_data['username'] or user_data['id']}\n"
        f"💬 <b>Guruh:</b> {group_title}\n"
        f"🆔 <b>Guruh ID:</b> {group_id}"
    )
    await _send_to_admins(member_text)
    
    # Foydalanuvchini bazaga qo'shish/yangilash
    async with api_client as client:
        existing_user = await client.get_user_full_info(user_data["id"])
        existing_groups = []
        
        if existing_user and existing_user.get("success") and existing_user.get("data"):
            existing_groups = [g["group_id"] for g in existing_user["data"].get("register_groups", [])]
        
        all_groups = list(set(existing_groups + [group_id]))
        
        if existing_groups:
            reg_result = await client.update_register(
                telegram_id=user_data["id"],
                username=user_data["username"],
                fio=user_data["full_name"],
                group_ids=all_groups
            )
        else:
            reg_result = await client.add_register(
                telegram_id=user_data["id"],
                group_ids=[group_id],
                username=user_data["username"],
                fio=user_data["full_name"],
                is_active=False,
                is_teacher=False
            )
        
        # Faoliyat yozuvi
        if reg_result and not (isinstance(reg_result, dict) and reg_result.get("success") is False):
            try:
                await client.add_member_activity(
                    telegram_id=user_data["id"],
                    group_id=group_id,
                    activity_type='join',
                    action_by='system',
                    activity_time=event_date.isoformat()
                )
            except Exception as e:
                logging.warning(f"Activity qo'shish xatolik: {e}")

async def _handle_member_leave(user_data: dict, group_id: int, group_title: str, event, leave_status):
    """A'zo chiqganida/chiqarilganida ishlov berish"""
    action = "chiqarildi" if leave_status == ChatMemberStatus.KICKED else "chiqdi"
    emoji = "🚫" if leave_status == ChatMemberStatus.KICKED else "🔴"
    
    # Kim action qilgan
    from_user = event.from_user
    admin_info = {}
    
    if from_user and from_user.id != user_data["id"]:
        by_whom = f"👨‍💼 <b>Kim:</b> {from_user.full_name or 'Noma\'lum'} (@{from_user.username or from_user.id})"
        admin_info = {
            "admin_telegram_id": from_user.id,
            "admin_name": from_user.full_name,
            "admin_username": from_user.username
        }
    else:
        by_whom = "📝 <b>Usul:</b> O'zi chiqdi"
    
    # Adminlarga xabar
    leave_text = (
        f"{emoji} <b>A'zo {action}!</b>\n\n"
        f"👤 <b>Ism:</b> {user_data['full_name'] or f"User {user_data['id']}"}\n"
        f"🆔 <b>User:</b> @{user_data['username'] or user_data['id']}\n"
        f"{by_whom}\n"
        f"💬 <b>Guruh:</b> {group_title}"
    )
    await _send_to_admins(leave_text)
    
    # Register jadvalidan guruhni o'chirish
    async with api_client as client:
        try:
            existing_user = await client.get_user_full_info(user_data["id"])
            
            if existing_user and existing_user.get("success") and existing_user.get("data"):
                existing_groups = [g["group_id"] for g in existing_user["data"].get("register_groups", [])]
                remaining_groups = [g for g in existing_groups if g != group_id]
                
                if remaining_groups != existing_groups:
                    await client.update_register(
                        telegram_id=user_data["id"],
                        username=user_data["username"],
                        fio=user_data["full_name"],
                        group_ids=remaining_groups
                    )
            
            # Faoliyat yozuvi
            await client.add_member_activity(
                telegram_id=user_data["id"],
                group_id=group_id,
                activity_type='leave' if leave_status == ChatMemberStatus.LEFT else 'kicked',
                action_by='self' if not admin_info else 'admin',
                activity_time=event.date.isoformat(),
                **admin_info
            )
            
        except Exception as e:
            logging.warning(f"Leave processing xatolik: {e}")

async def _send_to_admins(message: str):
    """Barcha adminlarga xabar yuborish"""
    try:
        async with api_client as client:
            admins_data = await client.get_all_admins()
            
        if not admins_data or not admins_data.get("success"):
            logging.error("Adminlar ro'yxatini olishda xatolik")
            return
        
        admin_ids = [admin["telegram_id"] for admin in admins_data.get("data", [])
                    if admin.get("telegram_id")]
        
        for admin_id in admin_ids:
            try:
                await bot.send_message(chat_id=admin_id, text=message, parse_mode="HTML")
            except Exception as e:
                logging.warning(f"Admin {admin_id} ga xabar yuborilmadi: {e}")
                
    except Exception as e:
        logging.error(f"Adminlarga xabar yuborishda xatolik: {e}")

async def _send_error_to_admin(error_message: str):
    """Birinchi adminga xato haqida xabar yuborish"""
    try:
        async with api_client as client:
            admins_data = await client.get_all_admins()
            
        if admins_data and admins_data.get("success") and admins_data.get("data"):
            first_admin = admins_data["data"][0]
            admin_id = first_admin.get("telegram_id")
            
            if admin_id:
                await bot.send_message(chat_id=admin_id, text=error_message, parse_mode="HTML")
                
    except Exception as e:
        logging.error(f"Admin ga xato xabarini yuborishda xatolik: {e}")