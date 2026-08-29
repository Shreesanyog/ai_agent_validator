"""Verify the Alembic migration produces the same schema the ORM expects.

This guards against models and migrations drifting apart — a real risk once
Alembic owns the schema in production instead of create_all.
"""
import os
import subprocess
import sqlite3
import sys
import pathlib


def test_alembic_upgrade_creates_all_orm_tables(tmp_path):
    backend = pathlib.Path(__file__).parent.parent
    db_file = tmp_path / 'migrate_test.db'
    env = dict(os.environ)
    env['DATABASE_URL'] = f'sqlite+aiosqlite:///{db_file}'
    env['ALLOW_PRIVATE_TARGETS'] = 'true'

    result = subprocess.run([sys.executable, '-m', 'alembic', 'upgrade', 'head'],
                            cwd=backend, env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr

    con = sqlite3.connect(db_file)
    tables = {r[0] for r in con.execute("select name from sqlite_master where type='table'")}
    con.close()

    # Every ORM table must exist after the migration.
    from app.db import Base
    import app.models  # noqa: F401
    orm_tables = set(Base.metadata.tables.keys())
    missing = orm_tables - tables
    assert not missing, f'Migration is missing tables the ORM defines: {missing}'
