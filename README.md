# 🏠 Nedvig — Estate Auction Tracker

Агрегатор торгов по недвижимости с рыночной оценкой и отображением на карте.

## Архитектура

```
┌─────────────────────────┐     ┌──────────────────────────┐
│   Frontend (GitHub Pages)│     │   API Service (Render)    │
│   React + Leaflet        │────▶│   FastAPI + PostgreSQL    │
│   Static SPA             │     │   /api/properties, etc.   │
└─────────────────────────┘     └──────────────────────────┘
                                           ▲
                                           │ HTTP
                                ┌──────────┴──────────────┐
                                │  Scraper Worker (Render)  │
                                │  TorgiGov, Fedresurs,     │
                                │  CIAN, ETP                │
                                │  Tor + curl_cffi          │
                                └──────────────────────────┘
```

## Стек

| Компонент | Технология |
|-----------|------------|
| **Frontend** | React 18, TypeScript, Vite, TailwindCSS, Leaflet |
| **Backend** | Python 3.12, FastAPI, SQLAlchemy 2.0 |
| **Database** | PostgreSQL 16 (Render managed) |
| **Scraping** | curl_cffi, Playwright, Tor SOCKS5 |
| **Deploy** | GitHub Pages (frontend), Render (backend + worker) |

## Источники данных

| Источник | Что даёт | Антиблокировка |
|----------|----------|----------------|
| **torgi.gov.ru** | Государственные торги | Прямой API (без блокировок) |
| **Fedresurs** | Банкротные торги | Playwright + Tor |
| **CIAN** | Рыночная оценка | curl_cffi + Tor |
| **ЭТП** | Доп. площадки | curl_cffi + free proxies |

## Быстрый старт

### Локально

```bash
# Backend
cd api
pip install -r requirements.txt
USE_SQLITE=true uvicorn main:app --reload --port 8000

# Scraper Worker
cd scraper-worker
pip install -r requirements.txt
USE_SQLITE=true uvicorn worker:app --reload --port 8001

# Frontend
cd frontend
npm install
npm run dev  # → http://localhost:5173
```

### Docker

```bash
docker-compose up -d
```

## API

| Метод | Путь | Описание |
|-------|------|----------|
| GET | `/health` | Health check |
| GET | `/api/properties` | Список с фильтрами |
| GET | `/api/properties/{id}` | Детали объекта |
| GET | `/api/map-data` | Данные для карты |
| GET | `/api/stats` | Статистика |
| GET | `/api/scrape-logs` | Логи парсинга |
| POST | `/api/scrape/trigger` | Ручной запуск (auth) |
| POST | `/api/auth/register` | Регистрация |
| POST | `/api/auth/login` | Вход |

## Деплой

- **Frontend:** Push в `main` → GitHub Actions → GitHub Pages
- **Backend:** Push в `main` → Render auto-deploy
- **Database:** Render managed PostgreSQL (free tier)

## Структура

```
Nedvig-2/
├── api/                    # API Service
│   ├── main.py
│   ├── config/settings.py
│   ├── models/
│   ├── routes/
│   ├── middleware/
│   ├── services/
│   ├── alembic/
│   ├── Dockerfile
│   └── requirements.txt
├── scraper-worker/         # Scraper Worker
│   ├── worker.py
│   ├── scrapers/
│   ├── services/
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/               # React SPA
│   ├── src/
│   ├── package.json
│   └── vite.config.ts
├── .github/workflows/      # CI/CD
├── render.yaml             # Render config
└── docker-compose.yml      # Local dev
```

## Тесты

```bash
cd api
pip install pytest pytest-asyncio httpx
USE_SQLITE=true python -m pytest tests/ -v
```

## Лицензия

MIT
