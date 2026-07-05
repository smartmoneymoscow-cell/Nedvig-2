FROM python:3.12-slim

WORKDIR /app

# System deps for Playwright/Selenium and PostgreSQL
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev curl wget gnupg2 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers (optional, for fallback scraping)
# RUN playwright install chromium

COPY . .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
