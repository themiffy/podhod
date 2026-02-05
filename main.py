import logging
import asyncio
import json

from aiogram import Bot, Dispatcher
from aiogram.types import Message, BotCommand, CallbackQuery
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.handlers import ErrorHandler

from routers import main_router


logging.basicConfig(level=logging.INFO)

with open("env.json", "r") as file:
    env = json.load(file)

bot = Bot(token=env["TOKEN"])
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
dp.include_router(main_router)


@dp.message(CommandStart())
async def start_handler(message: Message, state: FSMContext):
    print(message)


async def setup_bot_commands(bot: Bot):
    commands = [BotCommand(command="/start", description="В начало")]
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
    await setup_bot_commands(bot)
    await dp.start_polling(bot, on_startup=setup_bot_commands)

if __name__ == "__main__":
    asyncio.run(main())