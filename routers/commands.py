from hashlib import sha256
from typing import Optional

from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from aiogram.filters import Command

from app.database_func import get_sportsmen
from app.utils import answer_long
from app.llm import StatsLLM
from app.stats import build_stats_report


async def help_handler(message: Message):
    await answer_long(message, f'Психологическая помощь при алкоголизме доступна пациентам клиники «Зависимость 24» в Москве круглосуточно. Вызвать ее можно по телефону 8 (495) 182-66-66')

async def stats_handler(message: Message, llm: StatsLLM):
    args = (message.text or '').split(maxsplit=1)
    if len(args) > 1:
        await send_stats(message, llm, args[1].strip().lower().capitalize())
        return

    sportsmen = await get_sportsmen()
    rows = [[InlineKeyboardButton(text='Общая статистика', callback_data='stats:all')]]
    buttons = [InlineKeyboardButton(text=name, callback_data=sportsman_callback_data(name))
               for name in sportsmen]
    rows.extend(buttons[i:i + 2] for i in range(0, len(buttons), 2))
    await message.answer('Чью статистику показать?',
                         reply_markup=InlineKeyboardMarkup(inline_keyboard=rows), parse_mode=None)


def sportsman_callback_data(name: str) -> str:
    # Names can exceed Telegram's 64-byte limit. A deterministic key survives
    # restarts and edits to individual approaches without storing menu state.
    return 'stats:person:' + sha256(name.encode('utf-8')).hexdigest()[:32]


async def stats_callback(callback: CallbackQuery, llm: StatsLLM):
    if not isinstance(callback.message, Message):
        await callback.answer('Меню недоступно. Вызови /stats заново.', show_alert=True)
        return

    sportsmen = None
    data = callback.data or ''
    if data != 'stats:all':
        prefix = 'stats:person:'
        key = data[len(prefix):] if data.startswith(prefix) else ''
        if len(key) != 32 or any(char not in '0123456789abcdef' for char in key):
            await callback.answer('Кнопка недействительна. Вызови /stats заново.', show_alert=True)
            return
        matches = [name for name in await get_sportsmen() if sportsman_callback_data(name) == data]
        if len(matches) != 1:
            await callback.answer('Спортсмен не найден. Вызови /stats заново.', show_alert=True)
            return
        sportsmen = matches[0]

    # Clear Telegram's button spinner before generating the LLM commentary.
    await callback.answer()
    await send_stats(callback.message, llm, sportsmen)


async def send_stats(message: Message, llm: StatsLLM, sportsmen: Optional[str] = None):
    await answer_long(message, await build_stats_report(llm, sportsmen))


def create_commands_router() -> Router:
    router = Router(name=__name__)
    router.message.register(help_handler, Command('help'))
    router.message.register(stats_handler, Command('stats'))
    router.callback_query.register(stats_callback, F.data.startswith('stats:'))
    return router
