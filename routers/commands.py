from hashlib import sha256
from typing import Optional

from aiogram import F, Router
from aiogram.types import (CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup,
                           Message, MessageEntity, ReplyParameters, User)
from aiogram.filters import Command

from app.database_func import get_sportsmen
from app.utils import answer_long
from app.llm import StatsLLM
from app.stats import build_stats_report
from app.report_limit import ReportRateLimit


async def help_handler(message: Message):
    await answer_long(message, f'Психологическая помощь при алкоголизме доступна пациентам клиники «Зависимость 24» в Москве круглосуточно. Вызвать ее можно по телефону 8 (495) 182-66-66')

async def stats_handler(message: Message, llm: StatsLLM, report_limit: ReportRateLimit):
    args = (message.text or '').split(maxsplit=1)
    if len(args) > 1:
        if not message.from_user or message.sender_chat:
            await message.reply('Чтобы заказать отчёт, отправь команду от своего имени.')
            return
        user = message.from_user
        retry = report_limit.acquire(user.id)
        if retry:
            await message.reply(cooldown_message(report_limit, user.id, retry))
            return
        success = False
        try:
            await send_stats(message, llm, user, message.message_id,
                             args[1].strip().lower().capitalize())
            success = True
        finally:
            report_limit.finish(user.id, success)
        return

    sportsmen = await get_sportsmen()
    rows = [[InlineKeyboardButton(text='Общая статистика', callback_data='stats:all')]]
    buttons = [InlineKeyboardButton(text=name, callback_data=sportsman_callback_data(name))
               for name in sportsmen]
    rows.extend(buttons[i:i + 2] for i in range(0, len(buttons), 2))
    await message.answer('Чью статистику показать?',
                         reply_markup=InlineKeyboardMarkup(inline_keyboard=rows), parse_mode=None,
                         reply_parameters=ReplyParameters(message_id=message.message_id,
                                                          allow_sending_without_reply=True))


def sportsman_callback_data(name: str) -> str:
    # Names can exceed Telegram's 64-byte limit. A deterministic key survives
    # restarts and edits to individual approaches without storing menu state.
    return 'stats:person:' + sha256(name.encode('utf-8')).hexdigest()[:32]


async def stats_callback(callback: CallbackQuery, llm: StatsLLM, report_limit: ReportRateLimit):
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
    user = callback.from_user
    retry = report_limit.acquire(user.id)
    if retry:
        await callback.answer(cooldown_message(report_limit, user.id, retry), show_alert=True)
        return
    success = False
    try:
        if data != 'stats:all':
            matches = [name for name in await get_sportsmen() if sportsman_callback_data(name) == data]
            if len(matches) != 1:
                await callback.answer('Спортсмен не найден. Вызови /stats заново.', show_alert=True)
                return
            sportsmen = matches[0]
        await callback.answer('Готовлю отчёт…')
        menu = callback.message
        original = menu.reply_to_message
        reply_id = (original.message_id if original and original.from_user
                    and original.from_user.id == user.id else menu.message_id)
        await send_stats(menu, llm, user, reply_id, sportsmen)
        success = True
    finally:
        report_limit.finish(user.id, success)


def cooldown_message(limit: ReportRateLimit, user_id: int, seconds: int) -> str:
    if user_id in limit.in_flight:
        return 'Твой отчёт уже готовится. Дождись ответа.'
    minutes, seconds = divmod(seconds, 60)
    return f'Пока нельзя заказать новый отчёт. Повтори через {minutes} мин {seconds} сек.'


async def send_stats(message: Message, llm: StatsLLM, user: User, reply_id: int,
                     sportsmen: Optional[str] = None):
    mention = MessageEntity(type='text_mention', offset=0,
                            length=len(user.full_name.encode('utf-16-le')) // 2, user=user)
    progress = await message.answer(
        f'{user.full_name}, готовлю отчёт…', entities=[mention], parse_mode=None,
        reply_parameters=ReplyParameters(message_id=reply_id, allow_sending_without_reply=True),
    )
    try:
        report = f'{user.full_name}, твой отчёт:\n\n' + await build_stats_report(llm, sportsmen)
        await progress.edit_text(report[:4000], entities=[mention], parse_mode=None)
        if len(report) > 4000:
            await answer_long(progress, report[4000:], reply_to_message_id=progress.message_id)
    except Exception:
        await progress.edit_text(f'{user.full_name}, не удалось подготовить отчёт. Попробуй ещё раз.',
                                 entities=[mention], parse_mode=None)
        raise


def create_commands_router() -> Router:
    router = Router(name=__name__)
    router.message.register(help_handler, Command('help'))
    router.message.register(stats_handler, Command('stats'))
    router.callback_query.register(stats_callback, F.data.startswith('stats:'))
    return router
