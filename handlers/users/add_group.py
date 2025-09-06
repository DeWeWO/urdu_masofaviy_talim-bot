import asyncio
import logging
from datetime import datetime
from aiogram import types, F, Router
from aiogram.filters import ChatMemberUpdatedFilter
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
    # Faqat guruh/superguruh
    if event.chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        return

    me = await bot.get_me()
    # Aynan bot guruhga qo'shilgan holatni tekshiramiz
    if event.new_chat_member.user.id != me.id:
        return

    # Oldin chiqib ketgan/kicked bo'lgan bo'lsa va endi member/admin bo'lsa
    if (
        event.old_chat_member.status in (ChatMemberStatus.LEFT, ChatMemberStatus.KICKED)
        and event.new_chat_member.status in (ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR)
    ):
        title = event.chat.title or "No title"
        group_id = event.chat.id
        admin_ids = ADMINS if isinstance(ADMINS, (list, tuple)) else [ADMINS]

        accept_text = f"🎉 Bot yangi guruhga qo'shildi!\n\n📋 Guruh: {title}\n🆔 ID: {group_id}"
        error_text  = "⚠️⚠️ Botni guruhga qo'shishda xatolik bo'ldi. Qaytadan urinib ko'ring"
        reg_error   = "⚠️⚠️ Guruh a'zolarini yozishda xatolik bo'ldi."

        try:
            # 1) Adminlarga xabar
            for admin_id in admin_ids:
                try:
                    await bot.send_message(chat_id=admin_id, text=accept_text)
                except Exception as e:
                    logging.warning(f"Admin {admin_id} ga xabar yuborilmadi: {e}")

            # 2) Guruhni backendga yuborish
            resp = await api_client.add_group(title, group_id)
            if not resp or (isinstance(resp, dict) and resp.get("success") is False):
                logging.error(f"Backendga guruhni yozishda xatolik: {resp}")
                if admin_ids:
                    await bot.send_message(chat_id=admin_ids[0], text=error_text)

            # 3) Telethon orqali a'zolarni yig'ish
            members = []
            async for user in telethon_client.iter_participants(group_id):
                # Botlarni va "deleted account"larni tashlab ketish ixtiyoriy
                if getattr(user, "bot", False):
                    continue
                full_name = " ".join(filter(None, [user.first_name, user.last_name])).strip() or None
                members.append({
                    "id": user.id,
                    "username": user.username or None,
                    "full_name": full_name
                })

            # 4) Har bir a'zoni backendga yozish (mavjud guruhlarni saqlab qolish bilan)
            success_count = 0
            for i, m in enumerate(members, start=1):
                try:
                    # ✅ YAXSHILASH: Avval foydalanuvchining mavjud guruhlarini tekshirish
                    existing_user = await api_client.get_user_full_info(m["id"])
                    existing_groups = []
                    
                    if existing_user and existing_user.get("success") and existing_user.get("data"):
                        existing_groups = [g["group_id"] for g in existing_user["data"].get("register_groups", [])]
                    
                    # Yangi guruhni mavjud guruhlarga qo'shish
                    all_groups = list(set(existing_groups + [group_id]))
                    
                    if existing_user and existing_user.get("success"):
                        # Mavjud foydalanuvchini yangilash
                        reg = await api_client.update_register(
                            telegram_id=m["id"],
                            username=m["username"],
                            fio=m["full_name"],
                            group_ids=all_groups
                        )
                    else:
                        # Yangi foydalanuvchi yaratish
                        reg = await api_client.add_register(
                            telegram_id=m["id"],
                            group_ids=[group_id],
                            username=m["username"],
                            fio=m["full_name"],
                            is_active=False,
                            is_teacher=False
                        )
                    
                    if reg is not None and not (isinstance(reg, dict) and reg.get("success") is False):
                        success_count += 1
                    else:
                        logging.warning(f"Foydalanuvchini yozishda xato: {m} | resp={reg}")
                        
                except Exception as e:
                    logging.exception(f"add_register failed for user_id={m.get('id')}: {e}")

                # Juda ko'p request bo'lsa serverni ezmaslik uchun biroz pauza
                if i % 15 == 0:  # Kamroq throttling
                    await asyncio.sleep(0.1)

            # 5) Yakuniy ma'lumot
            info_text = f"✅ Guruhdan jami <b>{success_count}</b> ta a'zo bazaga yozildi."
            for admin_id in admin_ids:
                try:
                    await bot.send_message(chat_id=admin_id, text=info_text)
                except Exception as e:
                    logging.warning(f"Admin {admin_id} ga preview yuborilmadi: {e}")

        except Exception as e:
            logging.exception(f"bot_added_to_group xatolik: {e}")
            if admin_ids:
                try:
                    await bot.send_message(chat_id=admin_ids[0], text=reg_error)
                except Exception:
                    pass


@router.chat_member()
async def handle_member_changes(event: types.ChatMemberUpdated):
    """Guruh a'zolari o'zgarishlarini kuzatish va boshqarish"""
    
    # Faqat guruh/superguruh
    if event.chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        return

    # Botning o'zini e'tiborsiz qoldirish
    me = await bot.get_me()
    if event.new_chat_member.user.id == me.id:
        return

    user = event.new_chat_member.user
    old_status = event.old_chat_member.status
    new_status = event.new_chat_member.status
    group_id = event.chat.id
    group_title = event.chat.title or "Guruh"
    
    # Foydalanuvchi ma'lumotlari
    full_name = " ".join(filter(None, [user.first_name, user.last_name])).strip() or None
    username = user.username
    
    user_data = {
        "id": user.id,
        "full_name": full_name,
        "username": username,
    }

    try:
        # GURUHGA QO'SHILDI
        if (old_status in (ChatMemberStatus.LEFT, ChatMemberStatus.KICKED) and 
            new_status in (ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR)):
            
            await _handle_member_join(user_data, group_id, group_title, event.date)
            
        # GURUHDAN CHIQDI/CHIQARILDI  
        elif (old_status in (ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR) and 
              new_status in (ChatMemberStatus.LEFT, ChatMemberStatus.KICKED)):
            
            await _handle_member_leave(user_data, group_id, group_title, event, new_status)
            
    except Exception as e:
        logging.exception(f"handle_member_changes xatolik: {e}")
        await _send_error_to_admin("A'zo o'zgarishlarini qayta ishlashda xatolik")


async def _handle_member_join(user_data: dict, group_id: int, group_title: str, event_date):
    """Yangi a'zo qo'shilganida ishlov berish"""
    
    # 1. Adminlarga xabar yuborish
    member_text = (
        f"🟢 <b>Yangi a'zo qo'shildi!</b>\n\n"
        f"👤 <b>Ism:</b> {user_data['full_name'] or f"User {user_data['id']}"}\n"
        f"🆔 <b>User:</b> @{user_data['username'] or user_data['id']}\n"
        f"💬 <b>Guruh:</b> {group_title}\n"
        f"🆔 <b>Guruh ID:</b> {group_id}"
    )
    await _send_to_admins(member_text)
    
    # 2. Mavjud foydalanuvchini tekshirish
    existing_user = await api_client.get_user_full_info(user_data["id"])
    existing_groups = []
    
    # API javobini to'g'ri tekshirish
    if existing_user and isinstance(existing_user, dict):
        # 404 xatolik normal holat - yangi user
        if existing_user.get("success") is False and "topilmadi" in existing_user.get("error", "").lower():
            logging.info(f"Yangi foydalanuvchi: {user_data['id']}")
        elif existing_user.get("success") and existing_user.get("data"):
            existing_groups = [g["group_id"] for g in existing_user["data"].get("register_groups", [])]
    
    # 3. Yangi guruhni qo'shish
    all_groups = list(set(existing_groups + [group_id]))
    
    # Mavjud foydalanuvchi bo'lsa yangilash, aks holda yaratish
    if existing_groups:
        reg_result = await api_client.update_register(
            telegram_id=user_data["id"],
            username=user_data["username"],
            fio=user_data["full_name"],
            group_ids=all_groups
        )
        logging.info(f"Foydalanuvchi yangilandi: {user_data['id']}")
    else:
        reg_result = await api_client.add_register(
            telegram_id=user_data["id"],
            group_ids=[group_id],
            username=user_data["username"],
            fio=user_data["full_name"],
            is_active=False,
            is_teacher=False
        )
        logging.info(f"Yangi foydalanuvchi yaratildi: {user_data['id']}")
    
    # 4. Register natijasini tekshirish
    # API muvaffaqiyatli bo'lsa data qaytaradi, xatolik bo'lsa success: false
    if reg_result and isinstance(reg_result, dict):
        # Agar data mavjud bo'lsa va telegram_id bor bo'lsa - muvaffaqiyat
        if reg_result.get("telegram_id") or reg_result.get("id"):
            logging.info(f"✅ User {user_data['id']} muvaffaqiyatli ro'yxatga olindi")
        elif reg_result.get("success") is False:
            logging.error(f"Register xatolik: {reg_result.get('error', 'Noma\'lum xatolik')}")
            await _send_error_to_admin("⚠️ Yangi a'zoni ro'yxatga olishda xatolik")
            return
    else:
        logging.error(f"Register javob noto'g'ri: {reg_result}")
        await _send_error_to_admin("⚠️ Register API dan noto'g'ri javob")
        return
    
    # 5. Faoliyat yozuvini qo'shish
    try:
        activity_result = await api_client.add_member_activity(
            telegram_id=user_data["id"],
            group_id=group_id,
            activity_type='join',
            action_by='system',
            activity_time=event_date.isoformat()
        )
        
        if activity_result and isinstance(activity_result, dict):
            if activity_result.get("success") is False:
                logging.warning(f"Faoliyat yozish xatolik: {activity_result.get('error')}")
            else:
                logging.info(f"✅ Faoliyat yozuvi qo'shildi: {user_data['id']}")
        
    except Exception as e:
        logging.warning(f"Activity qo'shishda xatolik: {e}")


async def _handle_member_leave(user_data: dict, group_id: int, group_title: str, event, leave_status):
    """A'zo chiqganida/chiqarilganida ishlov berish"""
    
    # Action aniqlash
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
    
    # 1. Adminlarga xabar
    leave_text = (
        f"{emoji} <b>A'zo {action}!</b>\n\n"
        f"👤 <b>Ism:</b> {user_data['full_name'] or f"User {user_data['id']}"}\n"
        f"🆔 <b>User:</b> @{user_data['username'] or user_data['id']}\n"
        f"{by_whom}\n"
        f"💬 <b>Guruh:</b> {group_title}"
    )
    await _send_to_admins(leave_text)
    
    # 2. Register jadvalidan guruhni o'chirish
    try:
        existing_user = await api_client.get_user_full_info(user_data["id"])
        
        if existing_user and existing_user.get("success") and existing_user.get("data"):
            existing_groups = [g["group_id"] for g in existing_user["data"].get("register_groups", [])]
            
            # Chiqib ketgan guruhni olib tashlash
            remaining_groups = [g for g in existing_groups if g != group_id]
            
            if remaining_groups != existing_groups:  # O'zgarish bo'lsa
                update_result = await api_client.update_register(
                    telegram_id=user_data["id"],
                    username=user_data["username"],
                    fio=user_data["full_name"],
                    group_ids=remaining_groups
                )
                
                if update_result and isinstance(update_result, dict):
                    if update_result.get("telegram_id") or update_result.get("id"):
                        logging.info(f"✅ User {user_data['id']} guruhlar ro'yxati yangilandi: {remaining_groups}")
                    elif update_result.get("success") is False:
                        logging.error(f"Register yangilash xatolik: {update_result.get('error')}")
                else:
                    logging.error(f"Register yangilash javob xatolik: {update_result}")
            else:
                logging.info(f"User {user_data['id']} uchun o'zgarish kerak emas")
        else:
            logging.warning(f"User {user_data['id']} register jadvalida topilmadi")
    
    except Exception as e:
        logging.warning(f"Register jadvalini yangilashda xatolik: {e}")
    
    # 3. Faoliyat yozuvini qo'shish
    try:
        activity_result = await api_client.add_member_activity(
            telegram_id=user_data["id"],
            group_id=group_id,
            activity_type='leave' if leave_status == ChatMemberStatus.LEFT else 'kicked',
            action_by='self' if not admin_info else 'admin',
            activity_time=event.date.isoformat(),
            **admin_info
        )
        
        if activity_result and isinstance(activity_result, dict):
            if activity_result.get("success") is False:
                logging.warning(f"Leave faoliyat xatolik: {activity_result.get('error')}")
            else:
                logging.info(f"✅ Leave faoliyat yozuvi qo'shildi: {user_data['id']}")
        
    except Exception as e:
        logging.warning(f"Leave activity qo'shishda xatolik: {e}")
    
    logging.info(f"{emoji} User {user_data['id']} {group_title} guruhidan {action}")


async def _send_to_admins(message: str):
    """Barcha adminlarga xabar yuborish"""
    admin_ids = ADMINS if isinstance(ADMINS, (list, tuple)) else [ADMINS]
    
    for admin_id in admin_ids:
        try:
            await bot.send_message(chat_id=admin_id, text=message, parse_mode="HTML")
        except Exception as e:
            logging.warning(f"Admin {admin_id} ga xabar yuborilmadi: {e}")


async def _send_error_to_admin(error_message: str):
    """Birinchi adminga xato haqida xabar yuborish"""
    admin_ids = ADMINS if isinstance(ADMINS, (list, tuple)) else [ADMINS]
    
    if admin_ids:
        try:
            await bot.send_message(chat_id=admin_ids[0], text=error_message, parse_mode="HTML")
        except Exception as e:
            logging.error(f"Admin ga xato xabarini yuborib bo'lmadi: {e}")