# 🔍 Аудит скрейперов — найденные проблемы

## Общий вердикт: скрейперы НЕ РАБОТОСПОСОБНЫ в текущем виде

Ни один из трёх скрейперов не будет собирать реальные данные с сайтов. Каждый содержит
гипотетические API endpoints, устаревшие/нерабочие CSS-селекторы и логические ошибки.

---

## 1. TorgiGovScraper — 🔴 Критические проблемы

### 1.1 Фейковый API endpoint
```python
TORGIGOV_SEARCH_API = "https://torgi.gov.ru/new/api/public/lotcards/search"
```
**Проблема:** Этот endpoint — гипотетический. torgi.gov.ru не документировал публичный API.
Реальный сайт — SPA на Angular, данные загружаются через внутренние API с CSRF-токенами.

**Решение:** Нужно:
1. Зайти на torgi.gov.ru в браузере
2. Открыть DevTools → Network
3. Найти реальные XHR-запросы при поиске
4. Извлечь реальные URL, параметры и заголовки

### 1.2 Неправильные параметры запроса
```python
params = {
    "dynSubjRF": region_code or "",      # ← неправильное имя параметра
    "lotPropertyType": "2",              ← неправильное значение
    "publishDateFrom": date_from,         ← неправильный формат
    "page": str(page),                   ← может быть offset-based
    "size": str(page_size),              ← может быть другое имя
}
```
**Проблема:** Параметры выдуманы. Реальные имена и значения нужно смотреть в DevTools.

### 1.3 Фейковые CSS-селекторы (HTML fallback)
```python
lot_cards = soup.select(".lot-card, .lotItem, [class*='lot-card'], tr.lot-row")
```
**Проблема:** torgi.gov.ru — SPA. HTML-страница не содержит данных в HTML-тегах.
Данные подгружаются через JavaScript. BeautifulSoup не увидит ничего.

**Решение:** HTML-fallback не работает для SPA. Нужен либо реальный API,
либо Selenium/Playwright для рендеринга JS.

### 1.4 Неполный парсинг полей
Отсутствуют:
- `living_area` — жилая площадь
- `floor` / `total_floors` — этаж/этажность
- `bid_step` — шаг торгов
- `rooms` — количество комнат (не извлекается из title)

### 1.5 Неправильная логика статуса
```python
def _detect_auction_status(self, raw_data):
    status_str = raw_data.get("lotStatus", "").lower()
    if "идут" in status_str or "active" in status_str:
        return AuctionStatus.ACTIVE
    return AuctionStatus.UPCOMING  # ← "Опубликован" попадает сюда
```
**Проблема:** Статус "Опубликован" (published) — это ACTIVE, а не UPCOMING.
На torgi.gov.ru статусы: "Опубликован", "Идут торги", "Торги завершены", "Торги отменены".

---

## 2. GosPlanScraper — 🔴 Полностью нерабочий

### 2.1 Неправильное понимание источника
```python
GOSPLAN_API = "https://gosplan.info/api/v1"
GOSPLAN_SEARCH = "https://gosplan.info/search"
```
**Проблема:** gosplan.info — это НЕ агрегатор торгов по недвижимости.
Это REST API для доступа к данным ЕИС (Единая информационная система закупок):
- 44-ФЗ (госзакупки)
- 223-ФЗ (корпоративные закупки)
- ПП РФ 615

gosplan.info **не содержит** данных о торгах по недвижимости.
Он содержит данные о государственных закупках товаров/работ/услуг.

**Решение:** Полностью переосмыслить, что такое "ГосПлан" в контексте задачи.
Варианты:
1. Использовать gosplan.info API для поиска закупок **услуг по оценке недвижимости**
2. Заменить на другой источник: bankrot.fedresurs.ru (торги банкротов), реализация.рф
3. Убрать GosPlan и добавить реальные источники торгов по недвижимости

### 2.2 Фейковые API endpoints
```python
response = self.fetch_with_retry(f"{GOSPLAN_API}/lots", params=params)
```
**Проблема:** Endpoint `/api/v1/lots` не существует на gosplan.info.
Реальный API использует Swagger-документацию, нужно смотреть актуальные методы.

### 2.3 Фейковые CSS-селекторы
```python
cards = soup.select(".lot-card, .auction-card, .property-card, [class*='lot'], [class*='card']")
```
**Проблема:** Селекторы выдуманы. Нужно проверить реальную структуру HTML.

---

## 3. CianScraper — 🟡 Частично рабочий, но с проблемами

### 3.1 Фейковый API endpoint
```python
CIAN_API_SEARCH = "https://api.cian.ru/search-offers-v2/search-offers-desktop/"
```
**Проблема:** CIAN регулярно меняет API. Этот endpoint мог измениться.
Также CIAN активно блокирует автоматизированные запросы.

**Решение:** Проверить актуальный endpoint через DevTools.

### 3.2 Фейковый payload
```python
payload = {
    "jsonQuery": {
        "_type": "flatsale",
        "geo": {"type": "geo", "value": [{"type": "district", "id": ...}]},
        "room": {"type": "terms", "value": [rooms or 1, 2, 3]},
        ...
    }
}
```
**Проблема:** Структура jsonQuery — гипотетическая. CIAN использует
сложную вложенную структуру, которая регулярно меняется.

### 3.3 Ошибка в расчёте price_per_sqm (HTML fallback)
```python
avg_per_sqm = avg_price / (total_area * 0.85)  # Approximate
```
**Проблема:** На CIAN цены указаны за **весь объект**, а не за м².
Но `avg_price` — это средняя цена объекта, а не цена за м².
Деление на `total_area * 0.85` — некорректная аппроксимация.

**Правильно:** Брать цену за м² напрямую из карточек CIAN (если есть),
или делить на реальную площадь каждого comparable объекта.

### 3.4 Малый список городов
```python
CIAN_REGIONS = {
    "москва": 1, "санкт-петербург": 2, "новосибирск": 3, ...
}
```
**Проблема:** CIAN работает в 100+ городах. 10 городов — недостаточно.
Также region_id — не просто номер, а сложный идентификатор.

### 3.5 Нет обработки anti-bot
CIAN использует:
- Fingerprinting (Canvas, WebGL, AudioContext)
- Cookie-based challenges (Cloudflare/PerimeterX)
- Behavioral analysis (скорость кликов, мышь)

curl_cffi с TLS fingerprint — недостаточно. Нужен полноценный браузер
(Playwright/Selenium) с stealth-плагинами.

### 3.6 Нет фильтра по типу недвижимости
```python
payload["room"] = {"type": "terms", "value": [rooms or 1, 2, 3]}
```
**Проблема:** Для house/land/commercial нужна другая структура запроса.
Текущий код всегда использует `_type: "flatsale"`.

---

## 4. EnrichmentService — 🟡 Логические проблемы

### 4.1 Дублирование логики UPSERT
`_scrape_torgi()` и `_scrape_gosplan()` — копипаст с разными типами.
Нужен общий метод `_upsert_listings(listings, source)`.

### 4.2 Лимиты не масштабируются
```python
.limit(100)  # geocoding
.limit(20)   # market appraisal
```
При первом запуске может быть 1000+ объектов.
20 оценок за запуск = 50 запусков для 1000 объектов.
При интервале 6ч = 12.5 дней на полную оценку.

### 4.3 Нет retry для геокодирования
Если Yandex Geocoder вернул ошибку — объект помечается как "не геокодирован"
и будет обрабатываться снова и снова.

### 4.4 GosPlan не фильтрует недвижимость
gosplan.info возвращает **все закупки**, не только недвижимость.
Нет фильтрации по типу объекта закупки.

---

## 5. Что нужно исправить (приоритет)

### Приоритет 1: Определить реальные источники данных

| Источник | Статус | Что делать |
|----------|--------|------------|
| torgi.gov.ru | 🔴 Нужен реальный API | Зайти в DevTools, найти реальные endpoints |
| ГосПлан | 🔴 Неправильный источник | Заменить на bankrot.fedresurs.ru или реализация.рф |
| ЦИАН | 🟡 Нужна проверка API | Проверить актуальный endpoint + Playwright |

### Приоритет 2: Переписать скрейперы

1. **TorgiGovScraper** — найти реальный API через DevTools
2. **GosPlanScraper** — заменить на другой источник или убрать
3. **CianScraper** — добавить Playwright + stealth, проверить API

### Приоритет 3: Улучшить EnrichmentService

1. Вынести общий UPSERT в отдельный метод
2. Увеличить лимиты batch processing
3. Добавить retry для геокодирования
4. Добавить multi-region scraping

---

## 6. Рекомендуемые источники

### Реальные торги по недвижимости:

1. **torgi.gov.ru** — основной источник, нужен реальный API
2. **bankrot.fedresurs.ru** — торги банкротов (много ликвидной недвижимости)
3. **реализация.рф** — торги имущества банков-банкротов
4. **lot-online.ru** — крупнейшая площадка торгов
5. **utender.ru** — агрегатор торгов

### Рыночная оценка:

1. **CIAN** — самый полный каталог, но сложный anti-bot
2. **Avito** — проще парсить, но меньше данных
3. **Яндекс.Недвижимость** — есть API для оценки
4. **Domclick (Сбер)** — API для оценки стоимости
