"""Seed endpoint — populates database with realistic property data."""

import random
from datetime import date, timedelta
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from database import get_session
from models import AuctionProperty, SourceType, AuctionStatus, PropertyType

router = APIRouter(prefix="/api")

# Moscow coordinates: 55.7558, 37.6173
# SPb coordinates: 59.9343, 30.3351

MOSCOW_DISTRICTS = [
    {"name": "ЦАО", "lat": 55.7558, "lon": 37.6173},
    {"name": "САО", "lat": 55.8382, "lon": 37.5122},
    {"name": "СВАО", "lat": 55.8617, "lon": 37.6228},
    {"name": "ВАО", "lat": 55.7878, "lon": 37.7715},
    {"name": "ЮВАО", "lat": 55.7019, "lon": 37.7585},
    {"name": "ЮАО", "lat": 55.6234, "lon": 37.6553},
    {"name": "ЮЗАО", "lat": 55.6579, "lon": 37.5486},
    {"name": "ЗАО", "lat": 55.7259, "lon": 37.4311},
    {"name": "СЗАО", "lat": 55.8334, "lon": 37.4167},
    {"name": "ЗелАО", "lat": 55.9833, "lon": 37.2000},
    {"name": "ТиНАО", "lat": 55.4986, "lon": 37.3214},
    {"name": "НАО", "lat": 55.5344, "lon": 37.5547},
]

SPB_DISTRICTS = [
    {"name": "Центральный", "lat": 59.9343, "lon": 30.3351},
    {"name": "Адмиралтейский", "lat": 59.9142, "lon": 30.2900},
    {"name": "Василеостровский", "lat": 59.9467, "lon": 30.2367},
    {"name": "Калининский", "lat": 59.9933, "lon": 30.3900},
    {"name": "Кировский", "lat": 59.8750, "lon": 30.2667},
    {"name": "Московский", "lat": 59.8500, "lon": 30.3167},
    {"name": "Невский", "lat": 59.8733, "lon": 30.4500},
    {"name": "Петроградский", "lat": 59.9667, "lon": 30.3000},
    {"name": "Приморский", "lat": 60.0167, "lon": 30.2167},
    {"name": "Фрунзенский", "lat": 59.8500, "lon": 30.3500},
]

PROPERTY_TYPES = [
    ("apartment", "Квартира", 0.5),
    ("house", "Дом/Коттедж", 0.15),
    ("land", "Земельный участок", 0.1),
    ("commercial", "Коммерческая недвижимость", 0.1),
    ("room", "Комната", 0.08),
    ("garage", "Гараж/Машиноместо", 0.05),
    ("other", "Другое", 0.02),
]

SOURCES = [
    ("torgi_gov", 0.5),
    ("fedresurs", 0.25),
    ("etp", 0.15),
    ("cian", 0.1),
]

STREET_NAMES_MOSCOW = [
    "ул. Ленина", "ул. Пушкина", "ул. Гагарина", "ул. Мира", "пр. Мира",
    "ул. Советская", "ул. Центральная", "ул. Школьная", "ул. Садовая",
    "ул. Новая", "ул. Лесная", "ул. Полевая", "ул. Заводская", "ул. Комсомольская",
    "ул. Молодёжная", "ул. Октябрьская", "ул. Парковая", "ул. Строителей",
    "Кутузовский пр.", "Ленинградский пр.", "Каширское ш.", "Варшавское ш.",
    "ул. Тверская", "ул. Арбат", "ул. Пятницкая", "ул. Маросейка",
]

STREET_NAMES_SPB = [
    "Невский пр.", "Московский пр.", "Лиговский пр.", "Садовая ул.",
    "ул. Рубинштейна", "ул. Марата", "Загородный пр.", "Владимирский пр.",
    "ул. Восстания", "ул. Чехова", "ул. Пестеля", "ул. Репина",
    "Каменноостровский пр.", "Петроградская ул.", "ул. Блохина",
    "Кронверкский пр.", "ул. Льва Толстого", "ул. Чайковского",
]

APARTMENT_TITLES = [
    "{rooms}-комн. квартира, {area} м², {floor}/{total_floors} этаж",
    "{rooms}-комн. квартира {area} м²",
    "Квартира, {rooms} комн., {area} м², {district}",
]

HOUSE_TITLES = [
    "Дом {area} м², участок {land} сот., {district}",
    "Коттедж {area} м², {district}",
]

LAND_TITLES = [
    "Земельный участок {land} сот., {district}",
    "Участок {land} сот. под ИЖС",
]

COMMERCIAL_TITLES = [
    "Помещение {area} м², {district}",
    "Офис {area} м², {district}",
]


def _weighted_choice(items):
    total = sum(w for _, w in items)
    r = random.uniform(0, total)
    cumulative = 0
    for item, weight in items:
        cumulative += weight
        if r <= cumulative:
            return item
    return items[-1][0]


def _generate_property(city: str, districts: list, idx: int) -> dict:
    district = random.choice(districts)
    prop_type = _weighted_choice(PROPERTY_TYPES)
    source = _weighted_choice(SOURCES)

    lat = district["lat"] + random.uniform(-0.05, 0.05)
    lon = district["lon"] + random.uniform(-0.08, 0.08)

    streets = STREET_NAMES_MOSCOW if city == "Москва" else STREET_NAMES_SPB
    street = random.choice(streets)
    house = random.randint(1, 150)
    address = f"{street}, д. {house}"

    days_ago = random.randint(0, 120)
    pub_date = date.today() - timedelta(days=days_ago)

    auction_start = pub_date + timedelta(days=random.randint(5, 30))
    auction_end = auction_start + timedelta(days=random.randint(3, 14))

    statuses = [
        (AuctionStatus.ACTIVE, 0.4),
        (AuctionStatus.UPCOMING, 0.3),
        (AuctionStatus.COMPLETED, 0.25),
        (AuctionStatus.CANCELLED, 0.05),
    ]
    status = _weighted_choice(statuses)

    if prop_type == "apartment":
        rooms = random.choice([1, 1, 1, 2, 2, 2, 3, 3, 4, 5])
        area = round(random.uniform(25, 200), 1)
        floor = random.randint(1, 25)
        total_floors = max(floor, random.randint(5, 30))
        price_sqm = random.uniform(80000, 350000) if city == "Москва" else random.uniform(60000, 250000)
        start_price = round(area * price_sqm * random.uniform(0.4, 0.85), -3)
        market_price = round(area * price_sqm, -3)
        title_tpl = random.choice(APARTMENT_TITLES)
        title = title_tpl.format(rooms=rooms, area=int(area), floor=floor, total_floors=total_floors, district=district["name"])
    elif prop_type == "house":
        area = round(random.uniform(80, 500), 1)
        land = round(random.uniform(3, 30), 1)
        price_sqm = random.uniform(50000, 200000) if city == "Москва" else random.uniform(40000, 150000)
        start_price = round(area * price_sqm * random.uniform(0.4, 0.8), -3)
        market_price = round(area * price_sqm, -3)
        rooms = random.randint(2, 6)
        title = random.choice(HOUSE_TITLES).format(area=int(area), land=land, district=district["name"])
        floor = None
        total_floors = random.choice([1, 2, 3])
    elif prop_type == "land":
        land = round(random.uniform(2, 50), 1)
        price_sotka = random.uniform(200000, 3000000) if city == "Москва" else random.uniform(100000, 2000000)
        start_price = round(land * price_sotka * random.uniform(0.3, 0.7), -3)
        market_price = round(land * price_sotka, -3)
        area = None
        rooms = None
        floor = None
        total_floors = None
        title = random.choice(LAND_TITLES).format(land=land, district=district["name"])
    elif prop_type == "commercial":
        area = round(random.uniform(30, 1000), 1)
        price_sqm = random.uniform(100000, 500000) if city == "Москва" else random.uniform(80000, 300000)
        start_price = round(area * price_sqm * random.uniform(0.3, 0.7), -3)
        market_price = round(area * price_sqm, -3)
        rooms = None
        floor = random.randint(1, 10)
        total_floors = None
        title = random.choice(COMMERCIAL_TITLES).format(area=int(area), district=district["name"])
    elif prop_type == "room":
        area = round(random.uniform(8, 30), 1)
        price_sqm = random.uniform(100000, 300000) if city == "Москва" else random.uniform(70000, 200000)
        start_price = round(area * price_sqm * random.uniform(0.4, 0.8), -3)
        market_price = round(area * price_sqm, -3)
        rooms = 1
        floor = random.randint(1, 20)
        total_floors = max(floor, random.randint(5, 25))
        title = f"Комната {area} м², {district['name']}"
    elif prop_type == "garage":
        area = round(random.uniform(12, 30), 1)
        start_price = round(random.uniform(200000, 3000000), -3)
        market_price = round(start_price * random.uniform(1.1, 1.5), -3)
        rooms = None
        floor = None
        total_floors = None
        title = f"Гараж {area} м², {district['name']}"
    else:
        area = round(random.uniform(10, 500), 1)
        start_price = round(random.uniform(100000, 10000000), -3)
        market_price = round(start_price * random.uniform(1.1, 1.5), -3)
        rooms = None
        floor = None
        total_floors = None
        title = f"Объект {area} м², {district['name']}"

    discount = round(((market_price - start_price) / market_price) * 100, 1) if market_price and start_price else None

    source_urls = {
        "torgi_gov": f"https://torgi.gov.ru/new/public/lots/lot/{random.randint(1000000, 9999999)}",
        "fedresurs": f"https://fedresurs.ru/message/{random.randint(10000000, 99999999)}",
        "etp": f"https://etp-ets.ru/lot/{random.randint(100000, 999999)}",
        "cian": f"https://www.cian.ru/sale/suburban/{random.randint(100000000, 999999999)}/",
    }

    organizers = [
        "Сбербанк АО", "ВТБ Банк", "Альфа-Банк", "Газпромбанк",
        "Арбитражный управляющий Иванов И.И.", "Конкурсный управляющий",
        "Судебный пристав", "Росимущество", "Аукционная комиссия",
    ]

    return {
        "source": source.value if hasattr(source, 'value') else source,
        "source_id": f"{source.value if hasattr(source, 'value') else source}_{idx}_{random.randint(10000, 99999)}",
        "source_url": source_urls.get(source.value if hasattr(source, 'value') else source, ""),
        "title": title,
        "description": f"Лот №{random.randint(1, 9999)} на торгах по реализации имущества.",
        "property_type": prop_type.value if hasattr(prop_type, 'value') else prop_type,
        "address": address,
        "region": "Москва" if city == "Москва" else "Санкт-Петербург",
        "city": city,
        "latitude": lat,
        "longitude": lon,
        "total_area": area,
        "living_area": round(area * random.uniform(0.6, 0.9), 1) if area else None,
        "rooms": rooms,
        "floor": floor,
        "total_floors": total_floors,
        "start_price": start_price,
        "current_price": round(start_price * random.uniform(0.9, 1.0), -3) if status == AuctionStatus.ACTIVE else start_price,
        "market_price": market_price,
        "price_per_sqm": round(start_price / area, 2) if area and start_price else None,
        "discount_pct": discount,
        "auction_status": status.value if hasattr(status, 'value') else status,
        "auction_date_start": auction_start.isoformat(),
        "auction_date_end": auction_end.isoformat(),
        "publish_date": pub_date.isoformat(),
        "lot_number": str(random.randint(1, 500)),
        "organizer": random.choice(organizers),
        "bid_step": round(start_price * random.uniform(0.005, 0.05), -3),
        "deposit": round(start_price * random.uniform(0.05, 0.2), -3),
        "is_geocoded": True,
        "is_market_appraised": random.random() > 0.2,
    }


async def _seed_data(session: AsyncSession) -> dict:
    """Seed database with realistic property data for Moscow and SPb."""
    count = (await session.execute(select(func.count(AuctionProperty.id)))).scalar()
    if count and count > 0:
        return {"status": "already_seeded", "count": count}

    properties = []

    # Generate Moscow properties
    for i in range(200):
        data = _generate_property("Москва", MOSCOW_DISTRICTS, i)
        properties.append(AuctionProperty(**data))

    # Generate SPb properties
    for i in range(150):
        data = _generate_property("Санкт-Петербург", SPB_DISTRICTS, i)
        properties.append(AuctionProperty(**data))

    session.add_all(properties)
    await session.commit()

    return {"status": "seeded", "count": len(properties), "cities": ["Москва", "Санкт-Петербург"]}


@router.post("/seed")
async def seed_database(session: AsyncSession = Depends(get_session)):
    """Seed database with realistic property data for Moscow and SPb."""
    return await _seed_data(session)
