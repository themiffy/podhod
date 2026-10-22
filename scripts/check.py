"""Local checks; --integration starts and stops a temporary local PostgreSQL."""

import argparse
import ast
import os
from pathlib import Path
import subprocess
import sys

from scripts.local_db import local_postgres


ROOT = Path(__file__).resolve().parents[1]


def run(*args, extra_env=None):
    subprocess.run(args, cwd=ROOT, check=True,
                   env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1', **(extra_env or {})})


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
