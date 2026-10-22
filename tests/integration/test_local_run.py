"""Verify the manual runner's isolation and cleanup without contacting Telegram."""

from contextlib import closing
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import psycopg2

from scripts import run_local


class LocalRunTests(unittest.TestCase):
    def test_runner_uses_fresh_database_and_cleans_up_after_bot_failure(self):
        original_open = Path.open
        config = {'TOKEN': 'offline-test', 'DB_HOST': 'must-not-connect.example',
                  'DB_NAME': 'production', 'DB_USER': 'production', 'DB_PASS': 'unused'}
        socket_directories = []

        def open_config(path, *args, **kwargs):
            if path.name == 'env.local.json':
                return io.StringIO(json.dumps(config))
            if path.name == 'env.json':
                raise AssertionError('Must not read production config')
            return original_open(path, *args, **kwargs)

        async def inspect_database(local_config):
            self.assertEqual(local_config['DB_NAME'], 'podhod_test')
            self.assertEqual(local_config['DB_USER'], 'podhod_test')
            self.assertEqual(local_config['DB_PASS'], '')
            self.assertFalse(local_config['LLM_ENABLED'])
            socket_directories.append(Path(local_config['DB_HOST']))
            with closing(psycopg2.connect(
                host=local_config['DB_HOST'], port=local_config['DB_PORT'],
                dbname=local_config['DB_NAME'], user=local_config['DB_USER'],
            )) as connection:
                with connection.cursor() as cursor:
                    cursor.execute('SELECT count(*) FROM podhods')
                    self.assertEqual(cursor.fetchone(), (0,))
                    cursor.execute('SELECT count(*) FROM bot_answers')
                    self.assertEqual(cursor.fetchone(), (0,))
            raise RuntimeError('Simulated bot startup failure')

        with patch.object(Path, 'open', open_config), \
                patch.object(run_local, 'run_bot', inspect_database), \
                self.assertRaisesRegex(RuntimeError, 'Simulated bot startup failure'):
            run_local.main()

        self.assertEqual(len(socket_directories), 1)
        self.assertFalse(socket_directories[0].exists())
