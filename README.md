# Self-Hosted Portfolio Manager

A self-hosted, lightweight investment portfolio manager built with a Python (FastAPI + SQLite) backend and a modern HTML5 + Vanilla CSS + JS / Vue 3 frontend.

### 🎯 Project Origins & Intention
This tracker originally started as a simple tool to monitor cash flows and dividend distributions, focusing on custom asset groupings for **thematic plays** or for consolidated tracking of **stocks with multiple tickers** (e.g. mapping single-stock ETFs alongside their actual underlying equities and/or ADRs in a single view).

Over time, the project evolved into a full-featured dashboard. The codebase heavily favors **Interactive Brokers (IBKR)** integration because it is my primary brokerage account; automated IBKR statement/data fetching is handled by private companion services using the `ib_async` library (kept private/unexposed because they manage real-money brokerage credentials), while this service consumes their exported reports and webhook triggers. The system also supports manual entries and CSV sheets for other brokers like **Moomoo**, though full API automation is not implemented for them due to limitations with their official SDKs.

---

## 🔒 Environment & Security Context

This project is architected strictly for a **private, single-user local network environment**. It is **not** designed or audited to be exposed to the public internet or hosted in a multi-tenant environment.

To maintain lightweight development and simple administrative operations, certain functionalities are intentionally permissive:
* **Dynamic Database Patching**: The patching module dynamically imports and executes Python scripts directly from the `patching/` directory based on local JSON manifest instructions.
* **Database Hot-Restores**: The system allows SQLite hot-backups, downloads, deletes, and restorations on-the-fly without built-in credentials.

No authentication, CSRF validation, or multi-user access controls are implemented. If you expose this application to a public network, you do so at your own risk. It is highly recommended to run this container locally or strictly behind a secure private VPN (e.g. Tailscale, WireGuard).

> [!WARNING]
> **Financial & Valuation Disclaimer**: This repository is provided **AS-IS** without any warranties of any kind. The author(s) and contributor(s) are not responsible or liable for any financial loss, transaction accounting discrepancies, incorrect portfolio valuations, trading errors, or damages resulting from bugs or errors in this project. Use at your own risk.

---

## 🛠️ Getting Started

### Method 1: Using Docker Compose (Recommended)

1. Build and start the container in the background:
   ```bash
   docker compose up -d --build
   ```
2. Open your browser and navigate to `http://127.0.0.1:8080`.
3. To stop the container:
   ```bash
   docker compose down
   ```
*Note: SQLite database files are persistently stored in the `./data` directory on the host.*

### Method 2: Running Locally (Without Docker)

1. Create a Python virtual environment and install dependencies:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```
2. Initialize the SQLite database schema:
   ```bash
   python3 core/database.py
   ```
3. Start the Uvicorn development server:
   ```bash
   uvicorn app:app --host 127.0.0.1 --port 8080 --reload
   ```
4. Open your browser and navigate to `http://127.0.0.1:8080`.

### Running Tests (Containerized)

Automated unit tests (`tests/`) cover core financial math, SQLite configuration, and CSV ingestion:
```bash
docker build --target builder -t portfolio-manager-test .
docker run --rm -v "$(pwd)":/app -w /app -e PYTHONPATH=/app:/install/lib/python3.12/site-packages portfolio-manager-test sh -c "pip install --no-cache-dir -q -r requirements-dev.txt && pytest -v"
```

---

## 🚀 Key Features

* **Multi-Portfolio & Combined Net Worth**: Consolidated overview ("My Net Worth") alongside individual broker/portfolio segments with customizable sorting priorities.
* **Interactive Transaction & Dividend Ledger**: Dynamic management interface (`/trades`) for editing, deleting, or manually inputting historical stock transactions and dividend distributions.
* **FIFO Financial Calculation Engine**: Calculates cost basis, realized P&L (native + historical FX-adjusted SGD), stock splits, and 12-month net/gross dividend aggregates.
* **Interactive Dividend Calendar**: Grid/List monthly visualization (`/dividend-calendar`) with calendar views, monthly totals, search filters, and IBKR statement synchronization.
* **IBKR Statement Reconciliation**: Compares database positions against uploaded IBKR statement positions (`ib_data.json`) to display mismatch warnings and sync badges.
* **Options & Stress-Testing Dashboards**: Integrates with external options trackers to visualize active contracts, risk exposure metrics, expiration profiles, and cash stress tests.
* **Option Deliveries (Assignments & Exercises) Sync**: Interactive modal on the Trades Ledger to fetch option deliveries from Options Tracker (`/api/deliveries`), select target portfolios, and import stock executions at effective basis pricing with duplicate protection.
* **Control Center (Operations, Capital, Cash, Configuration & System Admin)**: Unified hub (`/control-center`) for administrative price refreshes, bulk price history imports, base capital & daily cash tracking, runtime settings overrides, database backups/hot-restores, and manifest-driven patching.
* **Smart & Synchronous Yahoo Finance Batch Ingestion**: Fetches prices in batches using `yfinance` (`auto_adjust=False`) with market-session awareness, 15-minute intraday caching, and synchronous UI updates.
* **Price History Gap-Filling & Bulk Overrides**: Date-level price editor on the dashboard and bulk JSON history override imports (`/api/prices/import-history`) to backfill missing bars or adjust illiquid securities with manual protection (`is_manual = 1`).
* **Transaction Visualizer (TX Visualizer)**: Per-ticker candlestick charts (`7d`, `1m`, `3m`, `6m`, `YTD`, `1y`, `5y`, `all`, and custom ranges) overlaying buy/sell executions with 3-decimal OHLC tooltips.
* **Tag Exposure & Analytics (`/tags`)**: Custom asset tagging and portfolio weight/exposure breakdown across holdings.
* **Fixed Deposit Comparison (`/fd-comparison`)**: Simulates deployed capital performance in fixed-rate deposits versus actual portfolio returns.
* **Position Calculator Widget**: Floating multi-ticker comparison drawer on the dashboard to simulate buys/sells, projected portfolio weights, within-stock trim %, and enforced lot sizes (`100` for SG/CA, `1` for US) with 1-click `Max` liquidation.

---

## ⚙️ Configuration & Supplementary Data Files

### Configuration Overrides Priority
1. **Database settings table overrides**: Custom configurations stored in SQLite (e.g., `sorting.classification_priority`, `external_services.options_tracker_url`, `external_services.backtester_url`), editable via **Control Center → Configuration**.
2. **`data/config.json`** overrides (falls back to `config/config.json` defaults).

See the [Settings & Configuration Guide](docs/settings_configuration.md) and [JSON Data Files Reference](docs/data_files.md) for all keys and schemas.

### Environment Variables
* `BASE_PATH`: Sub-path prefix for reverse-proxy hosting (e.g. `/portfolio`).
* `PORTFOLIO_DB_FILE`: File path for the SQLite database (defaults to `data/portfolio.db`).
* `IB_DATA_FILE`: Custom file path for the IBKR position report (defaults to `data/ib_data.json`).
* `exchange_rates_file`: File path for exchange rate caches (defaults to `data/exchange_rates.json`).

### Supplementary Data Files & Upload Targets
Allowed upload targets are configured dynamically under `"allowed_documents"` in [`config/config.json`](config/config.json) (writes go to `data/` so they remain untracked):

| File Path | Description / Purpose | If Missing / Default |
| :--- | :--- | :--- |
| **`data/config.json`** | User overrides for conversion rates, themes, and allowed upload targets. | Falls back to **`config/config.json`**. |
| **`data/ib_data.json`** | IBKR position & balance report (`NetLiquidation`, `GrossPositionValue`, `TotalCashValue`). | Reconciliation badges skipped; cash reports use DB only. |
| **`data/stock-options.json`** | Fallback options positions cache when `options_tracker_url` is offline. | Options panels omitted if neither API nor cache exists. |

---

## 🔌 External Services Integration

Configured under `"external_services"` in `config/config.json` (or overridden in **Control Center → Configuration**):

```json
  "external_services": {
    "options_tracker_url": "http://yui.home/options-tracker",
    "backtester_url": "http://yui.home/backtester/",
    "transaction_ocr_url": "http://yui.home/transaction-ocr/"
  }
```

* **Options Tracker Service (`options_tracker_url`)** ([GitHub](https://github.com/SkyStrike/options-tracker)): Powers **Active Open Options**, **Risk & Liquidity Analysis**, option P/L in the dashboard header, and **Option Deliveries** import (`/api/deliveries`). Falls back to `data/stock-options.json` if offline; hidden completely when unconfigured.
* **Backtesting Service (`backtester_url`)** ([GitHub](https://github.com/SkyStrike/backtester)): Adds direct backtest links (🔗) on underlying asset headers with pre-populated `yfinance` tickers and start dates; hidden when unconfigured.
* **Transaction OCR Service (`transaction_ocr_url`)**: Adds a direct link under the **Services** navbar dropdown; hidden when unconfigured.

---

## 📖 User Guides & Documentation

### Setup & Configuration
* **[Settings & Configuration Guide](docs/settings_configuration.md)**: Runtime precedence, SQLite settings overrides, external service URLs, and webhooks.
* **[JSON Data Files Reference](docs/data_files.md)**: Catalog and JSON schemas for system configurations and IBKR caches.
* **[Metadata Configuration Guide](docs/metadata_config.md)**: Custom portfolio classifications and broker setup.

### Importing & Broker Sync
* **[Data Migration Guide](docs/data_migration.md)**: Exporting portfolios from Snowball Analytics and importing them.
* **[Broker Capital CSV Guide](docs/capital_csv.md)**: Managing and importing base capital injection records.
* **[IBKR Data File Guide](docs/ib_data_guide.md)**: Formatting, uploading, and cron ingestion for `ib_data.json`.
* **[IBKR Dividend & Verification Guide](docs/ibkr_dividend_import.md)**: Accruals integration, XML flex imports, and reconciliation.
* **[File Upload API Guide](docs/file_uploads.md)**: Uploading `stock-options` and `ib-data` JSON files via API.

### Market Data & Features
* **[Illiquid Stock & Price History Guide](docs/illiquid_stock_price_update.md)**: Manual bar gap-filling, bulk JSON overrides (`tmp/history.json`), date-level overrides, and Closing vs Intraday P&L.
* **[Daily Weekday Metrics Job Guide](docs/daily_metrics_job.md)**: Automated 6 AM SGT weekday sync, cache pre-warming, and manual daily cash entry.
* **[Position Calculator Guide](docs/position_calculator.md)**: Simulating trades, lot-size rules, cashflows, and projected weightages.

### Maintenance & Automation
* **[System Maintenance & Patching Guide](docs/patching.md)**: Database backups, hot-restores, manifest schemas, and custom Python patch scripts.
* **[Advanced Scripting & API Guide](docs/advanced_scripting.md)**: Automation scripts, pre-warming triggers, and REST/Swagger integration.

---

## 📂 Project Structure

* **[`app.py`](app.py)**: FastAPI entrypoint, router registration, `BASE_PATH` mounting, and background cron loops.
* **`core/`**: SQLite connection & schema ([`database.py`](core/database.py)), Alembic runner ([`migrations.py`](core/migrations.py)), financial math ([`calculations.py`](core/calculations.py), [`performance_calculator.py`](core/performance_calculator.py)), caching ([`cache.py`](core/cache.py)), models, and Pydantic schemas.
* **`services/`**: Dashboard builder ([`rebuild_dashboard.py`](services/rebuild_dashboard.py)), Yahoo Finance ingestion ([`price_service.py`](services/price_service.py)), FX rates, dividend calendar/sync, performance reports, and FD simulator.
* **`routers/`**: Modular FastAPI endpoints (`views`, `dashboard`, `transactions`, `dividends`, `prices`, `portfolios`, `tickers`, `deliveries`, `reports`, `settings`, `uploads`, `patches`, `api_v1`).
* **`ingestion/`**: Snowball CSV portfolio & transaction importer ([`importer.py`](ingestion/importer.py)).
* **`migrations/` & `patching/`**: Alembic schema migrations and manifest-driven data patch scripts.
* **`templates/` & `static/`**: Vue 3 SPA dashboard shell (`spa_shell.html`, `spa_app.js`) and Ledger/Control Center views (`trades.html`, `control_center.html`, `app.js`).
* **`tests/`**: Containerized `pytest` unit test suite.

---

## 📄 License

This project is open-source and licensed under the [MIT License](LICENSE).
