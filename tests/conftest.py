import pytest
import core.database as db_module
import services.fetch_exchange_rates as fx_module


@pytest.fixture
def db_conn(tmp_path, monkeypatch):
    """Provides an initialized, isolated SQLite database connection for each test."""
    db_file = str(tmp_path / "test_portfolio.db")
    monkeypatch.setattr(db_module, "DB_FILE", db_file)
    monkeypatch.setattr(fx_module, "_historical_db_cache", None)
    db_module.init_db()
    conn = db_module.get_connection()
    yield conn
    conn.close()
