"""Build statistics reports without depending on Telegram handlers."""

import random
from typing import Optional

from app.database_func import get_volume, get_podhod_history
from app.llm import StatsLLM


MEMES = ('По пьяни', 'Этот нигер слишком жёсткий', 'Это плавность', 'Делает',
         'Мужчина', 'Эсса нигер', 'Пьяный 2', 'Недостаточно',
         'Так держать', 'В этом и смысл, бро...'
         )


async def build_stats_report(llm: StatsLLM, sportsmen: Optional[str] = None) -> str:
    report = ''
    period = 7
    if sportsmen: # Индивидуальный отчёт
        volume = await get_volume(sportsmen)
        volume_for_period = await get_volume(sportsmen, period)
        report += f'''Спортсмен {sportsmen} выпил {round(volume, 2)}л пива за всё время. 
А за отчётный период {period} дней он выпил {round(volume_for_period, 2)}л. {random.choice(MEMES)}
'''

    else: # Общий отчёт
        volume = await get_volume()
        volume_for_period = await get_volume(depth=period)
        report += f'''Всего всеми выпито {round(volume, 2)}л пива.
А за отчётный период {period} дней вы выпили {round(volume_for_period, 2)}л.'''

    if llm.settings.enabled:
        history = await get_podhod_history(sportsmen=sportsmen, depth=period)
        comment = await llm.generate(report, history, sportsmen, period)
        if comment:
            report += '\n\n' + comment

    return report
