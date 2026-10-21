"""LLM configuration. Process environment takes precedence over env.json."""

import math
import os
from dataclasses import dataclass, field
from typing import Mapping, Any, Optional
from urllib.parse import urlsplit


@dataclass(frozen=True)
class LLMSettings:
    enabled: bool = True
    provider: str = 'deepseek'
    base_url: str = 'https://api.deepseek.com'
    model: str = 'deepseek-flash'
    api_key: str = field(default='', repr=False)
    temperature: float = 0.85
    max_tokens: int = 1000
    timeout_seconds: float = 45.0
    max_history_chars: int = 24000

    def __post_init__(self):
        if self.provider not in ('deepseek', 'openai-compatible'):
            raise ValueError('LLM_PROVIDER must be deepseek or openai-compatible')
        url = urlsplit(self.base_url)
        if url.scheme not in ('http', 'https') or not url.netloc or url.query or url.fragment:
            raise ValueError('LLM_BASE_URL must be an HTTP(S) API base URL')
        if not self.model.strip():
            raise ValueError('LLM_MODEL must not be empty')
        if not 0 <= self.temperature <= 2:
            raise ValueError('LLM_TEMPERATURE must be between 0 and 2')
        if self.max_tokens <= 0 or self.max_history_chars <= 0:
            raise ValueError('LLM_MAX_TOKENS and LLM_MAX_HISTORY_CHARS must be positive')
        if not math.isfinite(self.timeout_seconds) or self.timeout_seconds <= 0:
            raise ValueError('LLM_TIMEOUT_SECONDS must be finite and positive')

    @classmethod
    def from_mapping(cls, config: Mapping[str, Any],
                     environ: Optional[Mapping[str, str]] = None) -> 'LLMSettings':
        values = {**config, **(os.environ if environ is None else environ)}
        enabled = str(values.get('LLM_ENABLED', True)).lower()
        if enabled not in ('true', 'false', '1', '0'):
            raise ValueError('LLM_ENABLED must be true or false')
        provider = values.get('LLM_PROVIDER', 'deepseek')
        if provider == 'openai-compatible' and not all(
            values.get(key) for key in ('LLM_BASE_URL', 'LLM_MODEL')
        ):
            raise ValueError('Set LLM_BASE_URL and LLM_MODEL for openai-compatible')
        return cls(
            enabled=enabled in ('true', '1'),
            provider=provider,
            base_url=values.get('LLM_BASE_URL', cls.base_url).rstrip('/'),
            model=values.get('LLM_MODEL', cls.model),
            api_key=values.get('LLM_API_KEY') or (
                values.get('DEEPSEEK_API_KEY', '') if provider == 'deepseek' else ''
            ),
            temperature=float(values.get('LLM_TEMPERATURE', cls.temperature)),
            max_tokens=int(values.get('LLM_MAX_TOKENS', cls.max_tokens)),
            timeout_seconds=float(values.get('LLM_TIMEOUT_SECONDS', cls.timeout_seconds)),
            max_history_chars=int(values.get('LLM_MAX_HISTORY_CHARS', cls.max_history_chars)),
        )
