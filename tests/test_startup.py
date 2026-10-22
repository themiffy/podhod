import importlib
import io
import json
import runpy
import sys
from pathlib import Path
import unittest
from unittest.mock import AsyncMock, MagicMock, mock_open, patch

from app.llm_config import LLMSettings


class StartupTests(unittest.TestCase):
    def test_legacy_launcher_arguments_do_not_prevent_startup(self):
        path = Path(__file__).resolve().parents[1] / 'main.py'
        for arguments in ([], ['>', 'log.log'], ['> log.log']):
            with self.subTest(arguments=arguments), \
                    patch.object(sys, 'argv', ['main.py', *arguments]), \
                    patch('builtins.open', side_effect=AssertionError('Must not read production config')), \
                    patch('asyncio.run', side_effect=lambda coroutine: coroutine.close()) as start:
                runpy.run_path(str(path), run_name='__main__')
            start.assert_called_once()

    def test_old_local_flag_cannot_fall_through_to_production_startup(self):
        path = Path(__file__).resolve().parents[1] / 'main.py'
        with patch.object(sys, 'argv', ['main.py', '--local']), \
                patch('sys.stderr', new_callable=io.StringIO), \
                patch('builtins.open', side_effect=AssertionError('Must not read production config')), \
                self.assertRaises(SystemExit) as caught:
            runpy.run_path(str(path), run_name='__main__')
        self.assertEqual(caught.exception.code, 2)

    def test_import_does_not_open_config_or_connect_to_services(self):
        with patch('builtins.open', side_effect=AssertionError('Unexpected config read')), \
                patch('psycopg2.pool.ThreadedConnectionPool', side_effect=AssertionError('Unexpected DB connection')), \
                patch('aiogram.Bot.__init__', side_effect=AssertionError('Unexpected bot creation')):
            import main
            importlib.reload(main)


class LifecycleTests(unittest.IsolatedAsyncioTestCase):
    async def test_report_cooldown_comes_from_config_or_environment(self):
        import main
        for environment, expected in (({}, 75), ({'REPORT_COOLDOWN_SECONDS': '42'}, 42)):
            bot = MagicMock(session=MagicMock(close=AsyncMock()))
            dispatcher = MagicMock(start_polling=AsyncMock())
            config = {'TOKEN': 'offline', 'DB_HOST': 'localhost', 'DB_NAME': 'podhod_test',
                      'DB_USER': 'test', 'DB_PASS': '', 'REPORT_COOLDOWN_SECONDS': 75}
            with self.subTest(environment=environment), \
                    patch.dict(main.os.environ, environment, clear=True), \
                    patch.object(main, 'Bot', return_value=bot), \
                    patch.object(main, 'Dispatcher', return_value=dispatcher) as create_dispatcher, \
                    patch.object(main, 'init_db'), patch.object(main, 'close_db'), \
                    patch.object(main, 'setup_bot_commands', new_callable=AsyncMock):
                await main.main(config)
            self.assertEqual(create_dispatcher.call_args.kwargs['report_limit'].cooldown_seconds, expected)

    async def test_invalid_cooldown_fails_before_opening_connections(self):
        import main
        for value in (0, -1, 1.5, True, None, '', 'invalid', 'nan'):
            with self.subTest(value=value), patch.dict(main.os.environ, {}, clear=True), \
                    patch.object(main, 'Bot') as bot, patch.object(main, 'init_db') as database, \
                    self.assertRaisesRegex(ValueError, 'REPORT_COOLDOWN_SECONDS'):
                await main.main({'REPORT_COOLDOWN_SECONDS': value})
            bot.assert_not_called()
            database.assert_not_called()

    async def test_polling_receives_llm_and_resources_are_closed(self):
        import main
        bot = MagicMock(session=MagicMock(close=AsyncMock()))
        dispatcher = MagicMock(start_polling=AsyncMock())
        config = {'TOKEN': 'test', 'DB_HOST': 'localhost', 'DB_NAME': 'podhod_test',
                  'DB_USER': 'test', 'DB_PASS': 'test'}
        with patch('builtins.open', mock_open(read_data=json.dumps(config))), \
                patch.object(main, 'Bot', return_value=bot), \
                patch.object(main, 'Dispatcher', return_value=dispatcher), \
                patch.object(main, 'init_db') as initialize, \
                patch.object(main, 'close_db') as close, \
                patch.object(main, 'setup_bot_commands', new_callable=AsyncMock), \
                patch.object(main.LLMSettings, 'from_mapping', return_value=LLMSettings()):
            await main.main()
        initialize.assert_called_once_with(host='localhost', port=5432,
                                           dbname='podhod_test', user='test', password='test')
        dispatcher.start_polling.assert_awaited_once()
        llm = dispatcher.start_polling.call_args.kwargs['llm']
        self.assertTrue(llm.client.session.closed)
        close.assert_called_once()
        bot.session.close.assert_awaited_once()

    async def test_explicit_local_config_never_reads_production_file(self):
        import main
        bot = MagicMock(session=MagicMock(close=AsyncMock()))
        dispatcher = MagicMock(start_polling=AsyncMock())
        config = {'TOKEN': 'local-test', 'DB_HOST': '/tmp/local-test', 'DB_PORT': 55439,
                  'DB_NAME': 'podhod_test', 'DB_USER': 'podhod_test', 'DB_PASS': '',
                  'LLM_ENABLED': False}
        with patch('builtins.open', side_effect=AssertionError('Must not read env.json')), \
                patch.object(main, 'Bot', return_value=bot), \
                patch.object(main, 'Dispatcher', return_value=dispatcher), \
                patch.object(main, 'init_db') as initialize, \
                patch.object(main, 'close_db'), \
                patch.object(main, 'setup_bot_commands', new_callable=AsyncMock), \
                patch.object(main.LLMSettings, 'from_mapping', return_value=LLMSettings(enabled=False)):
            await main.main(config)
        initialize.assert_called_once_with(host='/tmp/local-test', port=55439,
                                           dbname='podhod_test', user='podhod_test', password='')
        self.assertFalse(dispatcher.start_polling.call_args.kwargs['llm'].settings.enabled)
