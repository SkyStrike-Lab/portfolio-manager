from datetime import datetime
import pytest
from core.calculations import calculate_holdings, get_portfolio_summary


def _seed_portfolio_and_ticker(conn, portfolio_name="Test Portfolio", symbol="AAPL", currency="USD"):
    cur = conn.cursor()
    cur.execute("INSERT INTO portfolios (name, classification, broker) VALUES (?, 'Growth', 'IBKR')", (portfolio_name,))
    pid = cur.lastrowid
    cur.execute("INSERT INTO tickers (symbol, friendly_name, underlying) VALUES (?, ?, ?)", (symbol, symbol, symbol))
    tid = cur.lastrowid
    conn.commit()
    return pid, tid


def _seed_fx(conn, date_str, currency, rate):
    conn.execute(
        "INSERT OR REPLACE INTO exchange_rates (date, currency, rate, last_updated) VALUES (?, ?, ?, 'test')",
        (date_str, currency, rate),
    )
    conn.commit()


def test_weighted_avg_cost_and_partial_sell_fx(db_conn):
    """Verify weighted avg cost across multiple BUYs and proportional FX-aware realized P&L on partial SELL."""
    pid, tid = _seed_portfolio_and_ticker(db_conn, symbol="MSFT", currency="USD")
    _seed_fx(db_conn, "2026-01-10", "USD", 1.30)
    _seed_fx(db_conn, "2026-02-10", "USD", 1.40)
    _seed_fx(db_conn, "2026-03-10", "USD", 1.35)

    with db_conn:
        # Buy 10 @ 100 (rate 1.30 -> cost_sgd = 1300)
        db_conn.execute(
            "INSERT INTO transactions (portfolio_id, ticker_id, date, action, price, quantity, currency) VALUES (?, ?, '2026-01-10', 'BUY', 100.0, 10.0, 'USD')",
            (pid, tid),
        )
        # Buy 10 @ 200 (rate 1.40 -> cost_sgd = 2800)
        db_conn.execute(
            "INSERT INTO transactions (portfolio_id, ticker_id, date, action, price, quantity, currency) VALUES (?, ?, '2026-02-10', 'BUY', 200.0, 10.0, 'USD')",
            (pid, tid),
        )
        # Sell 10 @ 250 (rate 1.35 -> proceeds_native = 2500, proceeds_sgd = 3375)
        # Proportional 50% of each chunk: cost_native = 500 + 1000 = 1500; cost_sgd = 650 + 1400 = 2050
        # Realized P&L native = 2500 - 1500 = 1000; realized_pl_sgd = 3375 - 2050 = 1325
        db_conn.execute(
            "INSERT INTO transactions (portfolio_id, ticker_id, date, action, price, quantity, currency) VALUES (?, ?, '2026-03-10', 'SELL', 250.0, 10.0, 'USD')",
            (pid, tid),
        )

    holdings = calculate_holdings(pid, db_conn)
    assert tid in holdings
    assert holdings[tid]["shares"] == pytest.approx(10.0)
    assert holdings[tid]["avg_cost"] == pytest.approx(150.0)

    sell_row = db_conn.execute(
        "SELECT cost_basis_after, realized_pl, realized_pl_sgd FROM transactions WHERE action = 'SELL'"
    ).fetchone()
    assert sell_row["cost_basis_after"] == pytest.approx(150.0)
    assert sell_row["realized_pl"] == pytest.approx(1000.0)
    assert sell_row["realized_pl_sgd"] == pytest.approx(1325.0)


def test_stock_split_preserves_total_cost_and_subsequent_sell(db_conn):
    """Verify stock split scales shares up, scales avg_cost down, and keeps realized P&L accurate."""
    pid, tid = _seed_portfolio_and_ticker(db_conn, symbol="NVDA", currency="USD")
    _seed_fx(db_conn, "2026-01-05", "USD", 1.30)
    _seed_fx(db_conn, "2026-02-05", "USD", 1.30)

    with db_conn:
        # Buy 5 @ 400 (total cost = 2000 USD, 2600 SGD)
        db_conn.execute(
            "INSERT INTO transactions (portfolio_id, ticker_id, date, action, price, quantity, currency) VALUES (?, ?, '2026-01-05', 'BUY', 400.0, 5.0, 'USD')",
            (pid, tid),
        )
        # 4-for-1 split -> 20 shares @ 100
        db_conn.execute(
            "INSERT INTO transactions (portfolio_id, ticker_id, date, action, price, quantity, currency) VALUES (?, ?, '2026-01-20', 'SPLIT', 4.0, 0.0, 'USD')",
            (pid, tid),
        )
        # Sell 5 @ 120 -> proceeds = 600 USD, cost = 500 USD -> P&L = +100 USD (+130 SGD)
        db_conn.execute(
            "INSERT INTO transactions (portfolio_id, ticker_id, date, action, price, quantity, currency) VALUES (?, ?, '2026-02-05', 'SELL', 120.0, 5.0, 'USD')",
            (pid, tid),
        )

    holdings = calculate_holdings(pid, db_conn)
    assert holdings[tid]["shares"] == pytest.approx(15.0)
    assert holdings[tid]["avg_cost"] == pytest.approx(100.0)

    sell_row = db_conn.execute(
        "SELECT realized_pl, realized_pl_sgd FROM transactions WHERE action = 'SELL'"
    ).fetchone()
    assert sell_row["realized_pl"] == pytest.approx(100.0)
    assert sell_row["realized_pl_sgd"] == pytest.approx(130.0)


def test_same_day_buy_prioritized_before_sell_and_full_exit_clears_holding(db_conn):
    """Same-day SELL inserted before BUY must still process BUY first and full exit removes active holding."""
    pid, tid = _seed_portfolio_and_ticker(db_conn, symbol="SGX", currency="SGD")

    with db_conn:
        # Insert SELL before BUY on the exact same date
        db_conn.execute(
            "INSERT INTO transactions (portfolio_id, ticker_id, date, action, price, quantity, currency) VALUES (?, ?, '2026-04-01', 'SELL', 12.0, 100.0, 'SGD')",
            (pid, tid),
        )
        db_conn.execute(
            "INSERT INTO transactions (portfolio_id, ticker_id, date, action, price, quantity, currency) VALUES (?, ?, '2026-04-01', 'BUY', 10.0, 100.0, 'SGD')",
            (pid, tid),
        )

    holdings = calculate_holdings(pid, db_conn)
    assert tid not in holdings

    sell_row = db_conn.execute(
        "SELECT realized_pl, realized_pl_sgd, cost_basis_after FROM transactions WHERE action = 'SELL'"
    ).fetchone()
    assert sell_row["realized_pl"] == pytest.approx(200.0)
    assert sell_row["realized_pl_sgd"] == pytest.approx(200.0)
    assert sell_row["cost_basis_after"] == pytest.approx(0.0)


def test_portfolio_summary_price_modes_and_dividends(db_conn):
    """Verify get_portfolio_summary handles intraday vs closing price modes and net dividend FX conversion."""
    pid, tid = _seed_portfolio_and_ticker(db_conn, symbol="D05.SI", currency="SGD")
    today_str = datetime.now().strftime("%Y-%m-%d")
    _seed_fx(db_conn, today_str, "USD", 1.35)

    with db_conn:
        db_conn.execute(
            "INSERT INTO transactions (portfolio_id, ticker_id, date, action, price, quantity, currency) VALUES (?, ?, '2026-01-15', 'BUY', 30.0, 10.0, 'SGD')",
            (pid, tid),
        )
        db_conn.execute(
            """
            INSERT INTO ticker_prices (ticker_id, price, intraday_current, intraday_prev_close, daily_close, daily_prev_close, currency, last_updated)
            VALUES (?, 35.0, 35.0, 34.0, 36.0, 33.0, 'SGD', '2026-01-15T00:00:00')
            """,
            (tid,),
        )
        # Gross 100 USD - 30 USD tax = 70 USD net @ 1.35 = 94.50 SGD
        db_conn.execute(
            "INSERT INTO dividends (portfolio_id, ticker_id, date, amount, tax, currency) VALUES (?, ?, ?, 100.0, 30.0, 'USD')",
            (pid, tid, today_str),
        )

    rates = {"SGD": 1.0, "USD": 1.35, "CAD": 1.0}
    intraday = get_portfolio_summary(pid, db_conn, rates, price_mode="intraday")
    closing = get_portfolio_summary(pid, db_conn, rates, price_mode="closing")

    assert intraday["total_value_sgd"] == pytest.approx(350.0)
    assert intraday["total_daily_pl_sgd"] == pytest.approx(10.0)
    assert intraday["total_dividends_net_sgd"] == pytest.approx(94.5)

    assert closing["total_value_sgd"] == pytest.approx(360.0)
    assert closing["total_daily_pl_sgd"] == pytest.approx(30.0)
