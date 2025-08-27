from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.filters.callback_data import CallbackData


class PhoneCheckCallback(CallbackData, prefix='phonecheck'):
    is_actual: bool

def phone_check_kb_simple():
    builder = InlineKeyboardBuilder()
    builder.button(text='✔ Ha bu mening asosiy raqamim', callback_data='phone_check_yes')
    builder.button(text="❌ Yo'q bu asosiy raqamim emas", callback_data='phone_check_no')
    builder.adjust(1)
    return builder.as_markup()