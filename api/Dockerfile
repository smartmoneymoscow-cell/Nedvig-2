FROM python:3.12-slim

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev curl && rm -rf /var/lib/apt/lists/*

# Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application code (only api/ contents via dockerContext in render.yaml)
COPY alembic.ini .
COPY alembic/ alembic/
COPY config/ config/
COPY middleware/ middleware/
COPY models/ models/
COPY routes/ routes/
COPY services/ services/
COPY main.py .
COPY database.py .

EXPOSE 8000

# Run migrations then start server
CMD ["sh", "-c", "alembic upgrade head && uvicorn main:app --host 0.0.0.0 --port 8000"]
