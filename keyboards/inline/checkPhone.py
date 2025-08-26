from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.filters.callback_data import CallbackData


class PhoneCheckCallback(CallbackData, prefix='phonecheck'):
    is_actual: bool

def phone_check_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text='✔ Ha bu mening asosiy raqamim', callback_data=PhoneCheckCallback(is_actual=True))
    builder.button(text="❌ Yo'q bu asosiy raqamim emas", callback_data=PhoneCheckCallback(is_actual=False))
    builder.adjust(1)
    return builder.as_markup()
