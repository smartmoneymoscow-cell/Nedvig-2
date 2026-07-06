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
│  ┌──────────────────────────────────────────────┐   │
│  │ Middleware: Rate Limiting, Security Headers   │   │
│  └──────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────┤
│              Services Layer                          │
│  ┌──────────────┐  ┌──────────────┐                 │
│  │ Enrichment   │  │ Geocoder     │                 │
│  │ (orchestrator)│  │ (Yandex API) │                 │
│  └──────────────┘  └──────────────┘                 │
├─────────────────────────────────────────────────────┤
│              Scrapers Layer                          │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐      │
│  │TorgiGov    │ │ Fedresurs  │ │ CIAN       │      │
│  │(torgi.gov) │ │ (bankrupt) │ │ (market)   │      │
│  └────────────┘ └────────────┘ └────────────┘      │
│  ┌──────────────────────────────────────────────┐   │
│  │ ProxyManager + Anti-Detection (curl_cffi,    │   │
│  │ Playwright, UA rotation, proxy health-check) │   │
│  └──────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────┤
│  PostgreSQL 16 (SQLAlchemy + Alembic migrations)    │
└─────────────────────────────────────────────────────┘
```

## Источники данных

| Источник | Что даёт | Метод |
|----------|----------|-------|
| **torgi.gov.ru** | Лоты на государственных торгах | REST API (verified) |
| **Fedresurs** | Торги банкротов (банкротные лоты) | Playwright + API fallback |
| **ЦИАН** | Рыночная оценка стоимости | curl_cffi + Playwright fallback |
| **ЭТП** | Дополнительные площадки (lot-online, fabrikant) | HTML scraping |

## Быстрый старт

### 1. Клонировать и настроить

```bash
git clone <repo-url>
cd Nedvig-2
cp .env.example .env
# Заполнить .env: YANDEX_MAPS_API_KEY, PROXY_LIST, ADMIN_API_KEY
```

### 2. Docker (рекомендуется)

```bash
docker-compose up -d
```

### 3. Или локально

```bash
pip install -r requirements.txt
# Для Playwright (опционально):
# playwright install chromium
alembic upgrade head
uvicorn main:app --reload --port 8000
```

### 4. Открыть

http://localhost:8000

## API

| Метод | Путь | Описание | Auth |
|-------|------|----------|------|
| GET | `/health` | Health check | — |
| GET | `/api/properties` | Список объектов с фильтрами | — |
| GET | `/api/properties/{id}` | Детали объекта | — |
| GET | `/api/map-data` | Данные для карты (оптимизировано) | — |
| GET | `/api/stats` | Статистика | — |
| GET | `/api/scrape-logs` | Логи парсинга | — |
| POST | `/api/scrape/trigger` | Ручной запуск сбора | API Key |

## Безопасность

### Аутентификация

Admin-эндпоинты (scrape trigger) защищены API ключом:

```bash
# Генерация ключа:
python3 -c "import secrets; print(secrets.token_urlsafe(32))"

# Использование:
curl -X POST http://localhost:8000/api/scrape/trigger \
  -H "Authorization: Bearer <YOUR_API_KEY>"
```

### Rate Limiting

- API: 10 запросов/секунду на IP
- Scrape trigger: 0.5 запросов/секунду на IP

### Защита заголовков

- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `X-XSS-Protection: 1; mode=block`
- `Referrer-Policy: strict-origin-when-cross-origin`

## Конфигурация

Все настройки через переменные окружения (`.env`):

| Переменная | Описание | По умолчанию |
|-----------|----------|-------------|
| `DB_HOST` | Хост PostgreSQL | localhost |
| `DB_PORT` | Порт PostgreSQL | 5432 |
| `DB_PASSWORD` | Пароль БД | postgres |
| `YANDEX_MAPS_API_KEY` | API ключ Яндекс.Карт | — |
| `PROXY_LIST` | Прокси через запятую | — |
| `SCRAPE_INTERVAL_HOURS` | Интервал автосбора (часы) | 6 |
| `ADMIN_API_KEY` | API ключ для admin-эндпоинтов | — |
| `CORS_ORIGINS` | Разрешённые origins (через запятую) | * |
| `DEBUG` | Режим отладки | false |
| `APP_PORT` | Порт приложения | 8000 |

## Тесты

```bash
pip install pytest pytest-asyncio httpx
python3 -m pytest tests/ -v
```

75 тестов covering:
- Модели (SQLAlchemy, EnumString)
- API routes (CRUD, фильтры, пагинация, валидация)
- TorgiGovScraper (парсинг, типы, статусы)
- ProxyManager (ротация, health-check)
- BaseScraper (парсинг цен, дат)

## Структура проекта

```
Nedvig-2/
├── main.py                  # FastAPI app + middleware + lifespan
├── models.py                # SQLAlchemy models (AuctionProperty, ScrapeLog)
├── database.py              # DB engine & sessions (async + sync)
├── config/
│   └── settings.py          # Pydantic settings
├── scrapers/
│   ├── base_scraper.py      # Anti-detection base (curl_cffi, throttling)
│   ├── proxy_manager.py     # Proxy rotation + health-check
│   ├── torgi_scraper.py     # torgi.gov.ru (verified API)
│   ├── fedresurs_scraper.py # Fedresurs (bankruptcy auctions)
│   ├── cian_scraper.py      # CIAN (market price estimation)
│   └── etp_scraper.py       # ETP platforms (lot-online, fabrikant)
├── services/
│   ├── enrichment.py        # Pipeline orchestrator (async-safe)
│   └── geocoder.py          # Yandex Geocoder
├── api/
│   └── routes.py            # API endpoints (with input validation)
├── templates/
│   └── index.html           # Main page (Yandex.Map)
├── static/
│   ├── css/style.css
│   └── js/app.js
├── alembic/                 # DB migrations
├── tests/                   # 75 tests
├── docker-compose.yml
├── Dockerfile
└── requirements.txt
```

## Дорожная карта

### Phase 1: MVP ✅
- [x] Парсинг torgi.gov.ru (verified API)
- [x] Fedresurs scraper (bankruptcy auctions)
- [x] Рыночная оценка через ЦИАН
- [x] Яндекс.Карта с цветовой маркировкой
- [x] API для фильтрации и статистики
- [x] Rate limiting + security headers
- [x] Admin API key auth
- [x] Async-safe pipeline (asyncio.to_thread)
- [x] 75 тестов

### Phase 2: Production Ready
- [ ] Nginx reverse proxy + SSL
- [ ] Celery для фоновых задач парсинга
- [ ] Redis кэш для map-data
- [ ] Email/Telegram уведомления о новых лотах
- [ ] JWT авторизация
- [ ] Пагинация на фронтенде

### Phase 3: Расширенный функционал
- [ ] Избранные объекты
- [ ] Графики изменения цен
- [ ] PostGIS для гео-запросов
- [ ] Полный текстовый поиск (Elasticsearch)
- [ ] Telegram-бот для уведомлений
- [ ] Экспорт в Excel/CSV
