from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder

def register_markup():
    return ReplyKeyboardMarkup(resize_keyboard=True, keyboard=[
        [
            KeyboardButton(text="👤 Ro'yxatdan o'tish")
        ]
    ])

def share_contact():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📞 Kontaktni ulashish", request_contact=True)]
        ], resize_keyboard=True, one_time_keyboard=False
    )
    

def add_group():
    murkup = ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="👥 Guruhga qo'shish")]
    ], resize_keyboard=True, one_time_keyboard=False)
    return murkup