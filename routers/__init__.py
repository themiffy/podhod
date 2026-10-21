__all__ = ('create_router',)

from routers.podhod_router import create_podhod_router
from routers.commands import create_commands_router
from aiogram import Router

def create_router() -> Router:
    router = Router(name=__name__)
    router.include_router(create_commands_router())
    router.include_router(create_podhod_router())
    return router

