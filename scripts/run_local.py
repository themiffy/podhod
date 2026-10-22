"""Run the test bot against a fresh local database; stop both on Ctrl+C."""

import asyncio
from contextlib import closing
import json
from pathlib import Path

import psycopg2
from psycopg2.extensions import parse_dsn

from main import main as run_bot
from scripts.local_db import local_postgres


def main():
    root = Path(__file__).resolve().parents[1]
    with (root / 'env.local.json').open(encoding='utf-8') as file:
        config = json.load(file)
    with local_postgres() as dsn:
        params = parse_dsn(dsn)
        with closing(psycopg2.connect(dsn)) as connection:
            with connection, connection.cursor() as cursor:
                cursor.execute((root / 'db/schema.sql').read_text(encoding='utf-8'))
        # Database parameters always come from our temporary local cluster.
        config.update(DB_HOST=params['host'], DB_PORT=int(params['port']),
                      DB_NAME=params['dbname'], DB_USER=params['user'], DB_PASS='')
        config.setdefault('LLM_ENABLED', False)
        try:
            asyncio.run(run_bot(config))
        except KeyboardInterrupt:
            pass


if __name__ == '__main__':
    main()
