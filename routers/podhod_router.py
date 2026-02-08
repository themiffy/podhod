import logging
from aiogram import Router
from aiogram.types import Message

from app.utils import (is_podhod, extract_volumes,
                       extract_sportsmen, handle_volumes, pretty_print)
from app.database_func import add_podhod
from app.filters import HasText

podhod_router = Router(name=__name__)

@podhod_router.message(HasText())
async def any_message(message: Message):

    pretty_print(message)

    # Текст сообщения без картинки и с картинкой передаётся в разных полях (((
    text: str = message.text if message.text is not None else message.caption

    if not is_podhod(text): return

    sportsmen = extract_sportsmen(text)
    volumes = extract_volumes(text)

    logging.info(f'\nСпортсмен(ы): {str(sportsmen)} \nОбъёмы: {str(volumes)}')

    if len(sportsmen) == 0:
        await message.answer('Не указан спротсмен')
        return

    if len(sportsmen) > 1:
        await message.answer('Тут несколько спортсменов. Я не умею такое обрабатывать')
        return

    formated_sportsman: str = sportsmen[0][1:].capitalize()
    final_volume = handle_volumes(volumes)

    status = await add_podhod(user = formated_sportsman, volume = final_volume, message=text, date=message.date)


    await message.answer(f'Подход зарегистрирован!\nСпортсмен: {formated_sportsman}, объём: {round(final_volume, 2)}л')
