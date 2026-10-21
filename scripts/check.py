"""Local checks; --integration starts and stops a temporary local PostgreSQL."""

import argparse
import ast
from contextlib import contextmanager
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]


def run(*args, extra_env=None):
    subprocess.run(args, cwd=ROOT, check=True,
                   env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1', **(extra_env or {})})


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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--integration', action='store_true', help='Run scenarios on temporary local PostgreSQL')
    args = parser.parse_args()
    for folder in ('app', 'routers', 'tests', 'scripts'):
        for path in (ROOT / folder).rglob('*.py'):
            ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
    ast.parse((ROOT / 'main.py').read_text(encoding='utf-8'), filename='main.py')
    run(sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-v')
    if args.integration:
        with local_postgres() as dsn:
            run(sys.executable, '-m', 'unittest', 'discover', '-s', 'tests/integration', '-v',
                extra_env={'PODHOD_TEST_DATABASE_URL': dsn})
    run('git', 'diff', '--check')
    print('All requested checks passed.', flush=True)


if __name__ == '__main__':
    main()
