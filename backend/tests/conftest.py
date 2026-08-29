"""Test bootstrap.

Two things are forced before the app is imported:
  * ALLOW_PRIVATE_TARGETS — the SSRF guard blocks loopback by default (correctly);
    the E2E suite runs a mock agent on 127.0.0.1, so it is enabled for tests only,
    via the environment, never by weakening the guard itself.
  * DATABASE_URL — a dedicated throwaway SQLite file so tests never read or write
    a developer's real avaas.db, and each session starts from a clean schema.
"""
import os
import pathlib

_TEST_DB = pathlib.Path(__file__).parent / 'avaas_test.db'
if _TEST_DB.exists():
    _TEST_DB.unlink()

os.environ['ALLOW_PRIVATE_TARGETS'] = 'true'
os.environ['DATABASE_URL'] = f'sqlite+aiosqlite:///{_TEST_DB}'
os.environ.setdefault('USE_DEEPEVAL', 'false')

from app.core.config import settings  # noqa: E402

settings.cache_clear()


def pytest_sessionfinish(session, exitstatus):
    if _TEST_DB.exists():
        _TEST_DB.unlink()
