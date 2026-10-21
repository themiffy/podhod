"""Real aiogram dispatch and Telegram requests; only DB/LLM are replaced."""

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from app.llm import StatsLLM, UNAVAILABLE_COMMENT
from app.llm_client import LLMError
from app.llm_config import LLMSettings
from tests.support import make_dispatcher, make_update


class StatsCommandTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.volume = AsyncMock(side_effect=[12.5, 2.5])
        self.history = AsyncMock(return_value='#миша 2,5л')
        self.patches = [
            patch('routers.commands.get_volume', self.volume),
            patch('routers.commands.get_podhod_history', self.history),
        ]
        for replacement in self.patches:
            replacement.start()
            self.addCleanup(replacement.stop)
        self.dispatcher, self.bot, self.telegram = make_dispatcher()
        self.client = MagicMock(complete=AsyncMock(return_value='Это плавность'))

    async def asyncTearDown(self):
        await self.bot.session.close()

    async def dispatch(self, text, enabled=True):
        await self.dispatcher.feed_update(
            self.bot, make_update(text),
            llm=StatsLLM(LLMSettings(enabled=enabled), self.client),
        )
        self.assertEqual(len(self.telegram.calls), 1)
        method, request = self.telegram.calls[0]
        self.assertEqual(method, 'sendMessage')
        self.assertEqual(request['chat_id'], '-100123')
        self.assertIsNone(request['parse_mode'])
        return request['text']

    async def test_general_report_with_comment(self):
        report = await self.dispatch('/stats')
        self.assertIn('Всего всеми выпито 12.5л', report)
        self.assertIn('7 дней вы выпили 2.5л', report)
        self.assertIn('Это плавность', report)
        self.history.assert_awaited_once_with(sportsmen=None, depth=7)

    async def test_personal_report_with_comment(self):
        report = await self.dispatch('/stats МИША')
        self.assertIn('Спортсмен Миша выпил 12.5л', report)
        self.assertIn('Это плавность', report)
        self.history.assert_awaited_once_with(sportsmen='Миша', depth=7)
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
        self.history.assert_not_awaited()
        self.client.complete.assert_not_awaited()
        self.assertNotIn(UNAVAILABLE_COMMENT, report)
