# 🏗 Архитектура сервиса «Торги по недвижимости»

## 1. Обзор

Сервис агрегирует данные о недвижимости на государственных торгах, обогащает их рыночной оценкой и отображает на интерактивной карте.

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Пользователь                                │
│                    (браузер / мобильное приложение)                  │
└────────────────────────────┬────────────────────────────────────────┘
                             │ HTTPS
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      Nginx (reverse proxy)                          │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────────────────┐  │
│  │ Статика       │  │ API прокси   │  │ SSL termination          │  │
│  │ (CSS/JS/IMG)  │  │ → uvicorn    │  │ Rate limiting            │  │
│  └──────────────┘  └──────────────┘  │ Gzip compression          │  │
│                                       └───────────────────────────┘  │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    FastAPI Application (uvicorn)                     │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    API Layer (api/routes.py)                  │   │
│  │  GET /api/properties    — список с фильтрами                │   │
│  │  GET /api/properties/:id — детали объекта                   │   │
│  │  GET /api/map-data      — оптимизированные данные для карты │   │
│  │  GET /api/stats         — агрегированная статистика         │   │
│  │  GET /api/scrape-logs   — логи парсинга                     │   │
│  │  POST /api/scrape/trigger — ручной запуск сбора             │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                  Services Layer                               │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐   │   │
│  │  │ Enrichment    │  │ Geocoder     │  │ Scheduler        │   │   │
│  │  │ Service       │  │ (Yandex API) │  │ (APScheduler)    │   │   │
│  │  │ (оркестратор) │  │              │  │                  │   │   │
│  │  └──────────────┘  └──────────────┘  └──────────────────┘   │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                  Scrapers Layer                               │   │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────────────┐     │   │
│  │  │ TorgiGov    │  │ GosPlan    │  │ CIAN               │     │   │
│  │  │ Scraper     │  │ Scraper    │  │ Scraper            │     │   │
│  │  │ (API+HTML)  │  │ (API+HTML) │  │ (market price)     │     │   │
│  │  └──────┬─────┘  └──────┬─────┘  └─────────┬──────────┘     │   │
│  │         │               │                   │                │   │
│  │  ┌──────┴───────────────┴───────────────────┴──────────┐     │   │
│  │  │           Anti-Detection Layer                        │     │   │
│  │  │  ┌─────────────┐  ┌──────────┐  ┌────────────────┐  │     │   │
│  │  │  │ProxyManager  │  │curl_cffi │  │ User-Agent     │  │     │   │
│  │  │  │(rotation,    │  │(TLS      │  │ Rotation       │  │     │   │
│  │  │  │ health-check)│  │fingerpr.)│  │ (fake-ua)      │  │     │   │
│  │  │  └─────────────┘  └──────────┘  └────────────────┘  │     │   │
│  │  └──────────────────────────────────────────────────────┘     │   │
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
│   - WAL mode          │  └──────────────────────────────────────────┘
└──────────────────────┘
```

---

## 2. Слои архитектуры

### 2.1 Presentation Layer (фронтенд)

| Компонент | Технология | Назначение |
|-----------|-----------|------------|
| Карта | Яндекс.Карты JS API 2.1 | Отображение объектов с кластеризацией |
| UI | Vanilla JS + CSS | Фильтры, легенда, панель деталей |
| Шаблоны | Jinja2 | Server-side rendering HTML |

**Цветовая маркировка** (дата публикации):
```
Сегодня      → #e74c3c (красный)
1-3 дня      → #e67e22 (оранжевый)
4-7 дней     → #f1c40f (жёлтый)
2-4 недели   → #2ecc71 (зелёный)
1-3 месяца   → #3498db (синий)
3+ месяцев   → #9b59b6 (фиолетовый)
```

**Кластеризация**: `ymaps.Clusterer` с автоматической группировкой при зуме < 12.

**Балуны**: HTML-шаблон с ценой, рыночной оценкой, скидкой, ссылкой на источник.

### 2.2 API Layer

```
GET /api/properties
├── Query params: city, property_type, status, source,
│                 price_min, price_max, area_min, area_max,
│                 has_coords, has_market_price,
│                 date_from, date_to, sort_by, sort_order,
│                 page, page_size
├── Response: { total, page, page_size, pages, items[] }
└── Max page_size: 500

GET /api/properties/{id}
└── Response: AuctionProperty.to_dict()

GET /api/map-data
├── Query params: city, property_type, status, days
├── Response: [{ id, lat, lon, title, price, market_price,
│                discount_pct, area, rooms, status, type,
│                publish_date, source, url }]
└── Limit: 5000 objects (оптимизация для карты)

GET /api/stats
└── Response: { total, by_source, by_status, avg_discount,
                top_cities[] }

GET /api/scrape-logs?limit=20
└── Response: [{ id, source, started_at, finished_at,
                 items_found, items_new, items_updated, status }]

POST /api/scrape/trigger
└── Response: { status: "started" }
```

**Rate limiting**: через Nginx (10 req/s per IP для API, 2 req/s для scrape/trigger).

### 2.3 Services Layer

#### EnrichmentService (оркестратор)

```
run_full_pipeline()
│
├── Step 1a: TorgiGovScraper.scrape_listings()
│   ├── API-запрос → парсинг JSON
│   ├── Fallback: HTML scraping
│   └── UPSERT в auction_properties
│
├── Step 1b: GosPlanScraper.scrape_listings()
│   ├── API-запрос → парсинг JSON
│   ├── Fallback: HTML scraping
│   └── UPSERT в auction_properties
│
├── Step 2: Geocoder.batch_geocode()
│   ├── SELECT WHERE is_geocoded = false LIMIT 100
│   ├── Yandex Geocoder API (0.5s delay)
│   └── UPDATE latitude, longitude, is_geocoded
│
└── Step 3: CianScraper.batch_estimate()
    ├── SELECT WHERE is_market_appraised = false LIMIT 20
    ├── CIAN API → поиск сопоставимых объектов
    ├── Усреднение цены/м², отбрасывание выбросов
    └── UPDATE market_price, discount_pct, is_market_appraised
```

#### Geocoder

- API: Яндекс Геокодер (`https://geocode-maps.yandex.ru/1.x`)
- Кэш: in-memory dict (адрес → координаты)
- Rate limit: 0.5s между запросами
- Пакетная обработка: до 100 адресов за запуск

#### Планировщик (APScheduler)

```
┌────────────────────────────────────────┐
│         AsyncIOScheduler               │
│                                        │
│  ┌──────────────────────────────────┐  │
│  │ Job: main_scrape                  │  │
│  │ Trigger: interval (6h)            │  │
│  │ Target: enrichment_service        │  │
│  │   .run_full_pipeline()            │  │
│  └──────────────────────────────────┘  │
│                                        │
│  (расширяемо: добавить jobs для        │
│   геокодирования, переоценки и т.д.)   │
└────────────────────────────────────────┘
```

### 2.4 Scrapers Layer

#### Антиблокировка (общая для всех скрейперов)

```
BaseScraper
├── curl_cffi (impersonate="chrome120")
│   └── TLS fingerprint = Chrome 120 (обходит JA3-детект)
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

#### TorgiGovScraper

```
Входные данные:
├── region_code (OKATO, "77" = Москва)
├── days_back (30)
└── max_pages (50)

Pipeline:
├── 1. API endpoint: /new/api/public/lotcards/search
│   ├── Параметры: region, lotPropertyType=2, publishDateFrom, page
│   ├── Ответ: JSON { content: [...] }
│   └── Парсинг: _parse_lot_card()
│
├── 2. Fallback: HTML scraping
│   ├── URL: /new/public/lots/reg?page=N
│   ├── Селекторы: .lot-card, .lotItem, tr.lot-row
│   └── BeautifulSoup + lxml
│
└── 3. Детали лота (опционально)
    └── API: /new/api/public/lotcards/{lotId}

Парсинг лота:
├── source_id: lotId / lotNumber
├── title: lotName
├── address: lotAddress
├── start_price: startPrice (float)
├── total_area: totalArea (float)
├── publish_date: publishDate (DD.MM.YYYY)
├── auction_date_start: biddingStartDate (DD.MM.YYYY HH:MM)
├── auction_status: lotStatus → enum
├── property_type: _detect_property_type(title + description)
└── price_per_sqm: start_price / total_area
```

#### GosPlanScraper

```
Входные данные:
├── city (опционально)
├── days_back (30)
└── max_pages (50)

Pipeline:
├── 1. API: /api/v1/lots?page=N&type=real_estate
│   └── Парсинг: _parse_listing()
├── 2. Fallback: HTML scraping
│   └── Селекторы: .lot-card, .auction-card, .property-card
└── Аналогичная структура данных
```

#### CianScraper (рыночная оценка)

```
Входные данные (от EnrichmentService):
├── city: str
├── property_type: PropertyType
├── rooms: int
├── total_area: float
└── address: str

Pipeline:
├── 1. API: POST api.cian.ru/search-offers/v2/search-offers-desktop/
│   ├── Payload: { jsonQuery: { _type, geo, room, total_area±30% } }
│   ├── Ответ: { data: { offersSerialized: [...] } }
│   ├── Сбор цен за м² из 20 сопоставимых
│   ├── Отбрасывание выбросов (первый + последний квартиль)
│   └── Усреднение → price_per_sqm
│
├── 2. Fallback: HTML scraping
│   ├── URL: cian.ru/prodam/kvartiry/?total_area[min]=X&total_area[max]=Y
│   ├── Селекторы: [data-name='Price'], .price, span[data-mark='MainPrice']
│   └── Парсинг цен из текста ("12 500 000 ₽")
│
└── Выходные данные:
    ├── market_price: avg_price_per_sqm × total_area
    ├── price_per_sqm: float
    └── comparable_count: int
```

### 2.5 Data Layer

#### Модель: AuctionProperty

```
auction_properties
├── id              SERIAL PRIMARY KEY
├── source          VARCHAR(50)     -- 'torgi_gov' | 'gosplan'
├── source_id       VARCHAR(255)    -- ID в источнике
├── source_url      TEXT            -- Ссылка на лот
│
├── title           TEXT            -- Название
├── description     TEXT            -- Описание
├── property_type   VARCHAR(50)     -- apartment|house|land|...
│
├── address         TEXT            -- Адрес
├── region          VARCHAR(255)    -- Регион
├── city            VARCHAR(255)    -- Город
├── latitude        FLOAT           -- Широта
├── longitude       FLOAT           -- Долгота
│
├── total_area      FLOAT           -- Площадь общая (м²)
├── living_area     FLOAT           -- Площадь жилая (м²)
├── rooms           INTEGER         -- Комнат
├── floor           INTEGER         -- Этаж
├── total_floors    INTEGER         -- Этажность
│
├── start_price     FLOAT           -- Начальная цена
├── current_price   FLOAT           -- Текущая цена
├── market_price    FLOAT           -- Рыночная оценка (ЦИАН)
├── price_per_sqm   FLOAT           -- Цена за м²
├── discount_pct    FLOAT           -- Скидка от рынка (%)
│
├── auction_status  VARCHAR(50)     -- active|upcoming|completed|cancelled
├── auction_date_start  TIMESTAMP  -- Начало торгов
├── auction_date_end    TIMESTAMP  -- Конец торгов
├── publish_date    DATE            -- Дата публикации
├── lot_number      VARCHAR(100)    -- Номер лота
├── organizer       TEXT            -- Организатор
├── bid_step        FLOAT           -- Шаг торгов
├── deposit         FLOAT           -- Задаток
│
├── raw_data        JSON            -- Исходные данные (для отладки)
├── created_at      TIMESTAMP       -- Создание записи
├── updated_at      TIMESTAMP       -- Обновление записи
├── is_geocoded     BOOLEAN         -- Геокодирован?
└── is_market_appraised BOOLEAN     -- Оценён?

Индексы:
├── ix_source_source_id  UNIQUE (source, source_id)
├── ix_publish_date      (publish_date)
├── ix_city_property_type (city, property_type)
├── ix_auction_status    (auction_status)
└── ix_coords            (latitude, longitude)
```

#### Модель: ScrapeLog

```
scrape_logs
├── id              SERIAL PRIMARY KEY
├── source          VARCHAR(50)
├── started_at      TIMESTAMP
├── finished_at     TIMESTAMP
├── items_found     INTEGER
├── items_new       INTEGER
├── items_updated   INTEGER
├── errors          TEXT
├── status          VARCHAR(50)     -- running|success|error
└── proxy_used      VARCHAR(500)
```

#### EnumString TypeDecorator

Кросс-БД совместимость (SQLite + PostgreSQL):
```python
class EnumString(TypeDecorator):
    """Хранит Python enum как строку. Работает в SQLite и PostgreSQL."""
    impl = String
    def process_bind_param(self, value, dialect):
        return value.value if isinstance(value, enum.Enum) else value
    def process_result_value(self, value, dialect):
        return self._enum_class(value)  # → обратно в enum
```

---

## 3. Потоки данных

### 3.1 Основной pipeline (каждые 6 часов)

```
[Cron/Trigger]
     │
     ▼
┌─────────────────────────────────────────────────────┐
│            EnrichmentService.run_full_pipeline()     │
│                                                      │
│  ┌─────────────────────────────────────────────┐    │
│  │ Phase 1: Сбор данных (scraping)              │    │
│  │                                               │    │
│  │  torgi.gov.ru ──┐                             │    │
│  │                  ├──→ UPSERT в PostgreSQL     │    │
│  │  ГосПлан ───────┘    (source + source_id)    │    │
│  └─────────────────────────────────────────────┘    │
│                      │                               │
│                      ▼                               │
│  ┌─────────────────────────────────────────────┐    │
│  │ Phase 2: Геокодирование                      │    │
│  │                                               │    │
│  │  SELECT WHERE is_geocoded = false             │    │
│  │       │                                       │    │
│  │       ▼                                       │    │
│  │  Yandex Geocoder API                          │    │
│  │  (address → lat, lon)                         │    │
│  │       │                                       │    │
│  │       ▼                                       │    │
│  │  UPDATE is_geocoded = true                    │    │
│  └─────────────────────────────────────────────┘    │
│                      │                               │
│                      ▼                               │
│  ┌─────────────────────────────────────────────┐    │
│  │ Phase 3: Рыночная оценка                     │    │
│  │                                               │    │
│  │  SELECT WHERE is_market_appraised = false     │    │
│  │       │                                       │    │
│  │       ▼                                       │    │
│  │  CIAN API (поиск сопоставимых)                │    │
│  │  (город + тип + площадь ±30%)                 │    │
│  │       │                                       │    │
│  │       ▼                                       │    │
│  │  Усреднение price/м² → market_price           │    │
│  │  discount_pct = (1 - auction/market) × 100    │    │
│  │       │                                       │    │
│  │       ▼                                       │    │
│  │  UPDATE market_price, discount_pct            │    │
│  └─────────────────────────────────────────────┘    │
│                                                      │
│  ┌─────────────────────────────────────────────┐    │
│  │ Phase 4: Логирование                         │    │
│  │                                               │    │
│  │  ScrapeLog: source, items_found/new/updated,  │    │
│  │             status, errors, proxy_used         │    │
│  └─────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────┘
```

### 3.2 Запрос данных (пользователь)

```
[Браузер]
     │
     ▼
GET /api/map-data?city=Москва&days=30
     │
     ▼
┌─────────────────────────────────────────┐
│ SQL: SELECT id, lat, lon, title, price, │
│      market_price, discount_pct, ...    │
│ FROM auction_properties                 │
│ WHERE city ILIKE '%Москва%'             │
│   AND latitude IS NOT NULL              │
│   AND publish_date >= (today - 30d)     │
│ ORDER BY publish_date DESC              │
│ LIMIT 5000                              │
└──────────────────┬──────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────┐
│ JSON Response → JS                       │
│                                           │
│ for each property:                        │
│   color = getColorByDate(publish_date)    │
│   marker = new ymaps.Placemark(           │
│     [lat, lon], balloonContent, style     │
│   )                                       │
│   clusterer.add(marker)                   │
│                                           │
│ map.setBounds(clusterer.getBounds())      │
└─────────────────────────────────────────┘
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
│  Volumes: pgdata (персистентное хранилище БД)         │
└──────────────────────────────────────────────────────┘
```

### 4.2 Окружения

| Окружение | БД | Прокси | API ключи | Запуск |
|-----------|-----|--------|-----------|--------|
| **Dev** | SQLite | Нет | Опционально | `uvicorn --reload` |
| **Staging** | PostgreSQL | Тестовые | Все | `docker-compose` |
| **Production** | PostgreSQL | Боевые | Все | `docker-compose` + Nginx |

### 4.3 Production (Nginx)

```
                        ┌─────────────────────┐
   Internet ────────────│    Nginx            │
   (443/HTTPS)          │  ┌───────────────┐  │
                        │  │ SSL (Let's    │  │
                        │  │ Encrypt)      │  │
                        │  └───────┬───────┘  │
                        │          │          │
                        │  ┌───────▼───────┐  │
                        │  │ Rate Limiting │  │
                        │  │ 10 req/s API  │  │
                        │  │ 2 req/s scrape│  │
                        │  └───────┬───────┘  │
                        │          │          │
                        │  ┌───────▼───────┐  │
                        │  │ Static files  │──│──→ /static (CSS/JS)
                        │  └───────┬───────┘  │
                        │          │          │
                        │  ┌───────▼───────┐  │
                        │  │ Proxy pass    │──│──→ uvicorn :8000
                        │  └───────────────┘  │
                        └─────────────────────┘
```

---

## 5. Безопасность

| Угроза | Мера |
|--------|------|
| SQL-инъекции | SQLAlchemy ORM (параметризованные запросы) |
| XSS | Jinja2 auto-escaping, CSP headers |
| CSRF | SameSite cookies, проверка Origin |
| Rate limiting | Nginx limit_req |
| Scraping detection | TLS fingerprint, proxy rotation, delays |
| Data leak | Нет PII, публичные данные торгов |
| API abuse | Rate limiting + pagination limits |

---

## 6. Масштабирование

### 6.1 Горизонтальное

```
Phase 1 (текущий):
  1 сервер, SQLite/PostgreSQL, монолит

Phase 2 (10k+ объектов):
  Docker Compose: PostgreSQL + Nginx + uvicorn (1 replica)

Phase 3 (100k+ объектов, высокий трафик):
  ├── PostgreSQL: репликация (read replica для API)
  ├── uvicorn: 2-4 workers (gunicorn)
  ├── Celery/RQ: отдельные воркеры для парсинга
  ├── Redis: кэш для map-data (TTL 5 min)
  └── CDN: статические файлы

Phase 4 (1M+ объектов):
  ├── PostgreSQL: партиционирование по city/region
  ├── Elasticsearch: полнотекстовый поиск
  ├── PostGIS: гео-запросы (вместо lat/lon фильтров)
  └── Kubernetes: авто-масштабирование
```

### 6.2 Вертикальное

| Метрика | Текущий лимит | Решение |
|---------|-------------|---------|
| Объектов в БД | ~100k (SQLite) | PostgreSQL |
| Запросов/сек | ~50 (uvicorn) | gunicorn + workers |
| Парсинг/день | ~1000 лотов | Прокси-пул, параллелизм |
| Геокодирование | ~200/день (API лимит) | Кэш, batch processing |

---

## 7. Roadmap

### Phase 1: MVP (текущий) ✅
- [x] Парсинг torgi.gov.ru + ГосПлан
- [x] Рыночная оценка через ЦИАН
- [x] Яндекс.Карта с цветовой маркировкой
- [x] API для фильтрации и статистики
- [x] SQLite fallback для разработки
- [x] 73 теста

### Phase 2: Production Ready
- [ ] Alembic миграции (production PostgreSQL)
- [ ] Nginx reverse proxy + SSL
- [ ] Celery для фоновых задач парсинга
- [ ] Redis кэш для map-data
- [ ] Email-уведомления о новых лотах со скидкой > 20%
- [ ] Пагинация на фронтенде
- [ ] Сохранённые фильтры (localStorage)

### Phase 3: Расширенный функционал
- [ ] Авторизация (JWT)
- [ ] Избранные объекты
- [ ] Графики изменения цен
- [ ] PostGIS для гео-запросов
- [ ] Полный текстовый поиск (Elasticsearch)
- [ ] Telegram-бот для уведомлений
- [ ] Экспорт в Excel/CSV

### Phase 4: Масштабирование
- [ ] Kubernetes deployment
- [ ] Read replicas PostgreSQL
- [ ] CDN для статики
- [ ] Rate limiting per user (JWT)
- [ ] A/B тестирование UI
- [ ] Мобильное приложение (React Native)
