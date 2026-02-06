import logging
import asyncio
import json

from aiogram import Bot, Dispatcher
from aiogram.types import Message, BotCommand
from aiogram.filters import Command
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


@dp.message(Command('help'))
async def help_handler(message: Message):
    await message.answer(f'Психологическая помощь при алкоголизме доступна пациентам клиники «Зависимость 24» в Москве круглосуточно. Вызвать ее можно по телефону 8 (495) 182-66-66')


async def setup_bot_commands(bot: Bot):
    commands = [BotCommand(command="/help", description="Помощь")]
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