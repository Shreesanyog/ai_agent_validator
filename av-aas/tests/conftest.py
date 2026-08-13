import os
import sys
from pathlib import Path

# Ensure src/ is importable without an editable install.
SRC = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC))

# Force a predictable, external-service-free configuration for the whole
# test session, regardless of what's in a developer's local .env.
os.environ.setdefault("LLM_PROVIDER", "mock")
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_avaas.db")

import pytest  # noqa: E402


@pytest.fixture(autouse=True, scope="session")
def _cleanup_test_db():
    yield
    db_path = Path("./test_avaas.db")
    if db_path.exists():
        db_path.unlink()
