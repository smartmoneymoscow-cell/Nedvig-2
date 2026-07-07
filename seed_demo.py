"""Seed database with realistic sample data for demo purposes."""

import sys
import os
import random
from datetime import datetime, date, timedelta

sys.path.insert(0, os.path.dirname(__file__))

from database import async_session_factory, init_db
from models import AuctionProperty, SourceType, AuctionStatus, PropertyType
import asyncio

SAMPLE_DATA = [
    # Moscow apartments
    {"title": "3-комнатная квартира, 75.4 м²", "address": "г. Москва, ул. Тверская, д. 12, кв. 45", "city": "Москва", "region": "77", "property_type": "apartment", "rooms": 3, "total_area": 75.4, "floor": 5, "total_floors": 9, "start_price": 12500000, "market_price": 18200000, "discount_pct": 31.3, "lat": 55.7558, "lon": 37.6173},
    {"title": "1-комнатная квартира, 38.2 м²", "address": "г. Москва, ул. Арбат, д. 25, кв. 12", "city": "Москва", "region": "77", "property_type": "apartment", "rooms": 1, "total_area": 38.2, "floor": 3, "total_floors": 5, "start_price": 8900000, "market_price": 12100000, "discount_pct": 26.4, "lat": 55.7522, "lon": 37.5915},
    {"title": "2-комнатная квартира, 54.1 м²", "address": "г. Москва, Пр-т Мира, д. 88, кв. 33", "city": "Москва", "region": "77", "property_type": "apartment", "rooms": 2, "total_area": 54.1, "floor": 8, "total_floors": 16, "start_price": 9800000, "market_price": 14500000, "discount_pct": 32.4, "lat": 55.8050, "lon": 37.6350},
    {"title": "Студия, 25.6 м²", "address": "г. Москва, ул. Бауманская, д. 42, кв. 1", "city": "Москва", "region": "77", "property_type": "apartment", "rooms": 0, "total_area": 25.6, "floor": 12, "total_floors": 25, "start_price": 6200000, "market_price": 8500000, "discount_pct": 27.1, "lat": 55.7680, "lon": 37.6820},
    {"title": "4-комнатная квартира, 112 м²", "address": "г. Москва, Ленинский пр-т, д. 65, кв. 78", "city": "Москва", "region": "77", "property_type": "apartment", "rooms": 4, "total_area": 112.0, "floor": 4, "total_floors": 12, "start_price": 18500000, "market_price": 27000000, "discount_pct": 31.5, "lat": 55.7100, "lon": 37.5800},
    # Moscow houses
    {"title": "Жилой дом, 180 м²", "address": "МО, Одинцовский р-н, д. Ново-Дарьино", "city": "Одинцово", "region": "50", "property_type": "house", "rooms": 5, "total_area": 180.0, "floor": 2, "total_floors": 2, "start_price": 15000000, "market_price": 22000000, "discount_pct": 31.8, "lat": 55.6770, "lon": 37.2640},
    {"title": "Часть жилого дома, 95 м²", "address": "МО, Красногорск, ул. Ленина, д. 15", "city": "Красногорск", "region": "50", "property_type": "house", "rooms": 3, "total_area": 95.0, "floor": 1, "total_floors": 2, "start_price": 8500000, "market_price": 12800000, "discount_pct": 33.6, "lat": 55.8200, "lon": 37.3300},
    # Land
    {"title": "Земельный участок 10 соток", "address": "МО, Ленинский р-н, д. Горки", "city": "Горки-2", "region": "50", "property_type": "land", "rooms": None, "total_area": 1000.0, "floor": None, "total_floors": None, "start_price": 3200000, "market_price": 5000000, "discount_pct": 36.0, "lat": 55.5400, "lon": 37.5200},
    {"title": "Земельный участок 20 соток под ИЖС", "address": "МО, Истринский р-н, п. Павловская Слобода", "city": "Павловская Слобода", "region": "50", "property_type": "land", "rooms": None, "total_area": 2000.0, "floor": None, "total_floors": None, "start_price": 4800000, "market_price": 7200000, "discount_pct": 33.3, "lat": 55.8200, "lon": 37.0800},
    # Commercial
    {"title": "Офисное помещение, 65 м²", "address": "г. Москва, ул. Маросейка, д. 9", "city": "Москва", "region": "77", "property_type": "commercial", "rooms": None, "total_area": 65.0, "floor": 3, "total_floors": 5, "start_price": 11000000, "market_price": 16500000, "discount_pct": 33.3, "lat": 55.7570, "lon": 37.6350},
    {"title": "Торговое помещение, 120 м²", "address": "г. Москва, ул. Тверская, д. 18", "city": "Москва", "region": "77", "property_type": "commercial", "rooms": None, "total_area": 120.0, "floor": 1, "total_floors": 5, "start_price": 25000000, "market_price": 38000000, "discount_pct": 34.2, "lat": 55.7650, "lon": 37.6050},
    # SPb
    {"title": "2-комнатная квартира, 48 м²", "address": "г. Санкт-Петербург, Невский пр-т, д. 100, кв. 22", "city": "Санкт-Петербург", "region": "78", "property_type": "apartment", "rooms": 2, "total_area": 48.0, "floor": 4, "total_floors": 6, "start_price": 6500000, "market_price": 9800000, "discount_pct": 33.7, "lat": 59.9320, "lon": 30.3600},
    {"title": "3-комнатная квартира, 72 м²", "address": "г. Санкт-Петербург, ул. Марата, д. 55, кв. 10", "city": "Санкт-Петербург", "region": "78", "property_type": "apartment", "rooms": 3, "total_area": 72.0, "floor": 6, "total_floors": 8, "start_price": 8200000, "market_price": 12500000, "discount_pct": 34.4, "lat": 59.9260, "lon": 30.3470},
    {"title": "Квартира-студия, 30 м²", "address": "г. Санкт-Петербург, пр-т Просвещения, д. 40", "city": "Санкт-Петербург", "region": "78", "property_type": "apartment", "rooms": 0, "total_area": 30.0, "floor": 9, "total_floors": 16, "start_price": 3800000, "market_price": 5500000, "discount_pct": 30.9, "lat": 60.0520, "lon": 30.3300},
    # Other cities
    {"title": "1-комнатная квартира, 42 м²", "address": "г. Казань, ул. Баумана, д. 30, кв. 5", "city": "Казань", "region": "16", "property_type": "apartment", "rooms": 1, "total_area": 42.0, "floor": 5, "total_floors": 9, "start_price": 3200000, "market_price": 4800000, "discount_pct": 33.3, "lat": 55.7890, "lon": 49.1150},
    {"title": "Земельный участок 8 соток", "address": "г. Казань, Приволжский р-н", "city": "Казань", "region": "16", "property_type": "land", "rooms": None, "total_area": 800.0, "floor": None, "total_floors": None, "start_price": 1800000, "market_price": 2800000, "discount_pct": 35.7, "lat": 55.7700, "lon": 49.1400},
    {"title": "2-комнатная квартира, 52 м²", "address": "г. Екатеринбург, ул. Ленина, д. 40, кв. 8", "city": "Екатеринбург", "region": "66", "property_type": "apartment", "rooms": 2, "total_area": 52.0, "floor": 3, "total_floors": 5, "start_price": 3500000, "market_price": 5200000, "discount_pct": 32.7, "lat": 56.8380, "lon": 60.6050},
    {"title": "Гараж, 24 м²", "address": "г. Новосибирск, ул. Каменская, д. 60", "city": "Новосибирск", "region": "54", "property_type": "garage", "rooms": None, "total_area": 24.0, "floor": 1, "total_floors": 1, "start_price": 350000, "market_price": 550000, "discount_pct": 36.4, "lat": 55.0300, "lon": 82.9200},
    {"title": "Комната 12 м² в коммунальной квартире", "address": "г. Москва, ул. Покровка, д. 18, кв. 7", "city": "Москва", "region": "77", "property_type": "room", "rooms": 1, "total_area": 12.0, "floor": 3, "total_floors": 5, "start_price": 2800000, "market_price": 4200000, "discount_pct": 33.3, "lat": 55.7620, "lon": 37.6380},
    {"title": "Нежилое помещение 85 м²", "address": "г. Краснодар, ул. Красная, д. 176", "city": "Краснодар", "region": "23", "property_type": "commercial", "rooms": None, "total_area": 85.0, "floor": 1, "total_floors": 3, "start_price": 5500000, "market_price": 8000000, "discount_pct": 31.3, "lat": 45.0350, "lon": 38.9800},
]


async def seed():
    await init_db()
    async with async_session_factory() as session:
        # Check if data already exists
        from sqlalchemy import select, func
        count = (await session.execute(select(func.count(AuctionProperty.id)))).scalar()
        if count and count > 0:
            print(f"Database already has {count} records, skipping seed.")
            return

        now = datetime.utcnow()
        for i, item in enumerate(SAMPLE_DATA):
            days_ago = random.randint(0, 30)
            prop = AuctionProperty(
                source=random.choice([SourceType.TORGIGOV, SOURCE := SourceType.TORGIGOV]),
                source_id=f"demo-{i+1:04d}",
                source_url=f"https://torgi.gov.ru/new/public/lots/lot/demo-{i+1:04d}",
                title=item["title"],
                description=f"Лот на торгах по банкротству. {item['title']}",
                property_type=PropertyType(item["property_type"]),
                address=item["address"],
                region=item["region"],
                city=item["city"],
                latitude=item.get("lat"),
                longitude=item.get("lon"),
                total_area=item["total_area"],
                rooms=item.get("rooms"),
                floor=item.get("floor"),
                total_floors=item.get("total_floors"),
                start_price=item["start_price"],
                current_price=item["start_price"],
                market_price=item.get("market_price"),
                price_per_sqm=round(item["start_price"] / item["total_area"], 2) if item.get("total_area") else None,
                discount_pct=item.get("discount_pct"),
                auction_status=random.choice([AuctionStatus.ACTIVE, AuctionStatus.UPCOMING]),
                publish_date=date.today() - timedelta(days=days_ago),
                auction_date_end=datetime.now() + timedelta(days=random.randint(5, 60)),
                lot_number=f"LOT-{i+1:04d}",
                is_geocoded=True,
                is_market_appraised=True,
            )
            session.add(prop)

        await session.commit()
        print(f"✅ Seeded {len(SAMPLE_DATA)} demo properties")


if __name__ == "__main__":
    asyncio.run(seed())
