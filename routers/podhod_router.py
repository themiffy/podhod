import logging
from aiogram import Router
from aiogram.types import Message

from app.utils import is_podhod, extract_volume, extract_sportsmen
from app.database_func import add_podhod

podhod_router = Router(name=__name__)

@podhod_router.message()
async def any_message(message: Message):

    result = f' Is podhod: {is_podhod(message.text)}'
    sportsmen = extract_sportsmen(message.text)
    volumes = extract_volume(message.text)
    if is_podhod(message.text):
        result += f'\nСпортсмен(ы): {str(sportsmen)} \nОбъёмы: {str(volumes)}'

    await message.answer(result)
    status = await add_podhod(user = sportsmen[0], volume= volumes[0], message=message.text)
    await message.answer(f'added to DB: {status}')
