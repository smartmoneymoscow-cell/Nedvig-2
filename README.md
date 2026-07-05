# 🏠 Estate Auction Tracker

Агрегатор торгов по недвижимости с рыночной оценкой и отображением на Яндекс.Картах.

## Архитектура

```
┌─────────────────────────────────────────────────────┐
│                   FastAPI (main.py)                 │
│  ┌──────────┐  ┌──────────┐  ┌───────────────────┐ │
│  │ API routes│  │ Templates│  │ APScheduler       │ │
│  │ /api/*    │  │ Jinja2   │  │ (periodic scrape) │ │
│  └──────────┘  └──────────┘  └───────────────────┘ │
├─────────────────────────────────────────────────────┤
│              Services Layer                          │
│  ┌──────────────┐  ┌──────────────┐                 │
│  │ Enrichment   │  │ Geocoder     │                 │
│  │ (orchestrator)│  │ (Yandex API) │                 │
│  └──────────────┘  └──────────────┘                 │
├─────────────────────────────────────────────────────┤
│              Scrapers Layer                          │
│  ┌────────────┐ ┌──────────┐ ┌────────────────┐    │
│  │TorgiGov    │ │ GosPlan  │ │ CIAN           │    │
│  │(torgi.gov) │ │ (agg.)   │ │ (market price) │    │
│  └────────────┘ └──────────┘ └────────────────┘    │
│  ┌──────────────────────────────────────────────┐   │
│  │ ProxyManager (rotation, health, anti-bot)    │   │
│  └──────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────┤
│  PostgreSQL (SQLAlchemy + Alembic migrations)       │
└─────────────────────────────────────────────────────┘
```

## Источники данных

| Источник | Что даёт | Метод |
|----------|----------|-------|
| **torgi.gov.ru** | Лоты на государственных торгах | API + HTML fallback |
| **ГосПлан** | Агрегированные данные гос. площадок | API + HTML fallback |
| **ЦИАН** | Рыночная оценка стоимости | API + HTML scraping |

## Антиблокировка

- **curl_cffi** — TLS fingerprint impersonation (Chrome 120)
- **Прокси-ротация** — автоматический health-check и ротация
- **User-Agent ротация** — fake-useragent с реальными сигнатурами
- **Задержки** — рандомные паузы между запросами
- **Retry логика** — tenacity с exponential backoff

## Цветовая маркировка на карте

| Цвет | Дата публикации |
|------|----------------|
| 🔴 Красный | Сегодня |
| 🟠 Оранжевый | 1-3 дня |
| 🟡 Жёлтый | 4-7 дней |
| 🟢 Зелёный | 2-4 недели |
| 🔵 Синий | 1-3 месяца |
| 🟣 Фиолетовый | 3+ месяцев |

## Быстрый старт

### 1. Клонировать и настроить

```bash
cd estate-auction
cp .env.example .env
# Заполнить .env: API ключ Яндекс.Карт, прокси
```

### 2. Docker (рекомендуется)

```bash
docker-compose up -d
```

### 3. Или локально

```bash
# Установить PostgreSQL
# Создать БД: createdb estate_auction

# Установить зависимости
pip install -r requirements.txt

# Применить миграции
alembic upgrade head

# Запустить
uvicorn main:app --reload --port 8000
```

### 4. Открыть

http://localhost:8000

## API эндпоинты

| Метод | Путь | Описание |
|-------|------|----------|
| GET | `/api/properties` | Список объектов с фильтрами |
| GET | `/api/properties/{id}` | Детали объекта |
| GET | `/api/map-data` | Данные для карты (оптимизировано) |
| GET | `/api/stats` | Статистика |
| GET | `/api/scrape-logs` | Логи парсинга |
| POST | `/api/scrape/trigger` | Ручной запуск сбора |

## Конфигурация

Все настройки через переменные окружения (`.env`):

| Переменная | Описание | По умолчанию |
|-----------|----------|-------------|
| `DB_HOST` | Хост PostgreSQL | localhost |
| `DB_PORT` | Порт PostgreSQL | 5432 |
| `YANDEX_MAPS_API_KEY` | API ключ Яндекс.Карт | — |
| `PROXY_LIST` | Прокси через запятую | — |
| `SCRAPE_INTERVAL_HOURS` | Интервал автосбора (часы) | 6 |
| `APP_PORT` | Порт приложения | 8000 |

## Прокси

Формат в `PROXY_LIST`:
```
http://user:pass@host1:8080,socks5://host2:1080,http://host3:3128
```

Поддержка: HTTP, HTTPS, SOCKS5.

## Структура проекта

```
estate-auction/
├── main.py                  # FastAPI app + lifespan
├── models.py                # SQLAlchemy models
├── database.py              # DB engine & sessions
├── config/
│   ├── settings.py          # Pydantic settings
│   └── __init__.py
├── scrapers/
│   ├── base_scraper.py      # Anti-detection base
│   ├── proxy_manager.py     # Proxy rotation
│   ├── torgi_scraper.py     # torgi.gov.ru
│   ├── gosplan_scraper.py   # ГосПлан
│   ├── cian_scraper.py      # ЦИАН (market price)
│   └── __init__.py
├── services/
│   ├── geocoder.py          # Yandex Geocoder
│   ├── enrichment.py        # Pipeline orchestrator
│   └── __init__.py
├── api/
│   ├── routes.py            # API endpoints
│   └── __init__.py
├── templates/
│   └── index.html           # Main page (map)
├── static/
│   ├── css/style.css
│   └── js/app.js
├── alembic/                 # DB migrations
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── .env.example
```
