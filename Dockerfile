FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev curl && rm -rf /var/lib/apt/lists/*

COPY api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY api/alembic.ini .
COPY api/alembic/ alembic/
COPY api/ .

# Pre-start script for safe migrations
COPY api/prestart.sh /prestart.sh
RUN chmod +x /prestart.sh

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["/prestart.sh"]
