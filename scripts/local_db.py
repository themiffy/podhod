"""Temporary local PostgreSQL shared by integration tests and manual bot runs."""

from contextlib import contextmanager
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


@contextmanager
def local_postgres():
    pg_ctl = shutil.which('pg_ctl')
    pg_bin = Path(os.environ.get('PG_BIN') or (
        str(Path(pg_ctl).parent) if pg_ctl else
        '/Applications/Postgres.app/Contents/Versions/latest/bin'
    ))
    for name in ('initdb', 'pg_ctl', 'createdb', 'postgres'):
        if not os.access(pg_bin / name, os.X_OK):
            raise SystemExit('Local PostgreSQL not found. Set PG_BIN to its bin directory.')

    def pg(name, *args):
        result = subprocess.run([str(pg_bin / name), *args], text=True,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        if result.returncode:
            raise RuntimeError(f'{name} failed:\n{result.stdout}')
        return result.stdout.strip()

    print(pg('postgres', '--version'), flush=True)
    # Short path keeps Unix socket names within the OS limit. No TCP listener.
    root = Path(tempfile.mkdtemp(prefix='podhod-pg-', dir='/tmp'))
    data = root / 'data'
    try:
        pg('initdb', '-D', str(data), '-A', 'trust', '-U', 'podhod_test',
           '--no-locale', '--encoding=UTF8')
        pg('pg_ctl', '-D', str(data), '-l', str(root / 'postgres.log'),
           '-o', f"-k {root} -h '' -p 55439 -F", '-w', 'start')
        pg('createdb', '-h', str(root), '-p', '55439', '-U', 'podhod_test', 'podhod_test')
        yield f'dbname=podhod_test user=podhod_test host={root} port=55439'
    finally:
        if (data / 'postmaster.pid').exists():
            # If shutdown fails, raise and keep the directory for diagnosis.
            pg('pg_ctl', '-D', str(data), '-m', 'fast', '-w', 'stop')
            print('Temporary PostgreSQL stopped.', flush=True)
        shutil.rmtree(root)
