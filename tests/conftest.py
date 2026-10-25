"""Test fixtures. Every test runs against a fresh temporary database, never the user's finance data."""
import pytest

from finsight import database


@pytest.fixture(autouse=True)
def isolated_database(tmp_path):
    database.configure_database(f"sqlite:///{(tmp_path / 'test_finsight.db').as_posix()}")
    yield
