"""Async Chat Completions transport; no Telegram or report logic here."""

import asyncio
from typing import Protocol

import aiohttp

from app.llm_config import LLMSettings


class LLMError(Exception):
    """Safe diagnostic that contains no request or response body."""


class ChatClient(Protocol):
    async def complete(self, messages: list[dict[str, str]]) -> str:
        ...


class OpenAICompatibleClient:
    def __init__(self, session: aiohttp.ClientSession, settings: LLMSettings):
        self.session = session
        self.settings = settings

    async def complete(self, messages: list[dict[str, str]]) -> str:
        if not self.settings.api_key:
            raise LLMError('API key is not configured')
        payload = {
            'model': self.settings.model,
            'messages': messages,
            'temperature': self.settings.temperature,
            'max_tokens': self.settings.max_tokens,
            'stream': False,
        }
        if self.settings.provider == 'deepseek':
            # Short commentary does not need a reasoning budget.
            payload['thinking'] = {'type': 'disabled'}
        try:
            async with self.session.post(
                self.settings.base_url.rstrip('/') + '/chat/completions',
                headers={'Authorization': f'Bearer {self.settings.api_key}'},
                json=payload,
                timeout=aiohttp.ClientTimeout(total=self.settings.timeout_seconds),
                allow_redirects=False,
            ) as response:
                if response.status != 200:
                    raise LLMError(f'HTTP {response.status}')
                data = await response.json()
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError):
            raise LLMError('Network error, timeout or invalid JSON') from None

        try:
            choice = data['choices'][0]
            content = choice['message']['content']
            finish_reason = choice.get('finish_reason')
        except (KeyError, IndexError, TypeError, AttributeError):
            raise LLMError('Invalid completion response') from None
        if finish_reason not in (None, 'stop'):
            raise LLMError('Completion was interrupted or refused')
        if not isinstance(content, str) or not content.strip():
            raise LLMError('Completion contains no text')
        return content.strip()
