__all__ = ('main_router', 'commands_router')

from routers.podhod_router import podhod_router
from routers.commands import commands_router
from aiogram import Router

main_router = Router(name=__name__)
main_router.include_router(commands_router)
main_router.include_router(podhod_router)

