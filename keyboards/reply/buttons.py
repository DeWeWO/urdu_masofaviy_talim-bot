from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

def register_markup():
    return ReplyKeyboardMarkup(resize_keyboard=True, keyboard=[
        [
            KeyboardButton(text="👤 Ro'yxatdan o'tish")
        ]
    ])

def add_group():
    murkup = ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="👥 Guruhga qo'shish")]
    ], resize_keyboard=True, one_time_keyboard=False)
    return murkup