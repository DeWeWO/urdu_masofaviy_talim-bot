from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder

def register_markup():
    return ReplyKeyboardMarkup(resize_keyboard=True, keyboard=[
        [
            KeyboardButton(text="👤 Ro'yxatdan o'tish")
        ]
    ])


phone = ReplyKeyboardBuilder()
phone.add(KeyboardButton(text="📞 Kontaktni ulashish", request_contact=True))
phone.adjust(1)



def add_group():
    murkup = ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="👥 Guruhga qo'shish")]
    ], resize_keyboard=True, one_time_keyboard=False)
    return murkup