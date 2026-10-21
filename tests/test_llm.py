import asyncio
import unittest
from dataclasses import replace
from unittest.mock import AsyncMock, MagicMock

import aiohttp

from app.llm import StatsLLM, UNAVAILABLE_COMMENT
from app.llm_client import LLMError, OpenAICompatibleClient
from app.llm_config import LLMSettings


class SettingsTests(unittest.TestCase):
    def test_environment_overrides_file(self):
        settings = LLMSettings.from_mapping(
            {'LLM_MODEL': 'file-model', 'LLM_API_KEY': 'file-key'},
            {'LLM_MODEL': 'env-model', 'LLM_API_KEY': 'env-key', 'LLM_ENABLED': 'false'},
        )
        self.assertEqual(settings.model, 'env-model')
        self.assertEqual(settings.api_key, 'env-key')
        self.assertFalse(settings.enabled)
        self.assertNotIn('env-key', repr(settings))

    def test_deepseek_defaults_and_own_key(self):
        settings = LLMSettings.from_mapping({'DEEPSEEK_API_KEY': 'key'}, {})
        self.assertEqual(settings.model, 'deepseek-flash')
        self.assertEqual(settings.api_key, 'key')
        self.assertEqual(settings.base_url, 'https://api.deepseek.com')

    def test_other_provider_does_not_reuse_deepseek_key(self):
        settings = LLMSettings.from_mapping({
            'LLM_PROVIDER': 'openai-compatible',
            'LLM_BASE_URL': 'https://other.example/v1/',
            'LLM_MODEL': 'other-model', 'DEEPSEEK_API_KEY': 'private',
        }, {})
        self.assertEqual(settings.api_key, '')
        self.assertEqual(settings.base_url, 'https://other.example/v1')

    def test_invalid_settings_fail_explicitly(self):
        for values in (
            {'LLM_ENABLED': 'nope'}, {'LLM_PROVIDER': 'unknown'},
            {'LLM_PROVIDER': 'openai-compatible'}, {'LLM_MODEL': ''},
            {'LLM_BASE_URL': 'invalid'}, {'LLM_TEMPERATURE': 3},
            {'LLM_TIMEOUT_SECONDS': 0}, {'LLM_TIMEOUT_SECONDS': 'nan'},
            {'LLM_MAX_TOKENS': 0}, {'LLM_MAX_HISTORY_CHARS': -1},
        ):
            with self.subTest(values=values), self.assertRaises(ValueError):
                LLMSettings.from_mapping(values, {})


class ClientTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.settings = LLMSettings(api_key='test-key')
        self.response = MagicMock(status=200)
        self.response.json = AsyncMock(return_value={
            'choices': [{'message': {'content': '  Двигается!  '}, 'finish_reason': 'stop'}],
        })
        self.session = MagicMock()
        self.session.post.return_value.__aenter__ = AsyncMock(return_value=self.response)
        self.session.post.return_value.__aexit__ = AsyncMock(return_value=False)
        self.client = OpenAICompatibleClient(self.session, self.settings)

    async def test_deepseek_request_and_text_response(self):
        messages = [{'role': 'user', 'content': 'test'}]
        self.assertEqual(await self.client.complete(messages), 'Двигается!')
        args, kwargs = self.session.post.call_args
        self.assertEqual(args[0], 'https://api.deepseek.com/chat/completions')
        self.assertEqual(kwargs['headers']['Authorization'], 'Bearer test-key')
        self.assertEqual(kwargs['json']['messages'], messages)
        self.assertEqual(kwargs['json']['thinking'], {'type': 'disabled'})
        self.assertEqual(kwargs['json']['model'], 'deepseek-flash')
        self.assertEqual(kwargs['json']['max_tokens'], 1000)
        self.assertEqual(kwargs['timeout'].total, 45)
        self.assertFalse(kwargs['allow_redirects'])

    async def test_other_provider_uses_own_endpoint_without_thinking(self):
        settings = replace(self.settings, provider='openai-compatible',
                           base_url='https://other.example/v1/', model='other')
        await OpenAICompatibleClient(self.session, settings).complete([])
        args, kwargs = self.session.post.call_args
        self.assertEqual(args[0], 'https://other.example/v1/chat/completions')
        self.assertEqual(kwargs['json']['model'], 'other')
        self.assertNotIn('thinking', kwargs['json'])

    async def test_missing_key_never_sends_request(self):
        client = OpenAICompatibleClient(self.session, replace(self.settings, api_key=''))
        with self.assertRaises(LLMError):
            await client.complete([])
        self.session.post.assert_not_called()

    async def test_http_errors_are_sanitized(self):
        for status in (301, 401, 429, 500):
            self.response.status = status
            with self.subTest(status=status), self.assertRaisesRegex(LLMError, f'HTTP {status}'):
                await self.client.complete([])
        self.response.json.assert_not_awaited()

    async def test_transport_errors_are_normalized(self):
        for error in (asyncio.TimeoutError(), aiohttp.ClientConnectionError('secret'),
                      ValueError('private response')):
            self.session.post.return_value.__aenter__.side_effect = error
            with self.subTest(error=type(error)), self.assertRaises(LLMError) as caught:
                await self.client.complete([])
            self.assertNotIn('secret', str(caught.exception))
            self.assertNotIn('private', str(caught.exception))

    async def test_malformed_empty_and_truncated_responses(self):
        for data in (None, [], {}, {'choices': []}, {'choices': [None]},
                     {'choices': [{'message': {}}]},
                     {'choices': [{'message': {'content': None}}]},
                     {'choices': [{'message': {'content': '  '}}]},
                     {'choices': [{'message': {'content': ['text']}}]},
                     {'choices': [{'message': {'content': 'partial'}, 'finish_reason': 'length'}]}):
            self.response.json.return_value = data
            with self.subTest(data=data), self.assertRaises(LLMError):
                await self.client.complete([])

    async def test_invalid_json_body_is_normalized(self):
        self.response.json.side_effect = ValueError('private response body')
        with self.assertRaises(LLMError) as caught:
            await self.client.complete([])
        self.assertNotIn('private', str(caught.exception))

    async def test_cancellation_propagates(self):
        self.session.post.return_value.__aenter__.side_effect = asyncio.CancelledError()
        with self.assertRaises(asyncio.CancelledError):
            await self.client.complete([])


class ServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_both_reports_share_character_and_keep_history_out_of_system(self):
        client = MagicMock(complete=AsyncMock(return_value='Делает'))
        service = StatsLLM(LLMSettings(), client)
        for sportsmen in ('Миша', None):
            self.assertEqual(await service.generate('Всего 2л', 'UNTRUSTED HISTORY', sportsmen, 7), 'Делает')
            messages = client.complete.call_args.args[0]
            self.assertEqual([m['role'] for m in messages], ['system', 'user'])
            self.assertNotIn('UNTRUSTED HISTORY', messages[0]['content'])
            self.assertIn('UNTRUSTED HISTORY', messages[1]['content'])
            self.assertIn('Всего 2л', messages[1]['content'])
            if sportsmen:
                self.assertIn(sportsmen, messages[1]['content'])
            else:
                self.assertIn('все спортсмены', messages[1]['content'])

    async def test_failure_returns_comment_and_safe_log(self):
        client = MagicMock(complete=AsyncMock(side_effect=LLMError('HTTP 429')))
        with self.assertLogs('app.llm', level='WARNING') as logs:
            result = await StatsLLM(LLMSettings(), client).generate('report', 'private history')
        self.assertEqual(result, UNAVAILABLE_COMMENT)
        self.assertNotIn('private history', str(logs.output))

    async def test_disabled_skips_client(self):
        client = MagicMock(complete=AsyncMock())
        result = await StatsLLM(LLMSettings(enabled=False), client).generate('report', 'history')
        self.assertEqual(result, '')
        client.complete.assert_not_awaited()

    async def test_history_limit_preserves_recent_entries(self):
        client = MagicMock(complete=AsyncMock(return_value='ok'))
        service = StatsLLM(LLMSettings(max_history_chars=6), client)
        await service.generate('report', 'NEWESToldest')
        text = client.complete.call_args.args[0][1]['content']
        self.assertIn('NEWEST\n[История сокращена]', text)
        self.assertNotIn('oldest', text)

    async def test_empty_history_is_explicit(self):
        client = MagicMock(complete=AsyncMock(return_value='ok'))
        await StatsLLM(LLMSettings(), client).generate('report', '')
        self.assertIn('Подходов нет.', client.complete.call_args.args[0][1]['content'])
