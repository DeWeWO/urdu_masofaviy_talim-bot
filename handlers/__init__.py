from aiogram import Router

from filters import ChatPrivateFilter


def setup_routers() -> Router:
    from .users import start, help, add_group, register, profile, forward
    from .errors import error_handler

    router = Router()

    # Agar kerak bo'lsa, o'z filteringizni o'rnating
    start.router.message.filter(ChatPrivateFilter(chat_type=["private"]))

    router.include_routers(start.router, help.router,
        add_group.router, register.router, profile.router, forward.router, error_handler.router
    )

    return router
