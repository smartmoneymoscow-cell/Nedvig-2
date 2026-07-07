FROM python:3.12-slim

WORKDIR /app

# System deps + Tor + process manager
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev curl tor \
    libnss3 libatk-bridge2.0-0 libdrm2 libxkbcommon-x11-0 \
    libgbm1 libasound2 libxshmfence1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Playwright browsers
RUN playwright install chromium

# Tor config — exit nodes in RU + nearby countries for reliability
RUN echo "SocksPort 9050" >> /etc/tor/torrc && \
    echo "ExitNodes {ru},{by},{kz}" >> /etc/tor/torrc && \
    echo "StrictNodes 0" >> /etc/tor/torrc && \
    echo "CircuitBuildTimeout 30" >> /etc/tor/torrc && \
    echo "NumEntryGuards 6" >> /etc/tor/torrc

# Pre-start script
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

COPY . .

EXPOSE 8001

HEALTHCHECK --interval=60s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8001/health || exit 1

ENTRYPOINT ["/docker-entrypoint.sh"]
