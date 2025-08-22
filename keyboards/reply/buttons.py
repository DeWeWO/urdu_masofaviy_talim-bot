from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

def add_group():
    murkup = ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="👥 Guruhga qo'shish")]
    ], resize_keyboard=True, one_time_keyboard=False)
    return murkup