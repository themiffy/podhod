import logging
import asyncio
import json
import aiohttp

from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.handlers import ErrorHandler

from routers import main_router
from app.llm import StatsLLM
from app.llm_client import OpenAICompatibleClient
from app.llm_config import LLMSettings


logging.basicConfig(level=logging.INFO)

with open("env.json", "r") as file:
    env = json.load(file)

bot = Bot(token=env["TOKEN"])
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
dp.include_router(main_router)


async def setup_bot_commands(bot: Bot):
    commands = [BotCommand(command="/help", description="Помощь"),
                BotCommand(command="/stats", description="Статистика")]
    await bot.set_my_commands(commands)




@dp.errors()
class MyHandler(ErrorHandler):
    async def handle(self):
        logging.exception(
            "Cause unexpected exception %s: %s",
            self.exception_name,
            self.exception_message
        )

# Entry point
async def main() -> None:
    settings = LLMSettings.from_mapping(env)
    async with aiohttp.ClientSession() as session:
        llm = StatsLLM(settings, OpenAICompatibleClient(session, settings))
        await setup_bot_commands(bot)
        await dp.start_polling(bot, llm=llm)

if __name__ == "__main__":
    asyncio.run(main())
