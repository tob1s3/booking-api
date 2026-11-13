from datetime import date

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.booking_service import get_active_service, get_free_slots
from app.deps import Now, Session
from app.models import Service
from app.schemas import ServiceCreate, ServiceOut, ServiceUpdate, SlotsOut
from app.security import AdminUser

router = APIRouter(prefix="/services", tags=["services"])


@router.get("", response_model=list[ServiceOut])
async def list_services(session: Session) -> list[Service]:
    result = await session.scalars(
        select(Service).where(Service.is_active.is_(True)).order_by(Service.id)
    )
    return list(result)


@router.post("", response_model=ServiceOut, status_code=status.HTTP_201_CREATED)
async def create_service(data: ServiceCreate, session: Session, _: AdminUser) -> Service:
    service = Service(**data.model_dump())
    session.add(service)
    await session.commit()
    return service


@router.patch("/{service_id}", response_model=ServiceOut)
async def update_service(
    service_id: int, data: ServiceUpdate, session: Session, _: AdminUser
) -> Service:
    service = await session.get(Service, service_id)
    if service is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Услуга не найдена")
    # Услуги не удаляем, а выключаем (is_active=false): на них ссылаются старые записи
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(service, field, value)
    await session.commit()
    return service


@router.get("/{service_id}/slots", response_model=SlotsOut)
async def service_slots(service_id: int, day: date, session: Session, now: Now) -> SlotsOut:
    service = await get_active_service(session, service_id)
    slots = await get_free_slots(session, service, day, now)
    return SlotsOut(service_id=service.id, day=day.isoformat(), slots=slots)
