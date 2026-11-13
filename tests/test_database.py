def test_connection_pragmas_and_wal_mode(db_conn):
    """Verify foreign_keys, busy_timeout, and WAL journal mode are enabled."""
    fk = db_conn.execute("PRAGMA foreign_keys;").fetchone()[0]
    busy = db_conn.execute("PRAGMA busy_timeout;").fetchone()[0]
    journal = db_conn.execute("PRAGMA journal_mode;").fetchone()[0]

    assert fk == 1
    assert busy == 5000
    assert str(journal).lower() == "wal"
