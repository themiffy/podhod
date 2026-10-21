"""Exercise aiogram dispatch and dependency injection without external services."""

import runpy
import sys
import unittest
from pathlib import Path
from types import ModuleType
from unittest.mock import AsyncMock, MagicMock, patch

from aiogram import Bot, Dispatcher
from aiogram.types import Update

from app.llm import StatsLLM, UNAVAILABLE_COMMENT
from app.llm_client import LLMError
from app.llm_config import LLMSettings


class StatsCommandTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        # Load the real command router with only its database boundary replaced.
        # This avoids the legacy import-time connection pool and env.json read.
        self.database = ModuleType('app.database_func')
        self.database.get_volume = AsyncMock(side_effect=[12.5, 2.5])
        self.database.get_podhod_history = AsyncMock(return_value='#миша 2,5л')
        path = Path(__file__).resolve().parents[1] / 'routers' / 'commands.py'
        with patch.dict(sys.modules, {'app.database_func': self.database}):
            module = runpy.run_path(str(path))
        self.send = AsyncMock()
        self.globals_patch = patch.dict(module['stats_handler'].__globals__, {
            'answer_long': self.send, 'pretty_print': MagicMock(),
        })
        self.globals_patch.start()
        self.dispatcher = Dispatcher()
        self.dispatcher.include_router(module['commands_router'])
        self.bot = Bot(token='123456:TEST_TOKEN_FOR_OFFLINE_TESTS')
        self.client = MagicMock(complete=AsyncMock(return_value='Это плавность'))

    async def asyncTearDown(self):
        self.globals_patch.stop()
        await self.bot.session.close()

    async def dispatch(self, text, enabled=True):
        update = Update.model_validate({
            'update_id': 1,
            'message': {
                'message_id': 1, 'date': 1700000000,
                'chat': {'id': 123, 'type': 'private'},
                'from': {'id': 456, 'is_bot': False, 'first_name': 'Test'},
                'text': text,
            },
        })
        await self.dispatcher.feed_update(
            self.bot, update,
            llm=StatsLLM(LLMSettings(enabled=enabled), self.client),
        )
        self.send.assert_awaited_once()
        return self.send.call_args.args[1]

    async def test_general_report_with_comment(self):
        report = await self.dispatch('/stats')
        self.assertIn('Всего всеми выпито 12.5л', report)
        self.assertIn('7 дней вы выпили 2.5л', report)
        self.assertIn('Это плавность', report)
        self.database.get_podhod_history.assert_awaited_once_with(sportsmen=None, depth=7)

    async def test_personal_report_with_comment(self):
        report = await self.dispatch('/stats МИША')
        self.assertIn('Спортсмен Миша выпил 12.5л', report)
        self.assertIn('Это плавность', report)
        self.database.get_podhod_history.assert_awaited_once_with(sportsmen='Миша', depth=7)
        self.assertIn('Миша', self.client.complete.call_args.args[0][1]['content'])

    async def test_api_error_preserves_numeric_report(self):
        self.client.complete.side_effect = LLMError('HTTP 500')
        with self.assertLogs('app.llm', level='WARNING'):
            report = await self.dispatch('/stats')
        self.assertIn('Всего всеми выпито 12.5л', report)
        self.assertIn(UNAVAILABLE_COMMENT, report)

    async def test_disabled_llm_skips_history_and_api(self):
        report = await self.dispatch('/stats', enabled=False)
        self.assertIn('Всего всеми выпито 12.5л', report)
        self.database.get_podhod_history.assert_not_awaited()
        self.client.complete.assert_not_awaited()
        self.assertNotIn(UNAVAILABLE_COMMENT, report)
