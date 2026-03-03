import re
from aiogram.types import Message, Chat, User

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

def pretty_print(message: Message, depth: int = 0):
    """Этот нигер слишком сумасшедший"""
    space: str = '  '
    print(f'{space*depth}{type(message)}:')
    for field in message:
        if field[1]:
            if isinstance(field[1], (Chat, User,)):
                pretty_print(field[1], depth+1)
            else:
                print(f'{space*depth*2}{field[0]}: {field[1]}')

async def answer_long(message: Message, text: str) -> None:

    MESSAGE_MAX_LENGTH: int = 4000

    if len(text) < MESSAGE_MAX_LENGTH: await message.answer(text)
    else:
        print(f'Encountered long message: {len(text)=}')
        for i in range(MESSAGE_MAX_LENGTH,len(text), MESSAGE_MAX_LENGTH):
            print()
            await message.answer(text[i-MESSAGE_MAX_LENGTH : i])