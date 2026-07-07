# 📋 ПАСПОРТ ПРОЕКТА Nedvig-2

> **Дата:** 2026-07-07
> **Репозиторий:** https://github.com/smartmoneymoscow-cell/Nedvig-2
> **Ветка разработки:** `fix/deploy-and-code-quality`
> **Продакшн (frontend):** https://smartmoneymoscow-cell.github.io/Nedvig-2/

---

## 1. ОПИСАНИЕ ПРОЕКТА

**Nedvig-2** — агрегатор торгов по недвижимости с рыночной оценкой и отображением на карте.

Сервис собирает данные о лотах на государственных торгах (torgi.gov.ru), торгах банкротов (Fedresurs), электронных площадках (ЭТП), обогащает их рыночной оценкой (CIAN) и отображает на интерактивной карте с фильтрацией и статистикой.

### Целевая аудитория
- Инвесторы в недвижимость
- Риэлторы
- Арбитражные управляющие
- Частные покупатели

### Ключевые возможности
- 🗺️ Интерактивная карта с кластеризацией маркеров
- 🔍 Фильтры: город, тип, цена, площадь, скидка, статус, источник
- 📊 Статистика: всего объектов, по источникам, по статусам, средняя скидка
- 💰 Рыночная оценка: сравнение аукционной цены с рынком (CIAN)
- 🌙 Тёмная / светлая тема
- 📱 Мобильная адаптивность

---

## 2. ТЕХНИЧЕСКИЙ СТЕК

| Компонент | Технология | Версия |
|---|---|---|
| **Frontend** | React, TypeScript, Vite, TailwindCSS | React 18, TS 5, Vite 5, TW 3.4 |
| **Карта** | Leaflet, react-leaflet, MarkerCluster | Leaflet 1.9 |
| **Data fetching** | TanStack Query (react-query) | v5 |
| **Анимации** | Framer Motion | v11 |
| **Иконки** | Lucide React | latest |
| **Backend** | Python, FastAPI, SQLAlchemy 2.0 | Python 3.12, FastAPI 0.115 |
| **База данных** | PostgreSQL (prod), SQLite (dev/test) | PG 16 |
| **Миграции** | Alembic | 1.13 |
| **Скрейпинг** | curl_cffi, Playwright, BeautifulSoup | curl_cffi 0.7, PW 1.45 |
| **Прокси** | Free SOCKS5 auto-discovery, Tor | — |
| **Геокодинг** | Yandex Geocoder API | — |
| **Логирование** | Loguru | 0.7 |
| **Тестирование** | pytest, pytest-asyncio, httpx | pytest 9 |
| **Деплой frontend** | GitHub Pages | — |
| **Деплой backend** | Render (Docker) | — |
| **CI/CD** | GitHub Actions | — |

---

## 3. АРХИТЕКТУРА

### 3.1 Общая схема

```
┌─────────────────────────────────────────────────────────────────┐
│                    GitHub Pages (Frontend)                       │
│                    React + Leaflet + TailwindCSS                 │
│                    https://smartmoneymoscow-cell.github.io/...   │
└──────────────────────────┬──────────────────────────────────────┘
                           │ fetch()
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Render (Backend)                              │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │              FastAPI Application                           │  │
│  │  /api/properties  /api/map-data  /api/stats               │  │
│  │  /api/scrape-logs /api/auth  /health                       │  │
│  └──────────────────────────┬────────────────────────────────┘  │
│                              │                                   │
│  ┌──────────────────────────▼────────────────────────────────┐  │
│  │              PostgreSQL 16 (Render managed)                 │  │
│  │              auction_properties + scrape_logs + users       │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                           ▲
                           │ HTTP webhook
┌──────────────────────────┴──────────────────────────────────────┐
│              Scraper Worker (Background)                          │
│  ┌─────────┐ ┌──────────┐ ┌────────┐ ┌────────┐               │
│  │ TorgiGov │ │ Fedresurs│ │  CIAN  │ │  ETP   │               │
│  └────┬────┘ └────┬─────┘ └───┬────┘ └───┬────┘               │
│       └───────────┴───────────┴───────────┘                    │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  Anti-Detection: curl_cffi, Playwright, Tor, ProxyManager  │  │
│  └───────────────────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  Enrichment: Geocoder (Yandex) + Market Estimation (CIAN)  │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 Двойная структура кодовой базы

Проект имеет **два набора модулей** для обратной совместимости:

| Корневая директория | Микросервис | Назначение |
|---|---|---|
| `main.py`, `database.py`, `models.py` | `api/main.py`, `api/database.py`, `api/models/` | API Service |
| `scrapers/` | `scraper-worker/scrapers/` | Скрейперы |
| `services/` | `scraper-worker/services/` | Enrichment, Geocoder |
| `routes/`, `middleware/` | `api/routes/`, `api/middleware/` | API Routes, Middleware |
| `config/settings.py` | `api/config/settings.py`, `scraper-worker/config/settings.py` | Конфигурация |
| `tests/` | — | Юнит-тесты (используют корневые модули) |

Корневые файлы — для монолитного запуска и тестов.
`api/` и `scraper-worker/` — для микросервисного деплоя на Render.

---

## 4. СТРУКТУРА ФАЙЛОВ

```
Nedvig-2/
├── .github/workflows/          # CI/CD (GitHub Actions)
├── alembic/                    # Миграции БД (корневые)
│   └── versions/
│       └── 001_initial.py      # Создание таблиц
├── api/                        # API Service (микросервис)
│   ├── config/settings.py      # Pydantic Settings
│   ├── database.py             # AsyncEngine, sessions
│   ├── models/__init__.py      # SQLAlchemy ORM
│   ├── routes/
│   │   ├── properties.py       # /api/properties, /map-data, /stats
│   │   └── auth.py             # /api/auth/register, /login
│   ├── middleware/
│   │   └── rate_limiter.py     # Rate limiting + security headers
│   ├── services/
│   │   ├── auth.py             # JWT auth
│   │   └── password.py         # bcrypt hashing
│   ├── main.py                 # FastAPI app, lifespan, CORS
│   ├── Dockerfile              # Docker build
│   ├── requirements.txt        # Python deps
│   └── alembic/                # Миграции (микросервис)
│       └── versions/
│           ├── 001_initial.py  # String columns (не PG enum)
│           └── 002_fix_enums.py # No-op
├── frontend/                   # React SPA
│   ├── src/
│   │   ├── App.tsx             # Root component
│   │   ├── main.tsx            # Entry point
│   │   ├── api/client.ts       # API client (static + dynamic mode)
│   │   ├── components/
│   │   │   ├── Header.tsx      # Top navigation
│   │   │   ├── Sidebar.tsx     # Filters panel
│   │   │   ├── MapView.tsx     # Leaflet map + markers
│   │   │   ├── DetailPanel.tsx # Property detail slide-in
│   │   │   └── StatsBar.tsx    # Statistics bar
│   │   ├── types/index.ts      # TypeScript types
│   │   └── styles/globals.css  # CSS variables, animations
│   ├── index.html              # HTML template
│   ├── vite.config.ts          # Vite config (base: /Nedvig-2/)
│   ├── tailwind.config.js      # TailwindCSS config
│   ├── tsconfig.json           # TypeScript config
│   └── package.json            # npm deps
├── scrapers/                   # Скрейперы (корневые, для тестов)
│   ├── base_scraper.py         # BaseScraper: anti-detect, retry, throttle
│   ├── torgi_scraper.py        # TorgiGovScraper: REST API
│   ├── fedresurs_scraper.py    # FedresursScraper: Playwright + XHR
│   ├── cian_scraper.py         # CianScraper: market estimation
│   ├── etp_scraper.py          # EtpScraper: lot-online, fabrikant
│   └── proxy_manager.py        # ProxyManager: auto-discovery, rotation
├── scraper-worker/             # Scraper Worker (микросервис)
│   ├── scrapers/               # (зеркало scrapers/)
│   ├── services/
│   │   ├── enrichment.py       # EnrichmentService: pipeline orchestration
│   │   └── geocoder.py         # Yandex Geocoder
│   ├── worker.py               # Standalone worker (FastAPI healthcheck)
│   ├── Dockerfile
│   └── requirements.txt
├── services/                   # Services (корневые)
│   ├── enrichment.py
│   ├── geocoder.py
│   ├── auth.py
│   └── password.py
├── routes/                     # Routes (корневые)
│   ├── properties.py
│   └── auth.py
├── middleware/
│   └── rate_limiter.py
├── config/settings.py          # Unified Settings
├── database.py                 # DB connection
├── models.py                   # SQLAlchemy models
├── main.py                     # FastAPI app (root)
├── tests/                      # pytest тесты
│   ├── conftest.py             # Fixtures (SQLite test DB)
│   ├── test_models.py          # Model tests
│   ├── test_base_scraper.py    # Base scraper tests
│   ├── test_torgi_scraper.py   # TorgiGov tests
│   ├── test_cian_scraper.py    # CIAN tests
│   ├── test_proxy_manager.py   # Proxy manager tests
│   └── test_api_routes.py      # API endpoint tests
├── render.yaml                 # Render deploy config
├── docker-compose.yml          # Local dev (PG + API + Worker)
├── Dockerfile                  # Root Dockerfile (monolith)
├── requirements.txt            # Root Python deps
├── seed_demo.py                # Demo data seeder (20 properties)
├── static-api/                 # Static JSON for GH Pages
│   ├── map-data.json           # Map points
│   ├── properties.json         # Full property list
│   └── stats.json              # Statistics
├── ARCHITECTURE.md             # Detailed architecture doc
├── ANALYSIS_REPORT.md          # Full audit report
├── SCRAPER_AUDIT.md            # Scraper audit
└── WORK_PLAN.md                # Development plan
```

---

## 5. МОДЕЛЬ ДАННЫХ

### 5.1 AuctionProperty (основная таблица)

| Поле | Тип | Описание |
|---|---|---|
| `id` | INTEGER PK | Автоинкремент |
| `source` | VARCHAR(50) | Источник: torgi_gov, fedresurs, etp, cian |
| `source_id` | VARCHAR(255) | ID в источнике |
| `source_url` | TEXT | Ссылка на лот |
| `title` | TEXT | Название лота |
| `description` | TEXT | Описание |
| `property_type` | VARCHAR(50) | apartment, house, land, commercial, room, garage, other |
| `address` | TEXT | Адрес |
| `region` | VARCHAR(255) | Код региона (OKATO) |
| `city` | VARCHAR(255) | Город |
| `latitude` | FLOAT | Широта |
| `longitude` | FLOAT | Долгота |
| `total_area` | FLOAT | Общая площадь (м²) |
| `living_area` | FLOAT | Жилая площадь |
| `rooms` | INTEGER | Количество комнат |
| `floor` | INTEGER | Этаж |
| `total_floors` | INTEGER | Этажность |
| `start_price` | FLOAT | Начальная цена (₽) |
| `current_price` | FLOAT | Текущая цена |
| `market_price` | FLOAT | Рыночная оценка (CIAN) |
| `price_per_sqm` | FLOAT | Цена за м² |
| `discount_pct` | FLOAT | Скидка от рынка (%) |
| `auction_status` | VARCHAR(50) | active, upcoming, completed, cancelled |
| `auction_date_start` | TIMESTAMP | Начало торгов |
| `auction_date_end` | TIMESTAMP | Конец торгов |
| `publish_date` | DATE | Дата публикации |
| `lot_number` | VARCHAR(100) | Номер лота |
| `organizer` | TEXT | Организатор торгов |
| `bid_step` | FLOAT | Шаг торгов |
| `deposit` | FLOAT | Задаток |
| `raw_data` | JSON | Исходные данные из API |
| `created_at` | TIMESTAMP | Дата создания |
| `updated_at` | TIMESTAMP | Дата обновления |
| `is_geocoded` | BOOLEAN | Геокодировано? |
| `is_market_appraised` | BOOLEAN | Оценено рынком? |

**Индексы:**
- `ix_source_source_id` — UNIQUE (source, source_id)
- `ix_publish_date` — (publish_date)
- `ix_city_property_type` — (city, property_type)
- `ix_auction_status` — (auction_status)
- `ix_coords` — (latitude, longitude)

### 5.2 ScrapeLog

| Поле | Тип | Описание |
|---|---|---|
| `id` | INTEGER PK | Автоинкремент |
| `source` | VARCHAR(50) | Источник |
| `started_at` | TIMESTAMP | Время старта |
| `finished_at` | TIMESTAMP | Время завершения |
| `items_found` | INTEGER | Найдено лотов |
| `items_new` | INTEGER | Новых лотов |
| `items_updated` | INTEGER | Обновлённых лотов |
| `errors` | TEXT | Ошибки |
| `status` | VARCHAR(50) | running, success, error |
| `proxy_used` | VARCHAR(500) | Использованный прокси |

### 5.3 User

| Поле | Тип | Описание |
|---|---|---|
| `id` | INTEGER PK | Автоинкремент |
| `email` | VARCHAR(255) UNIQUE | Email |
| `hashed_password` | VARCHAR(255) | bcrypt хеш |
| `name` | VARCHAR(100) | Имя |
| `role` | VARCHAR(50) | user, admin |
| `is_active` | BOOLEAN | Активен? |
| `created_at` | TIMESTAMP | Дата регистрации |

---

## 6. API ENDPOINTS

| Метод | Путь | Описание | Аутентификация |
|---|---|---|---|
| GET | `/health` | Health check + DB status | Нет |
| GET | `/api/properties` | Список с фильтрами и пагинацией | Нет |
| GET | `/api/properties/{id}` | Детали объекта | Нет |
| GET | `/api/map-data` | Данные для карты (до 5000 точек) | Нет |
| GET | `/api/stats` | Агрегированная статистика | Нет |
| GET | `/api/scrape-logs` | Логи парсинга | Нет |
| POST | `/api/scrape/trigger` | Ручной запуск скрейпинга | API Key |
| POST | `/api/auth/register` | Регистрация | Нет |
| POST | `/api/auth/login` | Вход (JWT) | Нет |

### Параметры `/api/properties`

| Параметр | Тип | По умолч. | Описание |
|---|---|---|---|
| `city` | string | — | Фильтр по городу (ilike) |
| `property_type` | string | — | apartment, house, land, commercial, room, garage |
| `status` | string | — | active, upcoming, completed, cancelled |
| `source` | string | — | torgi_gov, fedresurs, etp, cian |
| `price_min` | float | — | Мин. цена |
| `price_max` | float | — | Макс. цена |
| `area_min` | float | — | Мин. площадь |
| `area_max` | float | — | Макс. площадь |
| `discount_min` | float | — | Мин. скидка (%) |
| `has_coords` | bool | true | Только с координатами |
| `has_market_price` | bool | — | С рыночной оценкой |
| `date_from` | date | — | Дата от |
| `date_to` | date | — | Дата до |
| `sort_by` | string | publish_date | Сортировка |
| `sort_order` | string | desc | asc / desc |
| `page` | int | 1 | Номер страницы |
| `page_size` | int | 50 | Размер страницы (max 500) |

---

## 7. СКРЕЙПЕРЫ

### 7.1 TorgiGovScraper (основной источник)

- **Источник:** torgi.gov.ru (государственные торги)
- **Метод:** REST API (`/new/api/public/lotcards/search`)
- **Статус:** ✅ Рабочий (verified API parameters)
- **Антиблокировка:** Не нужна (государственный API)
- **Частота:** Каждые 6 часов
- **Регионы:** 88+ OKATO кодов (все регионы РФ)
- **Категории:** 9 типов (жилое, земля, коммерческое и т.д.)
- **Поля:** title, price, area, rooms, floor, city, status, dates

### 7.2 FedresursScraper (банкротные торги)

- **Источник:** bankrot.fedresurs.ru
- **Метод:** Playwright (SPA) → XHR interception → curl_cffi fallback
- **Статус:** 🟡 Требует тестирования на российском IP
- **Антиблокировка:** Playwright stealth, Tor SOCKS5
- **Особенность:** Angular SPA, данные через XHR

### 7.3 CianScraper (рыночная оценка)

- **Источник:** cian.ru
- **Метод:** curl_cffi → Playwright → __NEXT_DATA__ parsing
- **Статус:** 🟡 Частично рабочий (CIAN блокирует автоматизацию)
- **Антиблокировка:** TLS fingerprint, Tor, proxy rotation
- **Города:** 60+ городов РФ
- **Назначение:** Оценка market_price и discount_pct

### 7.4 EtpScraper (дополнительные площадки)

- **Источники:** lot-online.ru, fabrikant.ru, utender.ru, roseltorg.ru
- **Метод:** API discovery → HTML scraping
- **Статус:** 🟡 Требует тестирования
- **Назначение:** Дополнительные лоты, не вошедшие в torgi.gov.ru

### 7.5 ProxyManager

- **Авто-discovery:** Публичные SOCKS5 списки
- **Health-check:** Каждые 5 минут
- **Ротация:** Round-robin по healthy-прокси
- **Fallback:** Tor SOCKS5 → прямое подключение

---

## 8. PIPELINE ОБОГАЩЕНИЯ

```
Scrape (torgi.gov.ru, Fedresurs, ETP)
    ↓
UPSERT в PostgreSQL (source + source_id = уникальный ключ)
    ↓
Geocode (Yandex Geocoder API, batch 500, 0.5s delay)
    ↓
Market Estimate (CIAN, batch 100, IQR outlier removal)
    ↓
Cleanup ScrapeLog (TTL 90 дней)
```

---

## 9. ТЕСТЫ

### Покрытие: 51 тест, все проходят

| Модуль | Тесты | Статус |
|---|---|---|
| `test_models.py` | EnumString, AuctionProperty.to_dict, ScrapeLog | ✅ |
| `test_base_scraper.py` | _parse_price, _parse_date, throttle, retry | ✅ |
| `test_torgi_scraper.py` | _detect_property_type, _parse_lot_card, status_map | ✅ |
| `test_cian_scraper.py` | region_id, search_url, remove_outliers | ✅ |
| `test_proxy_manager.py` | load, round-robin, mark_bad/good | ✅ |
| `test_api_routes.py` | health, properties, map-data, stats, validation | ✅ |

### Запуск тестов

```bash
USE_SQLITE=true DEBUG=true python3 -m pytest tests/ -v
```

---

## 10. ДЕПЛОЙ

### 10.1 Frontend → GitHub Pages

- **URL:** https://smartmoneymoscow-cell.github.io/Nedvig-2/
- **Статус:** ✅ Работает
- **Данные:** Статические JSON (20 демо-записей)
- **Обновление:** `cd frontend && npm run build` → push to `gh-pages`

**Режимы работы frontend:**
- `VITE_API_URL` пустой → статический режим (читает из `static-api/`)
- `VITE_API_URL=https://...` → динамический режим (читает из API)

### 10.2 Backend → Render

- **Конфиг:** `render.yaml`
- **Статус:** ⏳ Ожидает деплоя
- **План:** Free tier (web + PostgreSQL)

**render.yaml:**
```yaml
services:
  - type: web
    name: nedvig-api
    runtime: docker
    region: oregon
    plan: free
    dockerfilePath: ./Dockerfile
    healthCheckPath: /health
    envVars:
      - DATABASE_URL (from database)
      - ADMIN_API_KEY (auto-generated)
      - JWT_SECRET (auto-generated)
      - CORS_ORIGINS: "https://smartmoneymoscow-cell.github.io"

databases:
  - name: nedvig-db
    plan: free
```

### 10.3 Локальная разработка

```bash
# Backend
pip install -r requirements.txt
USE_SQLITE=true uvicorn main:app --reload --port 8000

# Frontend
cd frontend && npm install && npm run dev

# Docker Compose (всё вместе)
docker-compose up -d

# Тесты
USE_SQLITE=true python3 -m pytest tests/ -v
```

---

## 11. КОНФИГУРАЦИЯ (ENV VARS)

| Переменная | Обязательна | По умолч. | Описание |
|---|---|---|---|
| `DATABASE_URL` | Да (prod) | — | PostgreSQL connection string |
| `DB_HOST` | Нет | localhost | Хост БД |
| `DB_PORT` | Нет | 5432 | Порт БД |
| `DB_NAME` | Нет | estate_auction | Имя БД |
| `DB_USER` | Нет | postgres | Пользователь БД |
| `DB_PASSWORD` | Нет | postgres | Пароль БД |
| `ADMIN_API_KEY` | Нет | (auto-gen) | Ключ для /api/scrape/trigger |
| `JWT_SECRET` | Нет | (auto-gen) | Секрет для JWT |
| `CORS_ORIGINS` | Нет | * | Разрешённые origins (через запятую) |
| `SCRAPER_WORKER_URL` | Нет | — | URL scraper worker для webhook |
| `SCRAPE_INTERVAL_HOURS` | Нет | 6 | Интервал автоскрейпинга |
| `USE_TOR` | Нет | false | Использовать Tor SOCKS5 |
| `YANDEX_MAPS_API_KEY` | Нет | — | Ключ Яндекс Геокодера |
| `USE_SQLITE` | Нет | false | SQLite вместо PostgreSQL |
| `DEBUG` | Нет | false | Режим отладки |

---

## 12. БЕЗОПАСНОСТЬ

| Мера | Статус | Описание |
|---|---|---|
| Rate Limiting | ✅ | 10 req/s general, 0.5 req/s scrape trigger |
| Security Headers | ✅ | X-Content-Type-Options, X-Frame-Options, XSS-Protection |
| CORS | ✅ | Whitelist origins |
| API Key Auth | ✅ | Bearer token для admin endpoints |
| JWT Auth | ✅ | Для пользовательских endpoints |
| SSL Verification | ✅ | verify=True в curl_cffi |
| Input Validation | ✅ | Pydantic валидация всех параметров |
| SQL Injection | ✅ | SQLAlchemy ORM (параметризованные запросы) |
| Timing-safe Compare | ✅ | secrets.compare_digest для API key |

---

## 13. ИЗВЕСТНЫЕ ОГРАНИЧЕНИЯ

| Проблема | Влияние | Решение |
|---|---|---|
| torgi.gov.ru блокирует нероссийские IP | Скрейпинг не работает из-за рубежа | Развёртывание на российском VPS |
| CIAN блокирует автоматизацию | Нет рыночной оценки | Avito / Яндекс.Недвижимость как fallback |
| Fedresurs — Angular SPA | Требует Playwright | XHR interception + DOM fallback |
| GitHub Pages — статика | Нет реального API | Render backend + CORS |
| Free tier Render | Спящий режим (cold start 30s) | Upgrade to paid ($7/мес) |

---

## 14. МЕТРИКИ ПРОЕКТА

| Метрика | Значение |
|---|---|
| Python файлов | 62 |
| TypeScript/TSX файлов | 10 |
| Строк Python кода | ~10,000 |
| Строк TypeScript/CSS | ~1,100 |
| Тестов | 51 (все проходят) |
| Коммитов в ветке | 6 |
| Источников данных | 4 (torgi.gov.ru, Fedresurs, CIAN, ЭТП) |
| Городов CIAN | 60+ |
| OKATO регионов | 88+ |

---

## 15. ДОРОЖНАЯ КАРТА

### Фаза 1: MVP (текущий статус)
- [x] Frontend на GH Pages с картой
- [x] Скрейперы (структура + код)
- [x] API endpoints
- [x] Тесты (51)
- [ ] Backend на Render

### Фаза 2: Живые данные
- [ ] Реальный скрейпинг torgi.gov.ru
- [ ] Geocoding через Yandex API
- [ ] CIAN market estimation
- [ ] Автообновление каждые 6 часов

### Фаза 3: Продвинутые функции
- [ ] Пользовательская авторизация
- [ ] Избранные лоты
- [ ] Уведомления о новых лотах
- [ ] Расширенная аналитика
- [ ] Экспорт в CSV/Excel

### Фаза 4: Production
- [ ] Мониторинг (Prometheus + Grafana)
- [ ] Логирование (ELK)
- [ ] CDN для frontend
- [ ] Rate limiting (Redis)
- [ ] Backup strategy
