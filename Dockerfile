# ==========================================
# Stage 1: Build & Dependency Resolver
# ==========================================
FROM python:3.12-slim AS builder

WORKDIR /build

# Install compilation toolchain needed for Python package builds
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Install dependencies into an isolated prefix
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir --prefix=/install -r requirements.txt


# ==========================================
# Stage 2: Hardened Minimal Runtime Image
# ==========================================
FROM python:3.12-slim AS runtime

# 1. Apply OS security patches (fixes zlib1g) and purge default packaging tools (eliminates pip CVEs)
RUN apt-get update && apt-get upgrade -y && rm -rf /var/lib/apt/lists/* && \
    python -m pip uninstall -y pip setuptools wheel 2>/dev/null || true && \
    rm -rf /usr/local/lib/python3.12/ensurepip /usr/local/bin/pip*

# 2. Copy pre-built application dependencies from builder
COPY --from=builder /install /usr/local

# 3. Create non-root user (appuser:1000)
RUN groupadd -g 1000 appuser && \
    useradd -u 1000 -g appuser -s /bin/bash -m appuser

WORKDIR /app

# 4. Copy application source code with non-root ownership
COPY --chown=appuser:appuser . /app

# 5. Make patch scripts executable
RUN find /app/patching -type f -name "*.sh" -exec chmod +x {} +

# 6. Ensure persistent data directory exists with appuser ownership
RUN mkdir -p /app/data && \
    chown -R appuser:appuser /app

USER appuser

EXPOSE 8080

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORTFOLIO_DB_FILE=/app/data/portfolio.db \
    exchange_rates_file=/app/data/exchange_rates.json \
    exchange_rates_max_poll_hours=6 \
    exchange_rates_decimals=4 \
    BASE_PATH="" \
    LOG_LEVEL=INFO

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080", "--log-config", "log_config.json"]
