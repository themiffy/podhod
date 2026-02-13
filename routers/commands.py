from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command

from app.database_func import get_volume
from app.utils import pretty_print

import random

commands_router = Router(name=__name__)
MEMES = ('По пьяни', 'Этот нигер слишком жёсткий', 'Это плавность', 'Делает',
         'Мужчина', 'Эсса нигер', 'Пьяный 2', 'Недостаточно',
         'Так держать', 'В этом и смысл, бро...'
         )

@commands_router.message(Command('help'))
async def help_handler(message: Message):
    await message.answer(f'Психологическая помощь при алкоголизме доступна пациентам клиники «Зависимость 24» в Москве круглосуточно. Вызвать ее можно по телефону 8 (495) 182-66-66')

@commands_router.message(Command('stats'))
async def stats_handler(message: Message):
    report = ''
    if len(message.text.split()) > 1: # Индивидуальный отчёт
        sportsmen = message.text.split()[1].lower().capitalize()
        volume = await get_volume(sportsmen)
        report += f'Спортсмен {sportsmen} выпил {round(volume, 2)}л пива. {random.choice(MEMES)}'
    else: # Общий отчёт
        volume = await get_volume()
        report += f'Выпито {round(volume, 2)}л пива.'


    pretty_print(message)
    await message.answer(report)
#
# @commands_router.message(Command('top_report'))
# async def help_handler(message: Message):
#     await get_global_report()