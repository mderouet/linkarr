import logging

import pytest


@pytest.fixture(autouse=True)
def _disable_tmdb(monkeypatch):
    """Disable TMDb lookups and reset cache between tests."""
    import organize

    monkeypatch.setenv("TMDB_API_KEY", "")
    organize._tmdb_cache.clear()


@pytest.fixture(autouse=True)
def _disable_logging():
    """Prevent log file creation during tests."""
    logging.disable(logging.CRITICAL)
    yield
    logging.disable(logging.NOTSET)
