from aiogram.fsm.state import StatesGroup, State

class RegisterState(StatesGroup):
    fio = State()
    pnfl = State()
    tg_tel = State()
    tel = State()
    parent_tel = State()
    address = State()
    confirm = State()