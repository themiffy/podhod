import logging
from aiogram import Router, Bot
from aiogram.types import Message

from app.utils import (is_podhod, extract_volumes,
                       extract_sportsmen, handle_volumes)
from app.database_func import add_podhod, edit_podhod, add_answer, get_answer
from app.filters import HasText

async def any_message(message: Message):

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


async def edited_message(message: Message, bot: Bot):
    text: str = message.text if message.text is not None else message.caption

    if not is_podhod(text): return

    answer = await get_answer(tg_message_id=message.message_id, tg_chat_id=message.chat.id)
    if answer is None:
        # For example, a message predates the bot or was originally rejected.
        return
    answer_message_id, answer_chat_id = answer

    sportsmen = extract_sportsmen(text)
    volumes = extract_volumes(text)
    logging.info(f'\nMessage edited: Спортсмен(ы): {str(sportsmen)} \nОбъёмы: {str(volumes)}')

    if len(sportsmen) == 0:
        await bot.edit_message_text(text='Не указан спротсмен! Подход не изменён', chat_id=answer_chat_id, message_id=answer_message_id)
        return

    if len(sportsmen) > 1:
        await bot.edit_message_text(text='Тут несколько спортсменов. Я не умею такое обрабатывать, подход не изменён', chat_id=answer_chat_id, message_id=answer_message_id)
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


def create_podhod_router() -> Router:
    router = Router(name=__name__)
    router.message.register(any_message, HasText())
    router.edited_message.register(edited_message, HasText())
    return router
