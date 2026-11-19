import pytest
from routers.api_v1 import get_broker_summary_report
import services.fetch_exchange_rates as fx_module


def test_broker_summary_prefers_newer_per_broker_over_stale_consolidated(db_conn, monkeypatch):
    """Stale CONSOLIDATED cash rows must not overwrite newer per-broker daily_cash_report snapshots."""
    monkeypatch.setattr(fx_module, "get_exchange_rates", lambda: {"SGD": 1.0, "USD": 1.35, "CAD": 1.0})

    with db_conn:
        db_conn.execute("INSERT INTO portfolios (name, broker) VALUES ('Main IBKR', 'IBKR')")
        db_conn.execute("INSERT INTO portfolios (name, broker) VALUES ('MooMoo', 'MOOMOO')")
        db_conn.execute("INSERT INTO broker_capital_entries (date, broker, amount) VALUES ('2026-01-01', 'IBKR', 300000.0)")
        db_conn.execute("INSERT INTO broker_capital_entries (date, broker, amount) VALUES ('2026-01-01', 'MOOMOO', 5000.0)")
        # Legacy CONSOLIDATED snapshot from June 2026
        db_conn.execute(
            "INSERT INTO daily_cash_report (date, broker, liquidation_value, base_capital, total_stock_value, cash_on_hand) "
            "VALUES ('2026-06-26', 'CONSOLIDATED', 442495.02, 305000.0, 410000.0, 32495.02)"
        )
        # Newer per-broker snapshots from November 2026
        db_conn.execute(
            "INSERT INTO daily_cash_report (date, broker, liquidation_value, base_capital, total_stock_value, cash_on_hand) "
            "VALUES ('2026-11-18', 'IBKR', 395079.22, 300000.0, 380000.0, 15079.22)"
        )
        db_conn.execute(
            "INSERT INTO daily_cash_report (date, broker, liquidation_value, base_capital, total_stock_value, cash_on_hand) "
            "VALUES ('2026-11-16', 'MOOMOO', 5754.79, 5000.0, 4700.0, 1054.79)"
        )

    res = get_broker_summary_report(year=None, price_mode="closing")
    assert res["brokers"]["IBKR"]["liquidation_value_sgd"] == pytest.approx(395079.22)
    assert res["brokers"]["MOOMOO"]["liquidation_value_sgd"] == pytest.approx(5754.79)
    assert res["consolidated"]["liquidation_value_sgd"] == pytest.approx(400834.01)


def test_broker_summary_uses_consolidated_for_historical_year_when_newer(db_conn, monkeypatch):
    """Historical year-end CONSOLIDATED snapshot applies when it is newer than per-broker IBKR rows."""
    monkeypatch.setattr(fx_module, "get_exchange_rates", lambda: {"SGD": 1.0, "USD": 1.35, "CAD": 1.0})

    with db_conn:
        db_conn.execute("INSERT INTO portfolios (name, broker) VALUES ('Main IBKR', 'IBKR')")
        db_conn.execute("INSERT INTO broker_capital_entries (date, broker, amount) VALUES ('2025-01-01', 'IBKR', 250000.0)")
        db_conn.execute(
            "INSERT INTO daily_cash_report (date, broker, liquidation_value, base_capital, total_stock_value, cash_on_hand) "
            "VALUES ('2025-08-01', 'IBKR', 260000.0, 250000.0, 240000.0, 20000.0)"
        )
        db_conn.execute(
            "INSERT INTO daily_cash_report (date, broker, liquidation_value, base_capital, total_stock_value, cash_on_hand) "
            "VALUES ('2025-12-31', 'CONSOLIDATED', 310000.0, 250000.0, 290000.0, 20000.0)"
        )

    res = get_broker_summary_report(year=2025, price_mode="closing")
    assert res["brokers"]["IBKR"]["liquidation_value_sgd"] == pytest.approx(310000.0)
    assert res["consolidated"]["liquidation_value_sgd"] == pytest.approx(310000.0)
