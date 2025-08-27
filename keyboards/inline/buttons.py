from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters.callback_data import CallbackData
from data.config import BOT


class ChechCall(CallbackData, prefix='check'):
    checks : bool

register_confirm = InlineKeyboardMarkup(inline_keyboard=[
    [
        InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=ChechCall(checks=True).pack()),
        InlineKeyboardButton(text="❌ Bekor qilish", callback_data=ChechCall(checks=False).pack())
    ]
])



inline_keyboard = [[
    InlineKeyboardButton(text="✅ Yes", callback_data='yes'),
    InlineKeyboardButton(text="❌ No", callback_data='no')
]]

are_you_sure_markup = InlineKeyboardMarkup(inline_keyboard=inline_keyboard)

inine_add_group = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="👥 Guruhga qo'shish", url=f"https://t.me/{BOT}?startgroup=true")]
    ]
)