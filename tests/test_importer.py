import pytest
from ingestion.importer import clean_friendly_name, get_default_tax_rate, import_portfolio_data


def test_clean_friendly_name():
    assert clean_friendly_name("  Apple Inc.* ") == "Apple Inc."
    assert clean_friendly_name("DBS Group") == "DBS Group"
    assert clean_friendly_name("") == ""


def test_get_default_tax_rate():
    # Exchange-based precedence
    assert get_default_tax_rate("USD", "", "TO") == pytest.approx(0.15)
    assert get_default_tax_rate("CAD", "", "V") == pytest.approx(0.15)
    assert get_default_tax_rate("USD", "", "SG") == pytest.approx(0.0)
    assert get_default_tax_rate("USD", "", "NASDAQ") == pytest.approx(0.30)

    # Currency & country fallbacks
    assert get_default_tax_rate("SGD", "Singapore", "") == pytest.approx(0.0)
    assert get_default_tax_rate("CAD", "Canada", "") == pytest.approx(0.15)
    assert get_default_tax_rate("USD", "United States", "") == pytest.approx(0.30)


def test_import_portfolio_data_creates_portfolio_tickers_and_records(db_conn, tmp_path):
    # Pre-seed historical FX so importer does not hit Frankfurter API
    db_conn.execute(
        "INSERT INTO exchange_rates (date, currency, rate, last_updated) VALUES ('2026-01-10', 'USD', 1.34, 'test')"
    )
    db_conn.commit()

    holdings_csv = tmp_path / "holdings.csv"
    holdings_csv.write_text(
        "Holding,Holdings' name,Note,Shares,Currency,Share price,Country,Portfolios\n"
        "AAPL,Apple Inc.*,swing trade,10,USD,200.0,United States,Discord Trades\n"
        "OTHER,Other Corp,ignore,5,USD,10.0,United States,Different Portfolio\n",
        encoding="utf-8",
    )

    tx_csv = tmp_path / "transactions.csv"
    tx_csv.write_text(
        "Symbol,Event,Date,Price,Quantity,Currency,FeeTax,Note,Exchange\n"
        "AAPL,BUY,2026-01-10,180.0,10,USD,1.50,initial buy,NASDAQ\n"
        "AAPL,DIVIDEND,2026-01-10,2.50,25.0,USD,7.50,q1 div,NASDAQ\n",
        encoding="utf-8",
    )

    import_portfolio_data("Discord Trades", str(holdings_csv), str(tx_csv), db_conn)

    portfolio = db_conn.execute("SELECT id, name FROM portfolios WHERE name = 'Discord Trades'").fetchone()
    assert portfolio is not None

    ticker = db_conn.execute("SELECT symbol, friendly_name, tax_rate, exchange, category FROM tickers WHERE symbol = 'AAPL'").fetchone()
    assert ticker is not None
    assert ticker["friendly_name"] == "Apple Inc."
    assert ticker["tax_rate"] == pytest.approx(0.30)
    assert ticker["exchange"] == "NASDAQ"
    assert ticker["category"] == "swing"

    other = db_conn.execute("SELECT id FROM tickers WHERE symbol = 'OTHER'").fetchone()
    assert other is None

    tx = db_conn.execute("SELECT action, price, quantity, commission FROM transactions WHERE portfolio_id = ?", (portfolio["id"],)).fetchone()
    assert tx is not None
    assert tx["action"] == "BUY"
    assert tx["price"] == pytest.approx(180.0)
    assert tx["quantity"] == pytest.approx(10.0)
    assert tx["commission"] == pytest.approx(1.50)

    div = db_conn.execute("SELECT amount, tax, currency, qty FROM dividends WHERE portfolio_id = ?", (portfolio["id"],)).fetchone()
    assert div is not None
    assert div["amount"] == pytest.approx(25.0)
    assert div["tax"] == pytest.approx(7.50)
    assert div["currency"] == "USD"
    assert div["qty"] == pytest.approx(10.0)
