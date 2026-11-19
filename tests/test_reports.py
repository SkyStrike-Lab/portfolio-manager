import pytest
from routers.api_v1 import get_broker_summary_report
from core.performance_calculator import get_performance_report_data
from services.performance_report_service import build_chart_data
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


def test_performance_report_cross_year_chart_and_per_broker_cutoff(db_conn):
    """Combined Net Worth keeps 2024-2026 history and builds cross-year weekly/monthly/yearly series, while per-broker cash starts 2026-06-29."""
    db_path = db_conn.execute("PRAGMA database_list;").fetchone()[2]

    with db_conn:
        db_conn.execute("INSERT INTO portfolios (name, broker) VALUES ('Main IBKR', 'IBKR')")
        db_conn.execute("INSERT INTO broker_capital_entries (date, broker, amount) VALUES ('2024-12-01', 'IBKR', 50000.0)")
        db_conn.execute("INSERT INTO broker_capital_entries (date, broker, amount) VALUES ('2025-12-01', 'IBKR', 150000.0)")
        # 2024 IBKR row (preserved in Combined Net Worth, excluded from per-broker tab)
        db_conn.execute(
            "INSERT INTO daily_cash_report (date, broker, liquidation_value, base_capital, total_stock_value, cash_on_hand) "
            "VALUES ('2024-12-31', 'IBKR', 55000.0, 50000.0, 55000.0, 0.0)"
        )
        # 2025 CONSOLIDATED row (preserved in Combined Net Worth)
        db_conn.execute(
            "INSERT INTO daily_cash_report (date, broker, liquidation_value, base_capital, total_stock_value, cash_on_hand) "
            "VALUES ('2025-12-31', 'CONSOLIDATED', 220000.0, 200000.0, 210000.0, 10000.0)"
        )
        # 1H 2026 CONSOLIDATED row
        db_conn.execute(
            "INSERT INTO daily_cash_report (date, broker, liquidation_value, base_capital, total_stock_value, cash_on_hand) "
            "VALUES ('2026-06-26', 'CONSOLIDATED', 230000.0, 200000.0, 220000.0, 10000.0)"
        )
        # 2H 2026 per-broker row (starts 2026-06-29+)
        db_conn.execute(
            "INSERT INTO daily_cash_report (date, broker, liquidation_value, base_capital, total_stock_value, cash_on_hand) "
            "VALUES ('2026-07-10', 'IBKR', 240000.0, 200000.0, 225000.0, 15000.0)"
        )

    report = get_performance_report_data(db_path)
    # Combined Net Worth retains 2024, 2025, and 2026
    assert "2024" in report["cash_data"]
    assert "2025" in report["cash_data"]
    assert "2026" in report["cash_data"]
    assert report["cash_data"]["2025"][12]["base_capital_gains"] == pytest.approx(20000.0)

    # Per-broker cash starts from 2026-06-29+ only
    assert "2024" not in report["broker_cash_data"].get("IBKR", {})
    assert "2025" not in report["broker_cash_data"].get("IBKR", {})
    assert 7 in report["broker_cash_data"]["IBKR"]["2026"]

    chart = build_chart_data(
        report["years"],
        report["cash_data"],
        report["portfolio_data"],
        broker_cash_data=report["broker_cash_data"],
        daily_cash_series=report["daily_cash_series"],
        daily_broker_cash_series=report["daily_broker_series"],
    )
    cy = chart["cash_cross_year"]
    assert cy["yearly"]["dates"] == ["2024", "2025", "2026"]
    assert cy["yearly"]["values"] == [5000.0, 20000.0, 40000.0]
    assert cy["yearly"]["pcts"] == [10.0, 10.0, 20.0]
    assert len(cy["monthly"]["dates"]) == 4
    assert len(cy["weekly"]["dates"]) == 4

