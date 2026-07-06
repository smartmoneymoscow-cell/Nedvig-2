FROM python:3.12-slim

WORKDIR /app

# System deps + Tor
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev curl tor \
    libnss3 libatk-bridge2.0-0 libdrm2 libxkbcommon-x11-0 \
    libgbm1 libasound2 libxshmfence1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Playwright browsers
RUN playwright install chromium

# Tor config
RUN echo "SocksPort 9050" >> /etc/tor/torrc && \
    echo "ExitNodes {ru}" >> /etc/tor/torrc && \
    echo "StrictNodes 1" >> /etc/tor/torrc

COPY . .

# Start Tor + Worker
CMD ["sh", "-c", "tor & sleep 5 && uvicorn worker:app --host 0.0.0.0 --port 8001"]
