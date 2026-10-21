import importlib
import json
import unittest
from unittest.mock import AsyncMock, MagicMock, mock_open, patch

from app.llm_config import LLMSettings


class StartupTests(unittest.TestCase):
    def test_import_does_not_open_config_or_connect_to_services(self):
        with patch('builtins.open', side_effect=AssertionError('Unexpected config read')), \
                patch('psycopg2.pool.ThreadedConnectionPool', side_effect=AssertionError('Unexpected DB connection')), \
                patch('aiogram.Bot.__init__', side_effect=AssertionError('Unexpected bot creation')):
            import main
            importlib.reload(main)


class LifecycleTests(unittest.IsolatedAsyncioTestCase):
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
