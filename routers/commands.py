from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command

from app.database_func import get_volume, get_podhod_history
from app.utils import pretty_print
from app.llm import llm_generate_personal_stats, llm_generate_general_stats

import random

USE_LLM: bool = True

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
    period = 14
    if len(message.text.split()) > 1: # Индивидуальный отчёт
        sportsmen = message.text.split()[1].lower().capitalize()
        volume = await get_volume(sportsmen)
        volume_for_period = await get_volume(sportsmen, period)
        report += f'''Спортсмен {sportsmen} выпил {round(volume, 2)}л пива за всё время. 
А за отчётный период {period} дней он выпил {round(volume_for_period, 2)}л. {random.choice(MEMES)}
'''

        if USE_LLM:
            podhod_history = await get_podhod_history(sportsmen, period)
            dossier = f'{report}\n История последних подходов за {period} дней:\n {podhod_history}\n...'
            report += '\n\n' + llm_generate_personal_stats(sportsmen, dossier)


    else: # Общий отчёт
        volume = await get_volume()
        volume_for_period = await get_volume(depth=period)
        report += f'''Всего всеми выпито {round(volume, 2)}л пива.
А за отчётный период {period} дней вы выпили {round(volume_for_period, 2)}л.'''

        if USE_LLM:
            podhod_history = await get_podhod_history(sportsmen=None, depth=period)
            dossier = f'{report}\n История последних подходов за {period} дней:\n {podhod_history}\n...'
            report += '\n\n' + llm_generate_general_stats(dossier)

    pretty_print(message)
    await message.answer(report)
#
# @commands_router.message(Command('top_report'))
# async def help_handler(message: Message):
#     await get_global_report()