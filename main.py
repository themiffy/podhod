import argparse
import logging
import asyncio
import json
import aiohttp

from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand, ErrorEvent
from aiogram.fsm.storage.memory import MemoryStorage

from routers import create_router
from app.connection_pool import init_db, close_db
from app.llm import StatsLLM
from app.llm_client import OpenAICompatibleClient
from app.llm_config import LLMSettings


async def setup_bot_commands(bot: Bot):
    commands = [BotCommand(command="/help", description="Помощь"),
                BotCommand(command="/stats", description="Статистика")]
    await bot.set_my_commands(commands)

async def handle_error(event: ErrorEvent):
    exception = event.exception
    logging.error('Unhandled update error', exc_info=(
        type(exception), exception, exception.__traceback__
    ))

# Entry point
async def main(config=None) -> None:
    logging.basicConfig(level=logging.INFO)
    if config is None:
        with open('env.json', encoding='utf-8') as file:
            config = json.load(file)
    env = config
    settings = LLMSettings.from_mapping(env)
    bot = Bot(token=env['TOKEN'])
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(create_router())
    dp.errors.register(handle_error)
    try:
        init_db(host=env['DB_HOST'], port=env.get('DB_PORT', 5432),
                dbname=env['DB_NAME'], user=env['DB_USER'], password=env['DB_PASS'])
        async with aiohttp.ClientSession() as session:
            llm = StatsLLM(settings, OpenAICompatibleClient(session, settings))
            await setup_bot_commands(bot)
            await dp.start_polling(bot, llm=llm, close_bot_session=False)
    finally:
        close_db()
        await bot.session.close()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Подход Бот. Локальный запуск: python -m scripts.run_local',
        allow_abbrev=False,
    )
    parser.add_argument('--local', action='store_true', help=argparse.SUPPRESS)
    # Older launchers pass extra arguments (including literal shell redirects).
    # Preserve that startup behavior, but never mistake --local for production.
    args, _ = parser.parse_known_args()
    if args.local:
        parser.error('Для локального запуска используй: python -m scripts.run_local')
    asyncio.run(main())
