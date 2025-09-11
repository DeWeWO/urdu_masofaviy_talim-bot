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
                    error_msg = resp.get("error", "Noma'lum xatolik") if isinstance(resp, dict) else "API javob bermadi"
                    logging.error(f"Backendga guruhni yozishda xatolik: {error_msg}")
                    await _send_error_to_admin(f"⚠️ Botni guruhga qo'shishda xatolik bo'ldi: {error_msg}")
                    return
                else:
                    logging.info(f"Guruh {group_id} ({title}) muvaffaqiyatli bazaga qo'shildi")

            # A'zolarni yig'ish va yozish
            await _process_group_members(group_id)

        except Exception as e:
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
        await _send_error_to_admin("A'zo o'zgarishlarini qayta ishlashda xatolik")

async def _process_group_members(group_id: int):
    """Guruh a'zolarini yig'ish va bazaga yozish"""
    try:
        members = []
        
        # A'zolarni yig'ish
        async for user in telethon_client.iter_participants(group_id):
            if getattr(user, "bot", False):
                continue
            
            full_name = " ".join(filter(None, [user.first_name, user.last_name])).strip() or None
            members.append({
                "id": user.id,
                "username": user.username or None,
                "full_name": full_name
            })

        
        if not members:
            await _send_to_admins("⚠️ Guruhda hech qanday a'zo topilmadi yoki barcha a'zolar botlar.")
            return

        success_count = 0
        failed_count = 0
        
        async with api_client as client:
            for i, member in enumerate(members, start=1):
                try:                    
                    # Har doim foydalanuvchini add_register bilan qo'shamiz
                    # Chunki bir foydalanuvchi bir nechta guruhda bo'lishi mumkin
                    try:
                        result = await client.add_register(
                            telegram_id=member["id"],
                            group_ids=[group_id],
                            username=member["username"],
                            fio=member["full_name"],
                            is_active=False,
                            is_teacher=False
                        )                        
                    except Exception as add_error:
                        result = None
                    
                    # Natijani tekshirish
                    if result:
                        # Muvaffaqiyatli qo'shildi
                        success_count += 1
                        
                    elif result is None:
                        # API None qaytardi, ehtimol "already exists" xatoligi
                        
                        try:
                            # Mavjud guruhlarni olamiz
                            existing_user = await client.get_user_full_info(member["id"])
                            
                            if existing_user and existing_user.get("success") and existing_user.get("data"):
                                existing_groups = [g["group_id"] for g in existing_user["data"].get("register_groups", [])]
                                
                                # Agar bu guruh allaqachon mavjud bo'lsa
                                if group_id in existing_groups:
                                    success_count += 1
                                else:
                                    # Yangi guruhni qo'shib update qilamiz
                                    all_groups = list(set(existing_groups + [group_id]))
                                    
                                    update_result = await client.update_register(
                                        telegram_id=member["id"],
                                        username=member["username"],
                                        fio=member["full_name"],
                                        group_ids=all_groups
                                    )
                                                                        
                                    if update_result and not (isinstance(update_result, dict) and update_result.get("success") is False):
                                        success_count += 1
                                    else:
                                        failed_count += 1
                            else:
                                failed_count += 1
                                
                        except Exception as update_error:
                            failed_count += 1
                    else:
                        # result False yoki boshqa qiymat
                        failed_count += 1
                    
                except Exception as e:
                    failed_count += 1

                # Har 10 ta foydalanuvchidan keyin biroz kutish
                if i % 10 == 0:
                    await asyncio.sleep(0.2)

        # Natija haqida xabar
        info_text = (
            f"📊 <b>Guruh a'zolari qayta ishlandi:</b>\n\n"
            f"✅ <b>Muvaffaqiyatli:</b> {success_count} ta\n"
            f"❌ <b>Xatolik:</b> {failed_count} ta\n"
            f"📋 <b>Jami a'zolar:</b> {len(members)} ta"
        )
        
        if failed_count > 0:
            info_text += f"\n\n⚠️ <b>Eslatma:</b> Ba'zi a'zolarni qo'shishda muammolar bo'ldi. Loglarni tekshiring."
        
        await _send_to_admins(info_text)
        
    except Exception as e:
        await _send_error_to_admin(f"⚠️ Guruh a'zolarini qayta ishlashda jiddiy xatolik: {str(e)}")

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
        
        # Yangi guruhni qo'shish
        all_groups = list(set(existing_groups + [group_id]))
        
        if existing_user and existing_user.get("success") and existing_user.get("data"):
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
    
    # Register jadvalidan guruhni o'chirish va faoliyat yozuvi
    async with api_client as client:
        try:
            existing_user = await client.get_user_full_info(user_data["id"])
            
            if existing_user and existing_user.get("success") and existing_user.get("data"):
                existing_groups = [g["group_id"] for g in existing_user["data"].get("register_groups", [])]
                # Faqat chiqgan guruhni o'chirish
                remaining_groups = [g for g in existing_groups if g != group_id]
                
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
    admin_ids = ADMINS if isinstance(ADMINS, (list, tuple)) else [ADMINS]
    
    async with api_client as client:
        for admin_id in admin_ids:
            try:
                admin_data = await client.check_admin(admin_id)
                if admin_data and admin_data.get("is_admin"):
                    await bot.send_message(chat_id=admin_id, text=message, parse_mode="HTML")
            except Exception as e:
                logging.warning(f"Admin {admin_id} ga xabar yuborilmadi: {e}")

async def _send_error_to_admin(error_message: str):
    """Birinchi adminga xato haqida xabar yuborish"""
    admin_ids = ADMINS if isinstance(ADMINS, (list, tuple)) else [ADMINS]
    
    async with api_client as client:
        for admin_id in admin_ids:
            try:
                admin_data = await client.check_admin(admin_id)
                if admin_data and admin_data.get("is_admin"):
                    await bot.send_message(chat_id=admin_id, text=error_message, parse_mode="HTML")
                    break
            except Exception as e:
                logging.warning(f"Admin {admin_id} ga xato xabari yuborilmadi: {e}")