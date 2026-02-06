import re

PODHOD_MARK = '#подход'

def is_podhod(text: str) -> bool:
    return PODHOD_MARK in text.lower()

def extract_volumes(text: str) -> list:
    volume_pattern: str = r' ?\d+\.?\d*?л ?'
    volumes: list = [vol.strip() for vol in re.findall(volume_pattern, text)]
    return volumes

def extract_sportsmen(text: str) -> list:
    sportsmen_pattern: str = r'#\w+'
    hashtags: list = [tag for tag in re.findall(sportsmen_pattern, text.lower()) if tag != PODHOD_MARK]
    return hashtags

def handle_volumes(vols: list[str]) -> float:

    if len(vols) == 0: return 0 # объём не найден

    vols = [float(vol[:-1]) for vol in vols]
    return sum(vols)