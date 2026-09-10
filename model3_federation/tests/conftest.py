"""
Pytest configuration and fixtures for Model 3 Federation tests.
"""

from __future__ import annotations

import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Ensure repo root and model1-registry are on sys.path
REPO_ROOT = Path(__file__).resolve().parents[2]
MODEL1_ROOT = REPO_ROOT / "model1-registry"
MODEL3_ROOT = REPO_ROOT / "model3_federation"

for p in (str(REPO_ROOT), str(MODEL1_ROOT), str(MODEL3_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

# Inject model1_config shim if missing
if "model1_config" not in sys.modules:
    shim = types.ModuleType("model1_config")
    shim.REDIS_URL = "redis://localhost:6379"
    sys.modules["model1_config"] = shim


@pytest.fixture
def mock_db_session():
    """Mock SQLAlchemy database session for API testing."""
    session = MagicMock()
    session.execute.return_value.fetchall.return_value = []
    session.execute.return_value.fetchone.return_value = None
    return session


@pytest.fixture
def mock_db_factory(mock_db_session):
    """Factory returning a mock DB session context."""
    class Factory:
        def __call__(self):
            return mock_db_session
    return Factory()
