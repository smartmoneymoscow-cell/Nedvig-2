FROM python:3.12-slim

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev curl && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# Run migrations then start server
CMD ["sh", "-c", "python -c \"from database import *; import asyncio; asyncio.run(init_db())\" && uvicorn main:app --host 0.0.0.0 --port 8000"]
