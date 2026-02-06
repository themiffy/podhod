from aiogram.filters import Filter
from aiogram.types import Message



class HasText(Filter):


    def __init__(self) -> None:
        pass

    async def __call__(self, message: Message) -> bool:

        if message.sticker: return False
        if message.document: return False
        if message.audio: return False # Вот тут возможно нужно хэндлить
        if message.voice: return False
        if message.video_note: return False

        return True