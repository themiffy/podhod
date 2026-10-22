import re
from typing import Optional
from aiogram.types import Message, ReplyParameters

PODHOD_MARK = '#подход'

def is_podhod(text: str) -> bool:
    return PODHOD_MARK in text.lower()

def extract_volumes(text: str) -> list:
    volume_pattern: str = r' ?\d+[\.|,]?\d*?[л|Л] ?'
    volumes: list = [vol.strip() for vol in re.findall(volume_pattern, text)]
    return volumes

def extract_sportsmen(text: str) -> list:
    sportsmen_pattern: str = r'#\w+'
    hashtags: list = [tag for tag in re.findall(sportsmen_pattern, text.lower()) if tag != PODHOD_MARK]
    return hashtags

def handle_volumes(vols: list[str]) -> float:

    if len(vols) == 0: return 0 # объём не найден

    vols = [float(vol[:-1].replace(',', '.')) for vol in vols]
    return sum(vols)

async def answer_long(message: Message, text: str, *, reply_to_message_id: Optional[int] = None) -> None:

    MESSAGE_MAX_LENGTH: int = 4000

    for start in range(0, len(text), MESSAGE_MAX_LENGTH):
        reply = ({'reply_parameters': ReplyParameters(message_id=reply_to_message_id,
                                                     allow_sending_without_reply=True)}
                 if reply_to_message_id is not None else {})
        await message.answer(text[start:start + MESSAGE_MAX_LENGTH], parse_mode=None, **reply)
