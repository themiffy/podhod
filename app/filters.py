from aiogram.filters import Filter
from aiogram.types import Message

class HasText(Filter):
    async def __call__(self, message: Message) -> bool:

        if message.sticker: return False
        if message.document: return False
        if message.audio: return False
        if message.voice: return False
        if message.video_note: return False

        return message.text is not None or message.caption is not None
