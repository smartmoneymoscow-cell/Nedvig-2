FROM python:3.12-slim

WORKDIR /app

# System deps + Tor + Playwright browser deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev curl tor \
    libnss3 libatk-bridge2.0-0 libdrm2 libxkbcommon-x11-0 \
    libgbm1 libasound2 libxshmfence1 \
    && rm -rf /var/lib/apt/lists/*

# Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Playwright browsers (only chromium to save space)
RUN playwright install --with-deps chromium 2>/dev/null || playwright install chromium

# Tor config — Russian exit nodes for scraping .ru sites
RUN echo "SocksPort 9050" >> /etc/tor/torrc && \
    echo "ExitNodes {ru}" >> /etc/tor/torrc && \
    echo "StrictNodes 1" >> /etc/tor/torrc

# Application code
COPY config/ config/
COPY scrapers/ scrapers/
COPY services/ services/
COPY models.py .
COPY database.py .
COPY worker.py .

EXPOSE 8001

# Start Tor in background, then Worker
CMD ["sh", "-c", "tor & sleep 3 && uvicorn worker:app --host 0.0.0.0 --port 8001"]
