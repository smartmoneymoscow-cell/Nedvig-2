"""FastAPI routes for the estate auction application."""

from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_session
from models import AuctionProperty, ScrapeLog, SourceType, AuctionStatus, PropertyType

router = APIRouter(prefix="/api")


@router.get("/properties")
async def get_properties(
    session: AsyncSession = Depends(get_session),
    city: Optional[str] = Query(None, description="Filter by city"),
    property_type: Optional[str] = Query(None, description="Property type filter"),
    status: Optional[str] = Query(None, description="Auction status filter"),
    source: Optional[str] = Query(None, description="Data source filter"),
    price_min: Optional[float] = Query(None, description="Min price"),
    price_max: Optional[float] = Query(None, description="Max price"),
    area_min: Optional[float] = Query(None, description="Min area m²"),
    area_max: Optional[float] = Query(None, description="Max area m²"),
    has_coords: Optional[bool] = Query(True, description="Only with coordinates"),
    has_market_price: Optional[bool] = Query(None, description="Only with market appraisal"),
    date_from: Optional[date] = Query(None, description="Published after"),
    date_to: Optional[date] = Query(None, description="Published before"),
    sort_by: str = Query("publish_date", description="Sort field"),
    sort_order: str = Query("desc", description="Sort order asc/desc"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
):
    """Get filtered list of auction properties."""
    query = select(AuctionProperty)

    # Apply filters
    filters = []

    if city:
        filters.append(AuctionProperty.city.ilike(f"%{city}%"))
    if property_type:
        try:
            filters.append(AuctionProperty.property_type == PropertyType(property_type))
        except ValueError:
            pass
    if status:
        try:
            filters.append(AuctionProperty.auction_status == AuctionStatus(status))
        except ValueError:
            pass
    if source:
        try:
            filters.append(AuctionProperty.source == SourceType(source))
        except ValueError:
            pass
    if price_min is not None:
        filters.append(AuctionProperty.start_price >= price_min)
    if price_max is not None:
        filters.append(AuctionProperty.start_price <= price_max)
    if area_min is not None:
        filters.append(AuctionProperty.total_area >= area_min)
    if area_max is not None:
        filters.append(AuctionProperty.total_area <= area_max)
    if has_coords:
        filters.append(
            and_(
                AuctionProperty.latitude.isnot(None),
                AuctionProperty.longitude.isnot(None),
            )
        )
    if has_market_price is not None:
        if has_market_price:
            filters.append(AuctionProperty.market_price.isnot(None))
        else:
            filters.append(AuctionProperty.market_price.is_(None))
    if date_from:
        filters.append(AuctionProperty.publish_date >= date_from)
    if date_to:
        filters.append(AuctionProperty.publish_date <= date_to)

    if filters:
        query = query.where(and_(*filters))

    # Count
    count_query = select(func.count()).select_from(query.subquery())
    total = (await session.execute(count_query)).scalar()

    # Sort
    sort_column = getattr(AuctionProperty, sort_by, AuctionProperty.publish_date)
    if sort_order == "desc":
        query = query.order_by(sort_column.desc())
    else:
        query = query.order_by(sort_column.asc())

    # Paginate
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)

    result = await session.execute(query)
    properties = result.scalars().all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": (total + page_size - 1) // page_size,
        "items": [p.to_dict() for p in properties],
    }


@router.get("/properties/{property_id}")
async def get_property(
    property_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Get single property by ID."""
    result = await session.execute(
        select(AuctionProperty).where(AuctionProperty.id == property_id)
    )
    prop = result.scalar_one_or_none()
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")
    return prop.to_dict()


@router.get("/map-data")
async def get_map_data(
    session: AsyncSession = Depends(get_session),
    city: Optional[str] = Query(None),
    property_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    days: int = Query(90, description="Look back N days"),
):
    """Get optimized data for map display — only coords + minimal info."""
    filters = [
        AuctionProperty.latitude.isnot(None),
        AuctionProperty.longitude.isnot(None),
    ]

    if city:
        filters.append(AuctionProperty.city.ilike(f"%{city}%"))
    if property_type:
        try:
            filters.append(AuctionProperty.property_type == PropertyType(property_type))
        except ValueError:
            pass
    if status:
        try:
            filters.append(AuctionProperty.auction_status == AuctionStatus(status))
        except ValueError:
            pass

    if days:
        from datetime import timedelta
        cutoff = date.today() - timedelta(days=days)
        filters.append(AuctionProperty.publish_date >= cutoff)

    query = (
        select(AuctionProperty)
        .where(and_(*filters))
        .order_by(AuctionProperty.publish_date.desc())
        .limit(5000)
    )

    result = await session.execute(query)
    properties = result.scalars().all()

    return [
        {
            "id": p.id,
            "lat": p.latitude,
            "lon": p.longitude,
            "title": p.title or p.address or "Без названия",
            "price": p.start_price,
            "market_price": p.market_price,
            "discount_pct": p.discount_pct,
            "area": p.total_area,
            "rooms": p.rooms,
            "status": p.auction_status.value if p.auction_status else None,
            "type": p.property_type.value if p.property_type else None,
            "publish_date": p.publish_date.isoformat() if p.publish_date else None,
            "source": p.source.value if p.source else None,
            "url": p.source_url,
        }
        for p in properties
    ]


@router.get("/stats")
async def get_stats(session: AsyncSession = Depends(get_session)):
    """Get summary statistics."""
    total = (await session.execute(select(func.count(AuctionProperty.id)))).scalar()

    by_source = {}
    for source in SourceType:
        count = (
            await session.execute(
                select(func.count(AuctionProperty.id)).where(
                    AuctionProperty.source == source
                )
            )
        ).scalar()
        by_source[source.value] = count

    by_status = {}
    for status in AuctionStatus:
        count = (
            await session.execute(
                select(func.count(AuctionProperty.id)).where(
                    AuctionProperty.auction_status == status
                )
            )
        ).scalar()
        by_status[status.value] = count

    avg_discount = (
        await session.execute(
            select(func.avg(AuctionProperty.discount_pct)).where(
                AuctionProperty.discount_pct.isnot(None)
            )
        )
    ).scalar()

    # Top cities
    city_stats = (
        await session.execute(
            select(
                AuctionProperty.city,
                func.count(AuctionProperty.id).label("count"),
                func.avg(AuctionProperty.discount_pct).label("avg_discount"),
            )
            .where(AuctionProperty.city.isnot(None))
            .group_by(AuctionProperty.city)
            .order_by(func.count(AuctionProperty.id).desc())
            .limit(10)
        )
    ).all()

    return {
        "total": total,
        "by_source": by_source,
        "by_status": by_status,
        "avg_discount": round(avg_discount, 1) if avg_discount else None,
        "top_cities": [
            {
                "city": row.city,
                "count": row.count,
                "avg_discount": round(row.avg_discount, 1) if row.avg_discount else None,
            }
            for row in city_stats
        ],
    }


@router.get("/scrape-logs")
async def get_scrape_logs(
    session: AsyncSession = Depends(get_session),
    limit: int = Query(20),
):
    """Get recent scrape logs."""
    result = await session.execute(
        select(ScrapeLog).order_by(ScrapeLog.started_at.desc()).limit(limit)
    )
    logs = result.scalars().all()
    return [
        {
            "id": l.id,
            "source": l.source.value,
            "started_at": l.started_at.isoformat() if l.started_at else None,
            "finished_at": l.finished_at.isoformat() if l.finished_at else None,
            "items_found": l.items_found,
            "items_new": l.items_new,
            "items_updated": l.items_updated,
            "status": l.status,
            "errors": l.errors,
        }
        for l in logs
    ]
