# 📋 Nedvig-2 — Детальный план работ

> Цель: Разбить на микросервисы, сделать рабочие скрейперы без платных прокси,
> создать современный UI, задеплоить фронт на GitHub Pages, бэкенд на Render.

---

## Архитектура после рефакторинга

```
┌─────────────────────────────────────────────────────────────────┐
│                        GitHub Pages                             │
│                  static frontend (React/Vite)                   │
│                  https://smartmoneymoscow-cell.github.io/...    │
└──────────────────────────┬──────────────────────────────────────┘
                           │ fetch()
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Render (Web Service)                         │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │                  API Service (FastAPI)                      │  │
│  │  /api/properties  /api/map-data  /api/stats  /api/auth    │  │
│  │  /api/scrape-logs  /health  /api/agent/chat               │  │
│  └──────────────────────────┬────────────────────────────────┘  │
│                              │                                   │
│  ┌──────────────────────────▼────────────────────────────────┐  │
│  │                   PostgreSQL (Render managed)              │  │
│  │            auction_properties + scrape_logs + users        │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                           ▲
                           │ HTTP (webhook / cron trigger)
┌──────────────────────────┴──────────────────────────────────────┐
│                  Render (Background Worker)                      │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │              Scraper Worker (Python)                        │  │
│  │  ┌─────────┐ ┌──────────┐ ┌────────┐ ┌────────┐          │  │
│  │  │ TorgiGov │ │ Fedresurs│ │  CIAN  │ │  ETP   │          │  │
│  │  └────┬────┘ └────┬─────┘ └───┬────┘ └───┬────┘          │  │
│  │       └───────────┴───────────┴───────────┘               │  │
│  │                    │                                       │  │
│  │  ┌─────────────────▼──────────────────────────────────┐   │  │
│  │  │         Anti-Detection Layer                         │   │  │
│  │  │  • curl_cffi (TLS fingerprint)                      │   │  │
│  │  │  • Playwright (JS rendering)                        │   │  │
│  │  │  • Free proxy rotation (auto-discovery)             │   │  │
│  │  │  • Tor SOCKS5 (для блокированных сайтов)           │   │  │
│  │  │  • Smart throttling (randomized delays)             │   │  │
│  │  │  • UA rotation (fake-useragent)                     │   │  │
│  │  └────────────────────────────────────────────────────┘   │  │
│  │                    │                                       │  │
│  │  ┌─────────────────▼──────────────────────────────────┐   │  │
│  │  │         Enrichment Pipeline                          │   │  │
│  │  │  1. Scrape (asyncio.to_thread)                      │   │  │
│  │  │  2. UPSERT into PostgreSQL                          │   │  │
│  │  │  3. Geocode (Yandex Geocoder)                       │   │  │
│  │  │  4. Market estimate (CIAN)                          │   │  │
│  │  └────────────────────────────────────────────────────┘   │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Структура репозитория после рефакторинга

```
Nedvig-2/
├── api/                          # API Service (микросервис 1)
│   ├── main.py                   # FastAPI app
│   ├── config/
│   │   └── settings.py
│   ├── routes/
│   │   ├── properties.py
│   │   ├── map_data.py
│   │   ├── stats.py
│   │   ├── auth.py
│   │   └── admin.py
│   ├── middleware/
│   │   ├── rate_limiter.py
│   │   └── security.py
│   ├── models/
│   │   ├── base.py
│   │   ├── property.py
│   │   ├── user.py
│   │   └── scrape_log.py
│   ├── database.py
│   ├── requirements.txt
│   └── Dockerfile
│
├── scraper-worker/               # Scraper Worker (микросервис 2)
│   ├── scrapers/
│   │   ├── base.py
│   │   ├── torgi_gov.py
│   │   ├── fedresurs.py
│   │   ├── cian.py
│   │   └── etp.py
│   ├── services/
│   │   ├── enrichment.py
│   │   ├── geocoder.py
│   │   ├── proxy_manager.py
│   │   └── anti_detect.py
│   ├── worker.py                 # Entry point (cron + manual trigger)
│   ├── requirements.txt
│   └── Dockerfile
│
├── frontend/                     # Frontend (GitHub Pages)
│   ├── src/
│   │   ├── App.tsx
│   │   ├── main.tsx
│   │   ├── components/
│   │   │   ├── Map/
│   │   │   ├── Sidebar/
│   │   │   ├── PropertyCard/
│   │   │   ├── Filters/
│   │   │   ├── Stats/
│   │   │   └── Layout/
│   │   ├── hooks/
│   │   │   ├── useProperties.ts
│   │   │   ├── useMapData.ts
│   │   │   └── useStats.ts
│   │   ├── api/
│   │   │   └── client.ts
│   │   ├── types/
│   │   │   └── index.ts
│   │   └── styles/
│   │       └── globals.css
│   ├── public/
│   ├── index.html
│   ├── package.json
│   ├── vite.config.ts
│   ├── tailwind.config.js
│   └── tsconfig.json
│
├── alembic/                      # Shared migrations
├── shared/                       # Shared types/config
│   └── models.py                 # SQLAlchemy models (shared between api + worker)
│
├── docker-compose.yml            # Local dev
├── docker-compose.prod.yml       # Production (optional)
└── README.md
```

---

## Этап 0: Подготовка (0.5 дня)

### 0.1 Создать ветки
```
git checkout -b feature/microservices-refactor
git checkout -b feature/scrapers-v2
git checkout -b feature/frontend-v2
git checkout -b feature/deploy
```

### 0.2 Настроить GitHub Actions
- CI: pytest на каждый push
- CD: auto-deploy frontend на GitHub Pages при merge в main
- CD: auto-deploy backend на Render при merge в main

### 0.3 Настроить GitHub Environments
- `staging` — для тестового деплоя
- `production` — для продакшена

---

## Этап 1: Микросервисы — рефакторинг (2-3 дня)

### 1.1 Разделить на два сервиса

**API Service** (`api/`)
- Вынести из `main.py`: routes, middleware, models, database
- Убрать APScheduler (скрейпинг — отдельный сервис)
- Добавить endpoint `POST /api/scrape/trigger` который шлёт webhook на scraper-worker
- Добавить JWT авторизацию (registration, login, refresh)
- Добавить endpoint `/api/agent/chat` (NLU-парсер запросов)

**Scraper Worker** (`scraper-worker/`)
- Вынести скрейперы из `scrapers/`
- Вынести enrichment из `services/`
- Сделать `worker.py` — standalone скрипт:
  - Запускается по cron (APScheduler или systemd timer)
  - Принимает webhook от API для ручного запуска
  - Логирует результаты в scrape_logs
- Health check endpoint для Render

### 1.2 Shared code
- `shared/models.py` — SQLAlchemy модели (создаётся как installable package или symlink)
- Alembic миграции — общие, запускаются из API service

### 1.3 Database
- Render managed PostgreSQL
- Connection string через env vars
- Alembic auto-migrate при старте API

### 1.4 Межсервисное взаимодействие
- API → Worker: HTTP webhook (`POST /internal/scrape`)
- Worker → API: Прямой доступ к PostgreSQL (общая БД)
- Альтернатива: Redis queue (bull/celery) — но для MVP webhook проще

---

## Этап 2: Скрейперы — рабочие без платных прокси (3-4 дня)

### Стратегия обхода блокировок

| Метод | Описание | Стоимость |
|-------|----------|-----------|
| **curl_cffi** | TLS fingerprint = Chrome, обходит JA3-детект | Бесплатно |
| **Tor SOCKS5** | Смена IP через Tor exit nodes | Бесплатно |
| **Free proxy auto-discovery** | Автоматический поиск рабочих прокси | Бесплатно |
| **Playwright stealth** | Настоящий браузер + stealth overrides | Бесплатно |
| **Smart delays** | Рандомные паузы 3-15 сек между запросами | Бесплатно |
| **Session rotation** | Новые cookies/headers каждые N запросов | Бесплатно |
| **Request fingerprint rotation** | Разные Accept, Accept-Language, Referer | Бесплатно |
| **Direct API (torgi.gov.ru)** | Государственный API — без блокировок | Бесплатно |

### 2.1 TorgiGovScraper (основной источник)

**Статус:** Рабочий, доработки минимальны.

**Что исправить:**
1. Извлекать `city` из `card.get("cityName")`
2. Добавить `publishDateFrom` на основе `days_back`
3. Добавить retry с exponential backoff
4. Добавить multi-region scraping (поиск по всем регионам)
5. Логировать количество страниц и время

**Антиблокировка:** Не нужна — государственный API без rate limit (verified).
Достаточно паузы 1-3 сек между запросами.

### 2.2 FedresursScraper (банкротные торги)

**Статус:** Нужна переработка.

**Стратегия:**

**Primary: Playwright + stealth**
```python
# 1. Запуск headless Chromium с stealth
browser = playwright.chromium.launch(
    headless=True,
    args=["--disable-blink-features=AutomationControlled"]
)

# 2. Stealth overrides
page.add_init_script("""
    Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
    Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3]});
    window.chrome = {runtime: {}};
""")

# 3. Навигация + ожидание
page.goto("https://bankrot.fedresurs.ru/TradeList")
page.wait_for_load_state("networkidle")

# 4. Перехват API-запросов (Fedresurs загружает данные через XHR)
# Мониторим network requests и перехватываем JSON
api_data = []
page.on("response", lambda r: api_data.append(r.json()) 
        if "api" in r.url else None)

# 5. Парсинг перехваченных данных
```

**Fallback: Direct API discovery**
```python
# Fedresurs использует внутренние API endpoints
# Ищем их через DevTools → Network tab
# Возможные endpoints:
# - /api/v1/trades
# - /api/trades/search  
# - /api/v2/trades/list
# Пробуем каждый с curl_cffi
```

**Fallback 2: Tor SOCKS5**
```python
# Через Tor — бесплатно, IP меняется автоматически
session = curl_requests.Session(
    impersonate="chrome120",
    proxies={"https": "socks5://127.0.0.1:9050"}
)
```

### 2.3 CianScraper (рыночная оценка)

**Статус:** Частично рабочий, нужна доработка.

**Стратегия обхода:**

**Уровень 1: curl_cffi + Tor**
```python
# curl_cffi с TLS fingerprint + Tor SOCKS5
session = curl_requests.Session(
    impersonate="chrome120",
    proxies={"https": "socks5://127.0.0.1:9050"}
)
# Ротация exit node каждые 5 запросов
```

**Уровень 2: Playwright stealth**
```python
# Полноценный браузер с stealth
# CIAN проверяет Canvas fingerprint, WebGL, AudioContext
# Playwright + stealth plugin обходит большинство проверок
```

**Уровень 3: Парсинг __NEXT_DATA__**
```python
# CIAN — Next.js app. Данные в <script id="__NEXT_DATA__">
# Это самый надёжный способ — не нужен JS rendering
soup = BeautifulSoup(html, "lxml")
data = json.loads(soup.find("script", {"id": "__NEXT_DATA__"}).string)
offers = data["props"]["pageProps"]["offers"]
```

**Уровень 4: Avito как альтернатива**
```python
# Если CIAN полностью заблокирован — используем Avito
# Avito проще в парсинге, меньше anti-bot
# Но данных меньше (нет встроенной оценки)
```

**Уровень 5: Яндекс.Недвижимость API**
```python
# У Яндекса есть внутренний API для оценки
# Нужно найти через DevTools
```

### 2.4 EtpScraper (дополнительные площадки)

**Статус:** Нерабочий, нужна переработка.

**Стратегия:**
- Изучить реальную структуру HTML lot-online.ru, fabrikant.ru
- Использовать curl_cffi + free proxies
- Fallback: Playwright
- Если данные дублируют torgi.gov.ru — понизить приоритет

### 2.5 ProxyManager — бесплатные прокси

**Источники бесплатных прокси:**

| Источник | Тип | Обновление |
|----------|-----|------------|
| `free-proxy-list.net` | HTTP/SOCKS5 | Каждый час |
| `proxyscrape.com` | SOCKS5 | Каждые 30 мин |
| `github.com/proxifly/free-proxy-list` | SOCKS5 | Каждый день |
| `github.com/monosans/proxy-list` | SOCKS5 | Каждый день |
| `github.com/TheSpeedX/SOCKS-List` | SOCKS5 | Каждый день |
| **Tor** | SOCKS5 | Автоматическая ротация |

**Реализация:**
```python
class ProxyManager:
    # 1. Загрузка из публичных списков
    # 2. Health-check (пробный запрос к httpbin.org)
    # 3. Фильтрация по скорости (<2 сек)
    # 4. Round-robin rotation
    # 5. Mark bad/good динамически
    # 6. Fallback: Tor SOCKS5 (если ни один прокси не работает)
    # 7. Fallback: Direct connection (для torgi.gov.ru)
```

### 2.6 Tor integration

```python
# Dockerfile — установка Tor
RUN apt-get install -y tor
RUN echo "SocksPort 9050" >> /etc/tor/torrc
RUN echo "ExitNodes {ru}" >> /etc/tor/torrc  # Российские exit nodes

# Использование
session = curl_requests.Session(
    impersonate="chrome120",
    proxies={
        "http": "socks5h://127.0.0.1:9050",
        "https": "socks5h://127.0.0.1:9050",
    }
)
```

**Примечание:** Tor exit nodes могут быть заблокированы на CIAN. Используем как fallback.

---

## Этап 3: Frontend — современный UI (3-4 дня)

### 3.1 Стек

| Технология | Версия | Зачем |
|------------|--------|-------|
| **React** | 18 | UI framework |
| **TypeScript** | 5 | Type safety |
| **Vite** | 5 | Build tool (быстрый) |
| **TailwindCSS** | 3 | Utility-first CSS |
| **Leaflet** | 1.9 | Карта (бесплатная, без API ключа!) |
| **React-Leaflet** | 4 | React bindings для Leaflet |
| **TanStack Query** | 5 | Data fetching + кэш |
| **Zustand** | 4 | State management |
| **Framer Motion** | 11 | Анимации |
| **Lucide React** | — | Иконки |

### 3.2 Почему Leaflet вместо Яндекс.Карт?

| Критерий | Яндекс.Карты | Leaflet |
|----------|-------------|---------|
| API ключ | Нужен (платный для бизнеса) | Не нужен |
| Тайлы | Яндекс (ограничения) | OpenStreetMap (бесплатно) |
| Геокодирование | Платное | Nominatim (бесплатно) |
| Кастомизация | Ограничена | Полная |
| Размер | ~100KB | ~40KB |
| Мобильность | Средняя | Отличная |

**Тайлы:** `https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png`

### 3.3 Структура UI

```
┌─────────────────────────────────────────────────────────────┐
│  Header: Logo + Nav (Карта, Список, Статистика, О проекте)  │
├───────────────┬─────────────────────────────────────────────┤
│               │                                              │
│   Sidebar     │              Карта (Leaflet)                 │
│   ┌─────────┐ │                                              │
│   │ Фильтры │ │         📍 📍   📍                           │
│   │         │ │            📍      📍                        │
│   │ Город   │ │     📍        📍                             │
│   │ Тип     │ │         📍                                   │
│   │ Статус  │ │                                              │
│   │ Цена    │ │                                              │
│   │ Площадь │ │                                              │
│   │ Скидка  │ │                                              │
│   └─────────┘ │                                              │
│   ┌─────────┐ │                                              │
│   │ Легенда │ │                                              │
│   └─────────┘ │                                              │
│   ┌─────────┐ │                                              │
│   │ Стат.   │ │                                              │
│   └─────────┘ │                                              │
│               │                                              │
├───────────────┴─────────────────────────────────────────────┤
│  Detail Panel (выезжает справа при клике на маркер)         │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  Тип объекта · Источник                               │  │
│  │  Заголовок                                            │  │
│  │  ───────────────────────────────────────────────────  │  │
│  │  💰 Начальная цена: 8 500 000 ₽                      │  │
│  │  📊 Рыночная цена:   12 000 000 ₽                    │  │
│  │  🔥 Скидка:          −29.2%                           │  │
│  │  ───────────────────────────────────────────────────  │  │
│  │  📐 Площадь: 54 м²                                   │  │
│  │  🛏  Комнат: 2                                        │  │
│  │  🏢 Этаж: 5/9                                         │  │
│  │  📍 Адрес: г. Москва, ул. Ленина, д. 10              │  │
│  │  📅 Опубликовано: 01.07.2025                         │  │
│  │  ───────────────────────────────────────────────────  │  │
│  │  [Открыть на torgi.gov.ru →]  [На карте]             │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### 3.4 Ключевые фичи UI

1. **Карта с кластеризацией** — Leaflet.markercluster
2. **Цветовая маркировка** — по давности публикации (как сейчас)
3. **Фильтры в sidebar** — город, тип, статус, цена, площадь, скидка
4. **Detail panel** — выезжает справа при клике
5. **Режим «Список»** — таблица с сортировкой и пагинацией
6. **Режим «Статистика»** — графики (chart.js или recharts)
7. **Loading skeleton** — shimmer placeholders при загрузке
8. **Empty state** — «Нет объектов по вашим фильтрам»
9. **Responsive** — мобильная адаптация
10. **Dark/Light theme** — toggle
11. **Поиск по карте** — geocoding через Nominatim (OSM)
12. **Анимации** — Framer Motion для переходов

### 3.5 API client

```typescript
// src/api/client.ts
const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export async function fetchProperties(params: Filters): Promise<PaginatedResponse> {
  const searchParams = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== '') searchParams.set(k, String(v));
  });
  const res = await fetch(`${API_BASE}/api/properties?${searchParams}`);
  return res.json();
}

export async function fetchMapData(params: MapFilters): Promise<MapPoint[]> {
  const searchParams = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v) searchParams.set(k, String(v));
  });
  const res = await fetch(`${API_BASE}/api/map-data?${searchParams}`);
  return res.json();
}

export async function fetchStats(): Promise<Stats> {
  const res = await fetch(`${API_BASE}/api/stats`);
  return res.json();
}
```

### 3.6 Vite config для GitHub Pages

```typescript
// vite.config.ts
export default defineConfig({
  base: '/Nedvig-2/',  // Имя репозитория
  plugins: [react()],
  build: {
    outDir: 'dist',
  },
});
```

---

## Этап 4: Авторизация (1 день)

### 4.1 Backend (JWT)

```python
# api/routes/auth.py
POST /api/auth/register  # email + password → tokens
POST /api/auth/login     # email + password → tokens
POST /api/auth/refresh   # refresh_token → new tokens
GET  /api/auth/me        # current user

# JWT:
# - Access token: 15 min
# - Refresh token: 7 days
# - Stored in httpOnly cookies (secure, sameSite=strict)
```

### 4.2 Frontend

- Login/Register модальные окна
- Protected routes (избранное, настройки)
- Auto-refresh token

---

## Этап 5: Деплой (1-2 дня)

### 5.1 GitHub Pages (Frontend)

**GitHub Actions workflow:**

```yaml
# .github/workflows/deploy-frontend.yml
name: Deploy Frontend to GitHub Pages

on:
  push:
    branches: [main]
    paths: ['frontend/**']

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Setup Node
        uses: actions/setup-node@v4
        with:
          node-version: '20'
          
      - name: Install & Build
        working-directory: frontend
        run: |
          npm ci
          npm run build
          
      - name: Deploy to GitHub Pages
        uses: peaceiris/actions-gh-pages@v3
        with:
          github_token: ${{ secrets.GITHUB_TOKEN }}
          publish_dir: frontend/dist
```

**GitHub Settings:**
- Settings → Pages → Source: `gh-pages` branch
- URL: `https://smartmoneymoscow-cell.github.io/Nedvig-2/`

### 5.2 Render (Backend API)

**render.yaml:**

```yaml
services:
  # API Service
  - type: web
    name: nedvig-api
    runtime: docker
    dockerfilePath: ./api/Dockerfile
    envVars:
      - key: DATABASE_URL
        fromDatabase:
          name: nedvig-db
          property: connectionString
      - key: ADMIN_API_KEY
        generateValue: true
      - key: CORS_ORIGINS
        value: "https://smartmoneymoscow-cell.github.io"
      - key: JWT_SECRET
        generateValue: true
    healthCheckPath: /health

  # Scraper Worker
  - type: worker
    name: nedvig-scraper
    runtime: docker
    dockerfilePath: ./scraper-worker/Dockerfile
    envVars:
      - key: DATABASE_URL
        fromDatabase:
          name: nedvig-db
          property: connectionString
      - key: API_URL
        value: "https://nedvig-api.onrender.com"

databases:
  - name: nedvig-db
    plan: free
    databaseName: estate_auction
```

### 5.3 Dockerfile (API)

```dockerfile
FROM python:3.12-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev curl && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && uvicorn main:app --host 0.0.0.0 --port 8000"]
```

### 5.4 Dockerfile (Scraper Worker)

```dockerfile
FROM python:3.12-slim
WORKDIR /app

# System deps + Tor
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev curl tor \
    libnss3 libatk-bridge2.0-0 libdrm2 libxkbcommon-x11-0 \
    libgbm1 libasound2 libxshmfence1 \
    && rm -rf /var/lib/apt/lists/*

# Playwright
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN playwright install chromium

# Tor config (Russian exit nodes for better access to .ru sites)
RUN echo "SocksPort 9050" >> /etc/tor/torrc && \
    echo "ExitNodes {ru}" >> /etc/tor/torrc && \
    echo "StrictNodes 1" >> /etc/tor/torrc

COPY . .

# Start Tor + Worker
CMD ["sh", "-c", "tor & sleep 5 && python worker.py"]
```

### 5.5 Environment Variables

| Переменная | Где | Значение |
|------------|-----|----------|
| `DATABASE_URL` | API + Worker | Render PostgreSQL (auto) |
| `ADMIN_API_KEY` | API | Auto-generated |
| `JWT_SECRET` | API | Auto-generated |
| `CORS_ORIGINS` | API | `https://smartmoneymoscow-cell.github.io` |
| `YANDEX_MAPS_API_KEY` | Worker | (опционально, для геокодирования) |
| `SCRAPE_INTERVAL_HOURS` | Worker | `6` |
| `PROXY_LIST` | Worker | (опционально) |
| `USE_TOR` | Worker | `true` |
| `VITE_API_URL` | Frontend | `https://nedvig-api.onrender.com` |

---

## Этап 6: Тесты и CI (1-2 дня)

### 6.1 Backend тесты

```bash
# Структура тестов
tests/
├── unit/
│   ├── test_models.py          # ✅ Существует
│   ├── test_base_scraper.py    # ✅ Существует
│   ├── test_torgi_scraper.py   # ✅ Существует
│   ├── test_cian_scraper.py    # ✅ Существует
│   ├── test_proxy_manager.py   # ✅ Существует
│   ├── test_fedresurs_scraper.py  # ❌ Нужно добавить
│   ├── test_etp_scraper.py     # ❌ Нужно добавить
│   └── test_geocoder.py        # ❌ Нужно добавить
├── integration/
│   ├── test_api_routes.py      # ✅ Существует
│   ├── test_enrichment.py      # ❌ Нужно добавить
│   └── test_database.py        # ❌ Нужто добавить
└── e2e/
    └── test_full_pipeline.py   # ❌ Нужно добавить
```

### 6.2 CI Pipeline

```yaml
# .github/workflows/ci.yml
name: CI

on: [push, pull_request]

jobs:
  test-backend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - run: pip install -r api/requirements.txt
      - run: cd api && python -m pytest tests/ -v --tb=short

  test-frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '20'
      - run: cd frontend && npm ci && npm run build
```

---

## Этап 7: Доработки и polish (1-2 дня)

### 7.1 Исправить миграцию enum
```python
# Новая миграция: добавить fedresurs, etp в sourcetype
op.execute("ALTER TYPE sourcetype ADD VALUE IF NOT EXISTS 'fedresurs'")
op.execute("ALTER TYPE sourcetype ADD VALUE IF NOT EXISTS 'etp'")
```

### 7.2 Добавить Nginx reverse proxy (опционально)
- SSL termination
- Rate limiting
- Static file serving
- Caching

### 7.3 Добавить Redis (опционально)
- Rate limiter (distributed)
- Session cache
- API response cache (map-data, stats)

### 7.4 Добавить Telegram notifications
```python
# Уведомления о новых лотах с большой скидкой
async def notify_new_listings(listings):
    for listing in listings:
        if listing.discount_pct and listing.discount_pct > 20:
            await send_telegram(f"🔥 Скидка {listing.discount_pct}%: {listing.title}")
```

---

## Таймлайн

| Этап | Описание | Длительность | Статус |
|------|----------|-------------|--------|
| **0** | Подготовка (ветки, CI) | 0.5 дня | ⬜ |
| **1** | Микросервисы (рефакторинг) | 2-3 дня | ⬜ |
| **2** | Скрейперы (рабочие, без платных прокси) | 3-4 дня | ⬜ |
| **3** | Frontend (React + Leaflet) | 3-4 дня | ⬜ |
| **4** | Авторизация (JWT) | 1 день | ⬜ |
| **5** | Деплой (GitHub Pages + Render) | 1-2 дня | ⬜ |
| **6** | Тесты и CI | 1-2 дня | ⬜ |
| **7** | Доработки | 1-2 дня | ⬜ |
| | **Итого** | **13-18 дней** | |

---

## Приоритеты

### Phase 1: MVP запуск (5-7 дней)
- Этап 1 (рефакторинг)
- Этап 2 (только TorgiGov + CIAN скрейперы)
- Этап 3 (базовый UI)
- Этап 5 (деплой)

### Phase 2: Полнофункциональный (ещё 5-7 дней)
- Этап 2 (Fedresurs + ETP скрейперы)
- Этап 4 (авторизация)
- Этап 3 (расширенный UI: список, статистика, анимации)
- Этап 6 (тесты)

### Phase 3: Production-ready (ещё 3-4 дня)
- Этап 7 (Nginx, Redis, Telegram, polish)

---

## Риски

| Риск | Вероятность | Митигация |
|------|-------------|-----------|
| CIAN полностью блокирует | Средняя | Avito + Яндекс.Недвижимость как fallback |
| Fedresurs меняет SPA-структуру | Высокая | Перехват network requests (API interception) |
| Render free tier спит после 15 мин | Высокая | Cron job каждые 14 мин для keep-alive |
| GitHub Pages CORS | Низкая | CORS_ORIGINS настроен на домен Pages |
| Tor exit nodes заблокированы | Средняя | Free SOCKS5 proxies как fallback |
| Бесплатные прокси нестабильны | Высокая | Авто-discovery + health-check + Tor fallback |
