import logging
from aiogram import Router, Bot
from aiogram.types import Message

from app.utils import (is_podhod, extract_volumes,
                       extract_sportsmen, handle_volumes, pretty_print)
from app.database_func import add_podhod, edit_podhod, add_answer, get_answer
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
        await message.answer('Не указан спортсмен')
        return

    if len(sportsmen) > 1:
        await message.answer('Тут несколько спортсменов. Я не умею такое обрабатывать')
        return

    formated_sportsman: str = sportsmen[0][1:].capitalize()
    final_volume = handle_volumes(volumes)

    podhod_id = await add_podhod(user = formated_sportsman,
                              volume = final_volume,
                              message=text,
                              date=message.date,
                              tg_chat_id=message.chat.id,
                              tg_message_id=message.message_id)


    answer_message = await message.answer(f'Подход зарегистрирован!\nСпортсмен: {formated_sportsman}, объём: {round(final_volume, 2)}л')
    await add_answer(podhod_id=podhod_id, bot_message_id=answer_message.message_id, bot_chat_id=answer_message.chat.id)


@podhod_router.edited_message(HasText())
async def edited_message(message: Message, bot: Bot):
    pretty_print(message)

    text: str = message.text if message.text is not None else message.caption

    if not is_podhod(text): return

    answer_message_id, answer_chat_id = await get_answer(tg_message_id=message.message_id, tg_chat_id=message.chat.id)

    sportsmen = extract_sportsmen(text)
    volumes = extract_volumes(text)
    logging.info(f'\nMessage edited: Спортсмен(ы): {str(sportsmen)} \nОбъёмы: {str(volumes)}')

    if len(sportsmen) == 0:
        await bot.edit_message_text(text='Не указан спротсмен', chat_id=answer_chat_id, message_id=answer_message_id)
        return

    if len(sportsmen) > 1:
        await bot.edit_message_text(text='Тут несколько спортсменов. Я не умею такое обрабатывать', chat_id=answer_chat_id, message_id=answer_message_id)
        return

    formated_sportsman: str = sportsmen[0][1:].capitalize()
    final_volume = handle_volumes(volumes)


    await edit_podhod(user = formated_sportsman,
                volume = final_volume,
                message=text,
                date=message.date,
                tg_chat_id=message.chat.id,
                tg_message_id=message.message_id)

    await bot.edit_message_text(text=f'Подход обновлён!\nСпортсмен: {formated_sportsman}, объём: {round(final_volume, 2)}л',
                                chat_id=answer_chat_id, message_id=answer_message_id)