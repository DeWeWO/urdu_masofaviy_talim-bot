from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder

def register_markup():
    return ReplyKeyboardMarkup(resize_keyboard=True, keyboard=[
        [KeyboardButton(text="📝 Registratsiya")],
    ])

def share_contact():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📞 Kontaktni ulashish", request_contact=True)]
        ], resize_keyboard=True, one_time_keyboard=False
    )
    

def add_group():
    murkup = ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="👥 Guruhga qo'shish")],
        [KeyboardButton(text="📝 Ma'lumotlarni yangilash")],
        [KeyboardButton(text="👤 Mening ma'lumotlarim")],
    ], resize_keyboard=True, one_time_keyboard=False)
    return murkup

def update_info_markup():
    """Ma'lumotlarni yangilash uchun klaviatura"""
    markup = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📝 Ma'lumotlarni yangilash")],
            [KeyboardButton(text="👤 Mening ma'lumotlarim")],
        ],
        resize_keyboard=True,
        one_time_keyboard=False
    )
    return markup
