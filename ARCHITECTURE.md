# 🏗 Архитектура сервиса «Торги по недвижимости»

## 1. Обзор

Сервис агрегирует данные о недвижимости на государственных торгах и торгах банкротов,
обогащает их рыночной оценкой и отображает на интерактивной карте.

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Пользователь                                │
│                    (браузер / мобильное приложение)                  │
└────────────────────────────┬────────────────────────────────────────┘
                             │ HTTPS
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    FastAPI Application (uvicorn)                     │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    Middleware                                 │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │   │
│  │  │ Rate Limiting │  │ CORS         │  │ Security Headers │  │   │
│  │  │ (10 req/s)    │  │              │  │ (X-Frame, XSS)   │  │   │
│  │  └──────────────┘  └──────────────┘  └──────────────────┘  │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    API Layer (api/routes.py)                  │   │
│  │  GET /health           — health check                       │   │
│  │  GET /api/properties    — список с фильтрами                │   │
│  │  GET /api/properties/:id — детали объекта                   │   │
│  │  GET /api/map-data      — оптимизированные данные для карты │   │
│  │  GET /api/stats         — агрегированная статистика         │   │
│  │  GET /api/scrape-logs   — логи парсинга                     │   │
│  │  POST /api/scrape/trigger — ручной запуск сбора (auth)      │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                  Services Layer                               │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │   │
│  │  │ Enrichment    │  │ Geocoder     │  │ Scheduler        │  │   │
│  │  │ Service       │  │ (Yandex API) │  │ (APScheduler)    │  │   │
│  │  │ (async-safe)  │  │              │  │                  │  │   │
│  │  └──────────────┘  └──────────────┘  └──────────────────┘  │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                  Scrapers Layer                               │   │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────────────┐    │   │
│  │  │ TorgiGov    │  │ Fedresurs  │  │ CIAN               │    │   │
│  │  │ Scraper     │  │ Scraper    │  │ Scraper            │    │   │
│  │  │ (verified   │  │ (Playwright│  │ (market price)     │    │   │
│  │  │  API)       │  │  + httpx)  │  │                    │    │   │
│  │  └──────┬─────┘  └──────┬─────┘  └─────────┬──────────┘    │   │
│  │         │               │                   │                │   │
│  │  ┌──────┴───────────────┴───────────────────┴──────────┐    │   │
│  │  │           Anti-Detection Layer                        │    │   │
│  │  │  ┌─────────────┐  ┌──────────┐  ┌────────────────┐  │    │   │
│  │  │  │ProxyManager  │  │curl_cffi │  │ Playwright     │  │    │   │
│  │  │  │(rotation,    │  │(TLS      │  │ (JS rendering, │  │    │   │
│  │  │  │ health-check)│  │fingerpr.)│  │  stealth)      │  │    │   │
│  │  │  └─────────────┘  └──────────┘  └────────────────┘  │    │   │
│  │  └──────────────────────────────────────────────────────┘    │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │               Data Layer (SQLAlchemy ORM)                     │   │
│  │  ┌──────────────────┐  ┌──────────────────────────────────┐ │   │
│  │  │ AuctionProperty   │  │ ScrapeLog                        │ │   │
│  │  │ (основная модель) │  │ (логи парсинга)                  │ │   │
│  │  └──────────────────┘  └──────────────────────────────────┘ │   │
│  └─────────────────────────────────────────────────────────────┘   │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             ▼
┌──────────────────────┐  ┌──────────────────────────────────────────┐
│   PostgreSQL 16       │  │        Внешние API                       │
│   (основная БД)       │  │  ┌──────────────┐  ┌─────────────────┐  │
│   - auction_properties│  │  │ Yandex Maps  │  │ Yandex Geocoder │  │
│   - scrape_logs       │  │  │ API          │  │ API             │  │
│   - индексы           │  │  └──────────────┘  └─────────────────┘  │
└──────────────────────┘  └──────────────────────────────────────────┘
```

---

## 2. Слои архитектуры

### 2.1 Middleware Layer

#### Rate Limiting
```
RateLimiter (in-memory)
├── General: 10 requests/second per IP
├── Scrape trigger: 0.5 requests/second per IP
├── Cleanup: every 60 seconds
└── Response: 429 Too Many Requests + Retry-After header
```

#### Security Headers
```
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
X-XSS-Protection: 1; mode=block
Referrer-Policy: strict-origin-when-cross-origin
```

#### CORS
- Configurable via `CORS_ORIGINS` env var
- Default: `*` (open)
- Methods: GET, POST

#### Authentication
```
POST /api/scrape/trigger
├── Header: Authorization: Bearer <API_KEY>
├── Or query param: ?api_key=<API_KEY>
├── Uses secrets.compare_digest (timing-safe)
└── No key configured = open access (dev mode)
```

### 2.2 API Layer

```
GET /api/properties
├── Query params: city, property_type, status, source,
│                 price_min, price_max, area_min, area_max,
│                 has_coords, has_market_price,
│                 date_from, date_to, sort_by, sort_order,
│                 page, page_size
├── sort_by: whitelist validated (publish_date, start_price, etc.)
├── sort_order: validated (asc/desc only)
├── property_type/status/source: validated against enum values
├── Response: { total, page, page_size, pages, items[] }
└── Max page_size: 500

GET /api/properties/{id}
└── Response: AuctionProperty.to_dict()

GET /api/map-data
├── Query params: city, property_type, status, days
├── Response: [{ id, lat, lon, title, price, market_price,
│                discount_pct, area, rooms, status, type,
│                publish_date, source, url }]
└── Limit: 5000 objects

GET /api/stats
└── Response: { total, by_source, by_status, avg_discount,
                top_cities[] }

GET /api/scrape-logs?limit=20
└── Response: [{ id, source, started_at, finished_at,
                 items_found, items_new, items_updated, status }]

POST /api/scrape/trigger (auth required)
└── Response: { status: "started" }

GET /health
└── Response: { status: "ok", version: "1.0.0" }
```

### 2.3 Services Layer

#### EnrichmentService (async-safe оркестратор)

```
run_full_pipeline()
│
├── Step 1: TorgiGovScraper (asyncio.to_thread)
│   ├── Verified API: /new/api/public/lotcards/search
│   ├── Params: lotStatus=PUBLISHED,APPLICATIONS_SUBMISSION,DETERMINING_WINNER
│   │           byFirstVersion=true, withFacets=true
│   │           dynSubjRF={region_code}, text={search_text}
│   └── UPSERT в auction_properties
│
├── Step 2: FedresursScraper (asyncio.to_thread)
│   ├── Playwright (JS rendering for SPA)
│   ├── httpx fallback (API endpoints)
│   ├── HTML scraping fallback
│   └── UPSERT в auction_properties
│
├── Step 3: EtpScraper (asyncio.to_thread)
│   ├── lot-online.ru, fabrikant.ru
│   └── UPSERT в auction_properties
│
├── Step 4: Geocoder (async, batch=200)
│   ├── SELECT WHERE is_geocoded = false LIMIT 200
│   ├── Yandex Geocoder API (0.5s delay)
│   └── UPDATE latitude, longitude, is_geocoded
│
└── Step 5: CianScraper (asyncio.to_thread, batch=50)
    ├── SELECT WHERE is_market_appraised = false LIMIT 50
    ├── curl_cffi → Playwright fallback
    ├── IQR outlier removal
    └── UPDATE market_price, discount_pct
```

#### Geocoder
- API: Яндекс Геокодер (`https://geocode-maps.yandex.ru/1.x`)
- Кэш: in-memory dict (адрес → координаты)
- Rate limit: 0.5s между запросами
- Пакетная обработка: до 200 адресов за запуск

### 2.4 Scrapers Layer

#### Антиблокировка (общая для всех скрейперов)

```
BaseScraper
├── curl_cffi (impersonate="chrome120")
│   └── TLS fingerprint = Chrome 120 (обходит JA3-детект)
├── Playwright (fallback для сложных anti-bot)
│   ├── Stealth overrides (webdriver, plugins, languages)
│   ├── headless Chromium
│   └── JS rendering для SPA-сайтов
├── ProxyManager
│   ├── Ротация: round-robin по healthy-прокси
│   ├── Health-check: каждые 5 мин (httpbin.org/ip)
│   ├── Mark bad/good: динамическое исключение/восстановление
│   └── Форматы: HTTP, HTTPS, SOCKS5
├── User-Agent
│   └── fake-useragent: рандомный реальный UA
├── Headers
│   └── Accept, Accept-Language (ru-RU), Sec-Fetch-*, DNT
├── Throttling
│   └── Рандомная задержка 2-8s между запросами
└── Retry
    └── tenacity: 3 попытки, exponential backoff (5-60s)
```

#### TorgiGovScraper (verified API)

```
Входные данные:
├── region_code (OKATO, "77" = Москва)
├── search_text (опционально)
├── days_back (30)
└── max_pages (100)

Pipeline:
├── API endpoint: /new/api/public/lotcards/search
│   ├── Параметры (verified):
│   │   ├── lotStatus=PUBLISHED,APPLICATIONS_SUBMISSION,DETERMINING_WINNER
│   │   ├── byFirstVersion=true
│   │   ├── withFacets=true
│   │   ├── size={page_size} (max 100)
│   │   ├── sort=firstVersionPublicationDate,desc
│   │   ├── page={page_number}
│   │   ├── dynSubjRF={region_code} (optional)
│   │   ├── text={search_text} (optional)
│   │   └── catCode={category_code} (optional)
│   ├── Ответ: JSON { content: [...], totalPages, totalElements }
│   └── Парсинг: _parse_lot_card()
│
Парсинг лота:
├── source_id: id
├── title: lotName
├── address: lotName (contains full address)
├── start_price: priceMin || startPrice
├── total_area: characteristics[totalAreaRealty] || characteristics[SquareZU]
├── rooms: regex from title (\d+)-комн
├── floor: regex from characteristics[locationObjectRealty]
├── total_floors: characteristics[numberFloors]
├── auction_status: lotStatus → STATUS_MAP
├── publish_date: noticeFirstVersionPublicationDate
├── auction_date_end: biddEndTime
└── price_per_sqm: start_price / total_area
```

#### FedresursScraper (bankruptcy auctions)

```
Pipeline:
├── 1. Playwright (primary — SPA site)
│   ├── Navigate to bankrot.fedresurs.ru/TradeList
│   ├── Stealth overrides (navigator.webdriver)
│   ├── Extract cards from DOM
│   └── Pagination via next button
│
├── 2. httpx fallback (API endpoints)
│   ├── Try: /api/v1/trades, /api/trades/search
│   └── Parse JSON response
│
└── 3. HTML scraping fallback
    ├── BeautifulSoup
    ├── Look for embedded JSON
    └── Parse visible cards
```

#### CianScraper (market price estimation)

```
Pipeline:
├── 1. curl_cffi (primary)
│   ├── Build URL: cian.ru/cat.php?engine_version=2&region={id}&...
│   ├── Area filter: ±30% of target area
│   └── Parse HTML for price/area pairs
│
├── 2. Playwright fallback (anti-bot bypass)
│   ├── Same URL
│   ├── Wait for networkidle
│   └── Parse rendered HTML
│
└── Processing:
    ├── Extract price/area from cards
    ├── Extract from embedded JSON (__NEXT_DATA__)
    ├── IQR outlier removal
    └── avg_price_per_sqm × total_area → market_price
```

### 2.5 Data Layer

#### Модель: AuctionProperty

```
auction_properties
├── id              SERIAL PRIMARY KEY
├── source          VARCHAR(50)     -- torgi_gov|gosplan|fedresurs|etp
├── source_id       VARCHAR(255)    -- ID в источнике
├── source_url      TEXT            -- Ссылка на лот
│
├── title           TEXT
├── description     TEXT
├── property_type   VARCHAR(50)     -- apartment|house|land|commercial|room|garage
│
├── address         TEXT
├── region          VARCHAR(255)
├── city            VARCHAR(255)
├── latitude        FLOAT
├── longitude       FLOAT
│
├── total_area      FLOAT           -- м²
├── living_area     FLOAT
├── rooms           INTEGER
├── floor           INTEGER
├── total_floors    INTEGER
│
├── start_price     FLOAT
├── current_price   FLOAT
├── market_price    FLOAT           -- CIAN estimation
├── price_per_sqm   FLOAT
├── discount_pct    FLOAT           -- (1 - auction/market) × 100
│
├── auction_status  VARCHAR(50)     -- active|upcoming|completed|cancelled
├── auction_date_start  TIMESTAMP
├── auction_date_end    TIMESTAMP
├── publish_date    DATE
├── lot_number      VARCHAR(100)
├── organizer       TEXT
├── bid_step        FLOAT
├── deposit         FLOAT
│
├── raw_data        JSON
├── created_at      TIMESTAMP
├── updated_at      TIMESTAMP
├── is_geocoded     BOOLEAN
└── is_market_appraised BOOLEAN

Индексы:
├── ix_source_source_id  UNIQUE (source, source_id)
├── ix_publish_date      (publish_date)
├── ix_city_property_type (city, property_type)
├── ix_auction_status    (auction_status)
└── ix_coords            (latitude, longitude)
```

---

## 3. Потоки данных

### 3.1 Основной pipeline (каждые 6 часов, async-safe)

```
[Cron/Trigger]
     │
     ▼
┌─────────────────────────────────────────────────────┐
│     EnrichmentService.run_full_pipeline()            │
│     (все скрейперы через asyncio.to_thread)          │
│                                                      │
│  Phase 1: Сбор данных                                │
│  torgi.gov.ru ──┐                                    │
│  Fedresurs ─────┼──→ UPSERT в PostgreSQL             │
│  ЭТП ───────────┘                                    │
│                                                      │
│  Phase 2: Геокодирование (batch=200, async)          │
│  Yandex Geocoder API → lat, lon                      │
│                                                      │
│  Phase 3: Рыночная оценка (batch=50, to_thread)      │
│  CIAN → avg price/м² → market_price, discount_pct    │
└─────────────────────────────────────────────────────┘
```

---

## 4. Инфраструктура

### 4.1 Docker Compose

```
┌──────────────────────────────────────────────────────┐
│                   docker-compose.yml                  │
│                                                       │
│  ┌─────────────────┐    ┌──────────────────────────┐ │
│  │ postgres:16      │    │ app (Python 3.12)        │ │
│  │ -alpine          │◄───│                          │ │
│  │                  │    │ FastAPI + uvicorn         │ │
│  │ Port: 5432       │    │ Port: 8000                │ │
│  │ Volume: pgdata   │    │                          │ │
│  │ Health: pgready  │    │ depends_on: postgres      │ │
│  └─────────────────┘    └──────────────────────────┘ │
│                                                       │
│  Env vars: DB_*, YANDEX_MAPS_API_KEY, PROXY_LIST,    │
│            ADMIN_API_KEY, CORS_ORIGINS, DEBUG          │
└──────────────────────────────────────────────────────┘
```

---

## 5. Безопасность

| Угроза | Мера |
|--------|------|
| SQL-инъекции | SQLAlchemy ORM (параметризованные запросы) |
| XSS | Jinja2 auto-escaping, X-XSS-Protection header |
| CSRF | SameSite cookies, проверка Origin |
| Rate limiting | In-memory RateLimiter (10 req/s API, 0.5 req/s scrape) |
| Auth | API key для admin endpoints (secrets.compare_digest) |
| Input validation | sort_by whitelist, enum validation |
| Scraping detection | TLS fingerprint + Playwright + proxy rotation |
| Data leak | Нет PII, публичные данные торгов |

---

## 6. Roadmap

### Phase 1: MVP ✅
- [x] Парсинг torgi.gov.ru (verified API)
- [x] Fedresurs scraper (bankruptcy auctions)
- [x] CIAN market price estimation (curl_cffi + Playwright)
- [x] Яндекс.Карта с цветовой маркировкой
- [x] Rate limiting + security headers
- [x] Admin API key auth
- [x] Async-safe pipeline
- [x] 75 тестов

### Phase 2: Production Ready
- [ ] Nginx reverse proxy + SSL
- [ ] Celery для фоновых задач
- [ ] Redis кэш для map-data
- [ ] JWT авторизация
- [ ] Email/Telegram уведомления
