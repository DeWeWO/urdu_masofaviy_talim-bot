import asyncio
import logging
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
async def new_member_added(event: types.ChatMemberUpdated):
    # Faqat guruh/superguruh
    if event.chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        return

    me = await bot.get_me()
    # Agar bot emas, oddiy user bo'lsa
    if event.new_chat_member.user.id == me.id:
        return

    # Foydalanuvchi guruhga qo'shilgan (oldin LEFT/KICKED, endi MEMBER/ADMIN)
    if (
        event.old_chat_member.status in (ChatMemberStatus.LEFT, ChatMemberStatus.KICKED)
        and event.new_chat_member.status in (ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR)
    ):
        user = event.new_chat_member.user
        group_id = event.chat.id
        group_title = event.chat.title or "No title"

        full_name = " ".join(filter(None, [user.first_name, user.last_name])).strip() or None
        username = user.username or None

        user_data = {
            "id": user.id,
            "full_name": full_name,
            "username": username,
        }

        try:
            # 1) Adminlarga bildirish
            member_text = (
                f"{group_title} id: {group_id}\n"
                f"Guruhiga yangi a'zo qo'shildi!\n\n"
                f"User: @{user_data['username'] or user_data['id']}"
            )
            admin_ids = ADMINS if isinstance(ADMINS, (list, tuple)) else [ADMINS]
            for admin_id in admin_ids:
                try:
                    await bot.send_message(chat_id=admin_id, text=member_text)
                except Exception as e:
                    logging.warning(f"Admin {admin_id} ga yangi a'zo haqida xabar yuborilmadi: {e}")

            # 2) ✅ YAXSHILASH: Mavjud guruhlarni saqlab qolish
            existing_user = await api_client.get_user_full_info(user_data["id"])
            existing_groups = []
            
            if existing_user and existing_user.get("success") and existing_user.get("data"):
                existing_groups = [g["group_id"] for g in existing_user["data"].get("register_groups", [])]
                
            # Yangi guruhni mavjud guruhlarga qo'shish
            all_groups = list(set(existing_groups + [group_id]))
            
            if existing_user and existing_user.get("success"):
                # Mavjud foydalanuvchini yangilash
                reg = await api_client.update_register(
                    telegram_id=user_data["id"],
                    username=user_data["username"],
                    fio=user_data["full_name"],
                    group_ids=all_groups
                )
            else:
                # Yangi foydalanuvchi yaratish  
                reg = await api_client.add_register(
                    telegram_id=user_data["id"],
                    group_ids=[group_id],
                    username=user_data["username"],
                    fio=user_data["full_name"],
                    is_active=False,
                    is_teacher=False
                )

            if not reg or (isinstance(reg, dict) and reg.get("success") is False):
                logging.error(f"Backendga yangi a'zoni yozishda xatolik: {reg}")
                if admin_ids:
                    try:
                        await bot.send_message(
                            chat_id=admin_ids[0],
                            text="⚠️⚠️ Yangi a'zoni yozishda xatolik bo'ldi."
                        )
                    except Exception:
                        pass
            else:
                logging.info(f"✅ User {user_data['id']} successfully added/updated with groups {all_groups}")

        except Exception as e:
            logging.exception(f"new_member_added xatolik: {e}")
            admin_ids = ADMINS if isinstance(ADMINS, (list, tuple)) else [ADMINS]
            if admin_ids:
                try:
                    await bot.send_message(
                        chat_id=admin_ids[0],
                        text="⚠️⚠️ Yangi a'zoni qayta ishlashda xatolik bo'ldi."
                    )
                except Exception:
                    pass


@router.chat_member()
async def member_left_group(event: types.ChatMemberUpdated):
    """Foydalanuvchi guruhdan chiqib ketganda guruh ro'yxatini yangilash"""
    # Faqat guruh/superguruh
    if event.chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        return

    me = await bot.get_me()
    # Bot bo'lmasligi kerak
    if event.new_chat_member.user.id == me.id:
        return

    # Foydalanuvchi guruhdan chiqib ketgan (oldin MEMBER/ADMIN, endi LEFT/KICKED)
    if (
        event.old_chat_member.status in (ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR)
        and event.new_chat_member.status in (ChatMemberStatus.LEFT, ChatMemberStatus.KICKED)
    ):
        user = event.new_chat_member.user
        group_id = event.chat.id
        group_title = event.chat.title or "No title"

        try:
            # Foydalanuvchining mavjud guruhlarini olish
            existing_user = await api_client.get_user_full_info(user.id)
            
            if existing_user and existing_user.get("success") and existing_user.get("data"):
                existing_groups = [g["group_id"] for g in existing_user["data"].get("register_groups", [])]
                
                # Chiqib ketgan guruhni ro'yxatdan olib tashlash
                updated_groups = [g for g in existing_groups if g != group_id]
                
                if len(updated_groups) != len(existing_groups):
                    # Guruhlar ro'yxatini yangilash
                    reg = await api_client.update_register(
                        telegram_id=user.id,
                        group_ids=updated_groups
                    )
                    
                    if reg:
                        logging.info(f"✅ User {user.id} removed from group {group_id}")
                        # Admin'ga xabar
                        admin_ids = ADMINS if isinstance(ADMINS, (list, tuple)) else [ADMINS]
                        member_left_text = (
                            f"📤 {group_title} (ID: {group_id})\n"
                            f"guruhidan a'zo chiqib ketdi!\n\n"
                            f"User: @{user.username or user.id}"
                        )
                        for admin_id in admin_ids:
                            try:
                                await bot.send_message(chat_id=admin_id, text=member_left_text)
                            except Exception as e:
                                logging.warning(f"Admin {admin_id} ga xabar yuborilmadi: {e}")
                    
        except Exception as e:
            logging.exception(f"member_left_group xatolik: {e}")