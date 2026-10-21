"""Provider-independent generation of statistics commentary."""

import logging
from typing import Optional

from app.llm_client import ChatClient, LLMError
from app.llm_config import LLMSettings
from app.llm_prompts import build_stats_messages

logger = logging.getLogger(__name__)
UNAVAILABLE_COMMENT = 'Комментарий рефери временно недоступен.'


class StatsLLM:
    def __init__(self, settings: LLMSettings, client: ChatClient):
        self.settings = settings
        self.client = client

    async def generate(self, report: str, history: str,
                       sportsmen: Optional[str] = None, period: int = 7) -> str:
        if not self.settings.enabled:
            return ''
        # History is newest first. Keep the most recent entries within the budget.
        if len(history) > self.settings.max_history_chars:
            history = history[:self.settings.max_history_chars] + '\n[История сокращена]'
        messages = build_stats_messages(report, history, sportsmen, period)
        try:
            return await self.client.complete(messages)
        except LLMError as exc:
            # Never log histories, generated text, credentials or provider bodies.
            logger.warning('LLM commentary unavailable: %s', exc)
            return UNAVAILABLE_COMMENT
