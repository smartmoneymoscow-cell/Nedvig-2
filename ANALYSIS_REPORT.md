# 🏗 Nedvig-2 — Полный аудит проекта

## 1. Архитектура проекта

### Обзор

Проект «Estate Auction Tracker» — агрегатор торгов по недвижимости с рыночной оценкой и отображением на Яндекс.Картах. Монолитная архитектура на FastAPI.

```
Браузер → FastAPI (main.py) → PostgreSQL
              ↓
     ┌────────┼────────┐
     API    Шаблоны   APScheduler
     ↓                  ↓
  Services          Scrapers
  (Enrichment,      (TorgiGov,
   Geocoder)         Fedresurs,
                     CIAN, ETP)
```

### Слои

| Слоя | Файлы | Ответственность |
|------|-------|-----------------|
| **Entry point** | `main.py` | FastAPI app, middleware, lifespan, scheduler |
| **Config** | `config/settings.py` | Pydantic Settings, env vars |
| **Database** | `database.py`, `models.py` | SQLAlchemy ORM, engine, session |
| **API** | `api/routes.py` | REST endpoints (properties, map-data, stats, scrape-logs) |
| **Services** | `services/enrichment.py`, `services/geocoder.py` | Pipeline orchestration, geocoding |
| **Scrapers** | `scrapers/*.py` | Data collection from 4 sources |
| **Templates** | `templates/index.html` | Jinja2 main page (map + sidebar) |
| **Static** | `static/css/style.css`, `static/js/app.js` | Dark-theme CSS, map JS |
| **Migrations** | `alembic/` | DB schema versioning |
| **Tests** | `tests/` | 75 pytest tests |

---

## 2. Микросервисы

**Микросервисов нет.** Проект — монолит. Все компоненты (API, скрейпинг, геокодирование, оценка) запускаются в одном процессе.

### Рекомендации по декомпозиции (если потребуется масштабирование):

| Сервис | Задача | Технология |
|--------|--------|------------|
| **API Gateway** | REST API, авторизация | FastAPI |
| **Scraper Worker** | Парсинг в фоне | Celery + Redis |
| **Geocoder Worker** | Геокодирование | Celery + Redis |
| **CIAN Estimator** | Рыночная оценка | Celery + Redis |
| **Scheduler** | Периодические задачи | Celery Beat |

Сейчас всё это делает `APScheduler` внутри `main.py` — для MVP допустимо, но не для production.

---

## 3. Скрейперы

### 3.1 TorgiGovScraper — 🟢 Рабочий (с замечаниями)

**Источник:** torgi.gov.ru (государственные торги)
**Метод:** REST API (`/new/api/public/lotcards/search`)
**Статус:** Использует реальные параметры API (verified), корректный парсинг карточек.

**Плюсы:**
- Реальные параметры API (lotStatus, byFirstVersion, withFacets, dynSubjRF)
- Правильный маппинг статусов (PUBLISHED → UPCOMING, APPLICATIONS_SUBMISSION → ACTIVE)
- Извлечение характеристик по кодам (totalAreaRealty, numberFloors)
- Парсинг комнат из заголовка (regex)
- Поддержка пагинации

**Замечания:**
- `city` всегда `None` — нужно извлекать из `regionName`/`cityName` в ответе API
- Нет фильтрации по `days_back` — параметр передаётся, но не используется в API-запросе
- При ошибке на первой странице — break, на остальных — continue (асимметричная логика)

### 3.2 FedresursScraper — 🟡 Частично рабочий

**Источник:** bankrot.fedresurs.ru (банкротные торги)
**Метод:** Playwright (primary) → httpx (fallback) → HTML scraping (last resort)

**Плюсы:**
- Трёхуровневая стратегия fallback
- Stealth-плагины для Playwright
- Определение типа недвижимости по ключевым словам

**Проблемы:**
- CSS-селекторы для карточек — гипотетические (`.trade-card`, `.auction-item` и т.д.)
- API endpoints в fallback — не проверены (`/api/v1/trades`, `/api/trades/search`)
- Playwright устанавливается опционально — на Render не будет работать без `playwright install chromium`
- `_parse_playwright_card` использует generic селекторы, которые вряд ли совпадут с реальной вёрсткой

### 3.3 CianScraper — 🟡 Частично рабочий

**Источник:** cian.ru (рыночная оценка)
**Метод:** curl_cffi (primary) → Playwright (fallback)

**Плюсы:**
- IQR-фильтрация выбросов
- Попытка извлечения JSON из `__NEXT_DATA__`
- Пакетная обработка с ротацией сессий

**Проблемы:**
- CIAN активно блокирует автоматизацию — curl_cffi с TLS fingerprint может не пройти
- Селекторы карточек (`[data-name='OffersSerpItem']`) — могут быть устаревшими
- Нет обработки CAPTCHA/Challenge pages
- 10 запросов × 5 секунд = 50 секунд на batch — долго

### 3.4 EtpScraper — 🔴 Нерабочий

**Источник:** lot-online.ru, fabrikant.ru
**Метод:** HTML scraping

**Проблемы:**
- URL `/trades?category=real_estate&status=active` — не проверены
- CSS-селекторы — generic, не адаптированы под реальную вёрстку
- Скорее всего вернёт пустой список

### 3.5 ProxyManager — 🟢 Хорошо спроектирован

**Плюсы:**
- Авто-discovery прокси из публичных списков
- Health-check с mark_bad/mark_good
- Фильтрация по российским IP
- Thread-safe (Lock)
- Fallback на прямое подключение

---

## 4. Ошибки и избыточности кода

### 4.1 Дублирование логики PropertyType detection

**Файлы:** `torgi_scraper.py`, `fedresurs_scraper.py`, `etp_scraper.py`

Все три скрейпера имеют свой `_detect_property_type()` с похожей логикой. Нужно вынести в `base_scraper.py` или отдельный модуль.

### 4.2 Дублирование Playwright init

`CianScraper._init_playwright()` и `FedresursScraper._init_playwright()` — практически идентичный код. Нужен общий mixin или factory.

### 4.3 Дублирование UPSERT в enrichment.py

`_scrape_torgi()`, `_scrape_fedresurs()`, `_scrape_etp()` — одна и та же структура:
1. Создать ScrapeLog
2. Запустить скрейпер в thread
3. Вызвать `_upsert_listings()`
4. Обновить log_entry

Нужен generic метод `_run_scraper_pipeline(session, source_type, scraper_factory)`.

### 4.4 `session` vs `session_factory` неразбериха

В `enrichment.py` принимается `session: AsyncSession`, но `main.py` передаёт `async_session_factory()`. В `scheduled_scrape()`:
```python
async with async_session_factory() as session:
    await enrichment_service.run_full_pipeline(session)
    await session.commit()
```
А в `run_full_pipeline` каждый скрейпер добавляет в ту же сессию, но `commit` происходит только в конце. Если один скрейпер упадёт — откатятся все предыдущие.

### 4.5 `GOSPLAN` в enum, но нет GosPlanScraper

`SourceType.GOSPLAN` есть в `models.py`, но скрейпера для него нет (по SCRAPER_AUDIT.md он был заменён на Fedresurs). Это создаёт confusion:
- В UI фильтрах есть «ГосПлан»
- В stats запросах считается `gosplan` (всегда 0)
- В alembic migration — enum содержит `gosplan`, но не `fedresurs`/`etp`

### 4.6 Несовпадение enum в миграции и модели

**Alembic migration (001_initial.py):**
```python
op.execute("CREATE TYPE sourcetype AS ENUM ('torgi_gov', 'gosplan')")
```

**Model (models.py):**
```python
class SourceType(enum.Enum):
    TORGIGOV = "torgi_gov"
    GOSPLAN = "gosplan"
    FEDRESURS = "fedresurs"
    ETP = "etp"
```

Enum в БД не содержит `fedresurs` и `etp`! При попытке вставить запись с `source=fedresurs` — PostgreSQL вернёт ошибку enum constraint.

### 4.7 Hardcoded `verify=False` в curl_cffi

```python
session = curl_requests.Session(impersonate="chrome120", verify=False)
```
Отключение проверки SSL — security risk. В production должно быть `verify=True`.

### 4.8 `_get` возвращает `httpx.Response`, но curl_cffi возвращает другой тип

```python
def _get(self, url, params, **kwargs) -> httpx.Response:
    response = self._session.get(url, ...)  # curl_cffi response
    ...
    return response  # НЕ httpx.Response!
```
Type hint врёт. curl_cffi.response не совместим с httpx.Response.

---

## 5. Ошибки архитектуры

### 5.1 ScrapeLog не очищается

Таблица `scrape_logs` растёт бесконечно. Нет TTL, нет cleanup job. Через год — миллионы записей.

### 5.2 Нет retry для geocoding

Если Yandex Geocoder вернул ошибку, `is_geocoded` не ставится в `True` — объект будет обрабатываться снова и снова каждые 6 часов. Но если ошибка временная (rate limit) — это правильно. Нужна дифференциация: permanent failure → mark, temporary → retry.

### 5.3 Нет graceful shutdown для скрейперов

Если скрейпер работает 10 минут, а деплой происходит — `scheduler.shutdown(wait=False)` убьёт задачу немедленно. Данные могут быть потеряны (транзакция не committed).

### 5.4 APScheduler в одном процессе с uvicorn

При масштабировании на несколько workers — скрейпинг запустится N раз одновременно. Нужен distributed lock (Redis) или вынести в Celery.

### 5.5 In-memory Rate Limiter не работает при масштабировании

Каждый worker будет иметь свой лимитер. С 4 workers лимит фактически 40 req/s вместо 10.

### 5.6 Нет connection pooling для внешних API

Каждый запрос к Yandex Geocoder / CIAN создаёт новый `httpx.Client`. Нужен reuse или connection pool.

### 5.7 `CORS_ORIGINS: str = "*"` — небезопасно

Wildcard CORS в production = любой сайт может делать запросы к API. Должно быть whitelist.

### 5.8 `ADMIN_API_KEY` может быть пустым

Если не задан — scrape trigger endpoint открыт для всех. Это написано в коде:
```python
if not _admin_api_key:
    return True  # No key configured = open access (dev mode)
```
Нет предупреждения в логах при запуске в production без ключа.

---

## 6. Риски безопасности и план решения

### 🔴 Критические

| Риск | Описание | Решение |
|------|----------|---------|
| **Нет аутентификации пользователей** | Все API endpoints публичные | Добавить JWT auth (Phase 2 roadmap) |
| **SQL injection через ilike** | `f"%{city}%"` — хотя SQLAlchemy экранирует, wildcard `%` в начале обходит индексы | Использовать `textsearch` или параметризованный `contains` |
| **Hardcoded SECRET_KEY** | `"change-me-in-production"` в settings.py | Вынести в env, fail-fast если не задан |
| **`verify=False`** | SSL verification отключён для curl_cffi | Включить `verify=True` в production |
| **CORS `*`** | Любой origin может делать запросы | Ограничить конкретными доменами |

### 🟡 Важные

| Риск | Описание | Решение |
|------|----------|---------|
| **Rate limiter in-memory** | Не работает при масштабировании | Перенести в Redis |
| **Нет лимитов на scrape trigger** | Можно вызвать DoS на целевые сайты | Добавить глобальный lock + cooldown |
| **Playwright в контейнере** | Требует ~400MB для Chromium | Отдельный контейнер для scraping worker |
| **Логи содержат raw_data** | Потенциально чувствительные данные из API | Очистить raw_data перед сохранением |
| **Нет HTTPS** | Docker-compose exposing port 8000 без TLS | Добавить Nginx reverse proxy + Let's Encrypt |

### 🟢 Рекомендации

- Добавить `SECURITY.md` с описанием security policy
- Настроить Dependabot для автоматических обновлений
- Добавить `bandit` в CI для статического анализа
- Использовать `httpx.AsyncClient` вместо sync client в geocoder

---

## 7. Баги в коде

### 7.1 Enum mismatch (критический)

Alembic migration создаёт enum `sourcetype` только с `torgi_gov` и `gosplan`. Модель определяет 4 значения. При вставке `fedresurs` или `etp` — PostgreSQL error.

**Файл:** `alembic/versions/001_initial.py`
**Фикс:** Обновить миграцию или создать новую с ALTER TYPE.

### 7.2 `city` всегда None для torgi.gov.ru

В `_parse_lot_card()`:
```python
city = None  # Needs geocoding
```
Но в API-ответе есть `cityName`! Парсинг не извлекает его.

**Файл:** `scrapers/torgi_scraper.py`, метод `_parse_lot_card`
**Фикс:** Добавить `city = card.get("cityName")`

### 7.3 `days_back` не передаётся в API-запрос

Параметр `days_back` принимается в `scrape_listings()`, но не формирует `publishDateFrom` в API params. Скрейпер возвращает данные за всё время.

**Файл:** `scrapers/torgi_scraper.py`
**Фикс:** Добавить `params["publishDateFrom"] = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")`

### 7.4 Price per sqm не рассчитывается для обновлённых записей

В `_upsert_listings()` при обновлении — `price_per_sqm` не пересчитывается, даже если изменились `start_price` или `total_area`.

**Файл:** `services/enrichment.py`, метод `_upsert_listings`
**Фикс:** Добавить расчёт `price_per_sqm` при обновлении.

### 7.5 `_estimate_market_prices` — property_type может быть enum

```python
.prop.property_type.in_(["apartment", "house", "room"])
```
Если `property_type` — это `PropertyType` enum, а не строка — сравнение не сработает. SQLAlchemy обычно конвертирует, но `EnumString` TypeDecorator может не сработать в `IN` clause.

### 7.6 `session.commit()` в `scheduled_scrape()`, но `get_session()` тоже committs

`get_session()`:
```python
yield session
await session.commit()
```
`scheduled_scrape()`:
```python
await enrichment_service.run_full_pipeline(session)
await session.commit()
```
Двойной commit. Второй commit на уже-committed сессии — no-op, но если между ними произойдёт ошибка — данные могут быть в inconsistent state.

### 7.7 CSS `style.css` не используется

`index.html` содержит все стили inline в `<style>` теге. Файл `static/css/style.css` содержит тёмную тему, но не подключается к `index.html`. Два набора стилей — светлая (inline) и тёмная (файл) — конфликтуют.

### 7.8 `app.js` не используется

`index.html` содержит inline `<script>` с map-логикой. Файл `static/js/app.js` содержит класс `EstateAuctionApp`, но не подключается. Два набора JS-кода.

### 7.9 `preview.html` — orphaned file

Файл `preview.html` существует, но нигде не используется и не упоминается.

---

## 8. Автотесты и покрытие

### Что покрыто (75 тестов):

| Модуль | Тесты | Покрытие |
|--------|-------|----------|
| `test_models.py` | EnumString, AuctionProperty.to_dict, ScrapeLog | 🟢 Хорошо |
| `test_base_scraper.py` | _parse_price, _parse_date, _parse_datetime, throttle | 🟢 Хорошо |
| `test_torgi_scraper.py` | _detect_property_type, _parse_lot_card, status_map | 🟢 Хорошо |
| `test_cian_scraper.py` | region_id, search_url, remove_outliers | 🟡 Базово |
| `test_proxy_manager.py` | load, round-robin, mark_bad/good, headers | 🟢 Хорошо |
| `test_api_routes.py` | health, properties, map-data, stats, scrape-logs, validation | 🟡 Базово |

### Что НЕ покрыто:

| Модуль | Проблема |
|--------|----------|
| **FedresursScraper** | 0 тестов |
| **EtpScraper** | 0 тестов |
| **EnrichmentService** | 0 тестов (критический — вся оркестрация) |
| **Geocoder** | 0 тестов |
| **main.py middleware** | Rate limiter, security headers — 0 тестов |
| **Auth** | verify_admin_key — 0 тестов |
| **Error handling** | Нет тестов на ошибки БД, таймауты, retry |

### Рекомендации:

1. Добавить тесты для EnrichmentService (мокать скрейперы)
2. Добавить тесты для FedresursScraper (мокать Playwright)
3. Добавить интеграционные тесты с реальной SQLite БД
4. Добавить тесты для rate limiter
5. Проверить, что тесты вообще проходят (не запускались)

---

## 9. UX веб-интерфейса

### Текущее состояние

Два файла с конфликтующим дизайном:
- `index.html` — светлая тема, элегантная типографика (Playfair Display)
- `static/css/style.css` + `static/js/app.js` — тёмная тема, не подключены

### Проблемы UX:

1. **Нет состояния загрузки** — при первом открытии карты пользователь видит пустую карту без индикации загрузки
2. **Нет пустого состояния** — если нет данных, просто пустая карта без подсказки
3. **Нет поиска по карте** — нельзя найти конкретный адрес
4. **Нет фильтра по цене на UI** — input'ы есть, но не отправляются на API (priceMin/priceMax не передаются в loadData)
5. **Нет мобильного меню** — sidebar не адаптирован для мобильных
6. **Нет уведомлений о новых лотах** — push/email не реализован
7. **Scrape trigger без feedback** — кнопка «Обновить данные» запускает скрейпинг, но пользователь не видит прогресс
8. **Нет пагинации на карте** — загружаются все 5000 объектов сразу
9. **Нет фильтра по discount** — ключевая фича для инвесторов
10. **Нет сравнения объектов** — нельзя выбрать несколько и сравнить
11. **Нет экспорта** — нельзя скачать CSV/Excel
12. **Balloon на карте переполнен** — слишком много информации в маленьком balloon

### Рекомендации по UI:

**Немедленные фиксы:**
- Добавить loading spinner при загрузке данных
- Передавать priceMin/priceMax в API запрос
- Добавить пустое состояние «Нет объектов по вашим фильтрам»
- Добавить debounce на фильтры

**Модернизация:**
- Перейти на React/Vue SPA вместо Jinja2 + inline JS
- Добавить SSR для SEO (Next.js или Nuxt)
- Реализовать виртуализацию маркеров (Leaflet.markercluster)
- Добавить анимации переходов
- Добавить dark/light theme toggle
- Реализовать сохранённые поиски

### Референсы для интерфейса:

| Сервис | Что взять |
|--------|-----------|
| **ЦИАН** | Фильтры, карточки объектов, UX поиска |
| **Avito Недвижимость** | Карта + список, мобильный UX |
| **Яндекс.Недвижимость** | Карта, фильтры, аналитика |
| **Domclick (Сбер)** | Ипотечный калькулятор, оценка |
| **Realtor.com** | Map view, filters, saved searches |
| **Zillow** | Price history, Zestimate, neighborhood data |
| **Redfin** | Discount highlights, market trends |

---

## 10. Деплой на Render

### Проблемы с текущей конфигурацией

1. **Dockerfile не устанавливает Playwright browsers**
   ```dockerfile
   # RUN playwright install chromium  ← закомментировано!
   ```
   FedresursScraper и CianScraper (Playwright fallback) не будут работать.

2. **Alembic migration enum mismatch**
   Миграция создаёт enum `sourcetype` с 2 значениями, модель ожидает 4. При запуске `alembic upgrade head` — ошибка при вставке данных с `source=fedresurs`.

3. **`docker-compose.yml` vs `Dockerfile` conflict**
   `docker-compose.yml` использует `command: sh -c "alembic upgrade head && uvicorn main:app ..."`, но `Dockerfile` уже имеет `CMD ["uvicorn", ...]`. На Render используется Dockerfile, а не docker-compose.

4. **Нет DATABASE_URL для Render**
   Render предоставляет managed PostgreSQL с Internal Database URL. `.env.example` использует `DB_HOST`, `DB_PORT`, `DB_NAME` отдельно — нужно собрать URL.

5. **Playwright требует системных зависимостей**
   ```dockerfile
   RUN apt-get install -y ... gcc libpq-dev curl wget gnupg2
   ```
   Этого недостаточно для Playwright — нужны `libnss3`, `libatk-bridge2.0-0`, `libdrm2`, `libxkbcommon-x11-0` и т.д.

### План запуска на Render

#### Шаг 1: Исправить Dockerfile

```dockerfile
FROM python:3.12-slim

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev curl wget gnupg2 \
    libnss3 libatk-bridge2.0-0 libdrm2 libxkbcommon-x11-0 \
    libgbm1 libasound2 libxshmfence1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers
RUN playwright install chromium

COPY . .

EXPOSE 8000

CMD ["sh", "-c", "alembic upgrade head && uvicorn main:app --host 0.0.0.0 --port 8000"]
```

#### Шаг 2: Исправить миграцию

Создать новую миграцию для добавления enum значений:

```python
# alembic/versions/002_add_fedresurs_etp.py
def upgrade():
    op.execute("ALTER TYPE sourcetype ADD VALUE IF NOT EXISTS 'fedresurs'")
    op.execute("ALTER TYPE sourcetype ADD VALUE IF NOT EXISTS 'etp'")

def downgrade():
    pass  # Cannot remove enum values in PostgreSQL
```

Или: переписать модель на `EnumString` (String column) вместо PostgreSQL enum — уже сделано в models.py, но миграция создаёт native enum. Нужно привести в соответствие.

#### Шаг 3: Настроить Environment Variables на Render

```
DB_HOST=<render-postgres-internal-host>
DB_PORT=5432
DB_NAME=estate_auction
DB_USER=<render-user>
DB_PASSWORD=<render-password>
YANDEX_MAPS_API_KEY=<your-key>
ADMIN_API_KEY=<generate-with-secrets>
CORS_ORIGINS=https://your-app.onrender.com
DEBUG=false
SCRAPE_INTERVAL_HOURS=6
```

#### Шаг 4: Создать Web Service на Render

- **Environment:** Docker
- **Dockerfile Path:** `./Dockerfile`
- **Port:** 8000
- **Health Check Path:** `/health`
- **Instance Type:**至少 Standard (Playwright нужна RAM)

#### Шаг 5: Создать PostgreSQL на Render

- **Plan:** Free или Starter
- **Database Name:** `estate_auction`
- Подключить Internal Database URL к env vars

#### Альтернатива: Убрать Playwright из Dockerfile

Если Playwright не критичен (Fedresurs scraper и так нерабочий), можно обойтись без него:

```dockerfile
FROM python:3.12-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends gcc libpq-dev && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && uvicorn main:app --host 0.0.0.0 --port 8000"]
```

Это сэкономит ~400MB и ускорит деплой.

---

## Сводка приоритетов

### 🔴 Критично (блокирует запуск):
1. Исправить enum mismatch в миграции
2. Исправить Dockerfile (CMD + Playwright)
3. Настроить env vars для Render

### 🟡 Важно (нужно ASAP):
4. Извлекать `city` из API ответа torgi.gov.ru
5. Использовать `days_back` в API запросах
6. Добавить тесты для EnrichmentService
7. Убрать `verify=False` в production
8. Ограничить CORS

### 🟢 Улучшения:
9. Добавить loading states в UI
10. Реализовать price filter на frontend
11. Добавить Redis для rate limiting и кэша
12. Вынести скрейпинг в Celery workers
13. Добавить Telegram/email уведомления
