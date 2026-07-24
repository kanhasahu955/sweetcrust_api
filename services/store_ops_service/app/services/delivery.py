from __future__ import annotations

from sqlmodel import Session, select

from app.models.enums import UserRole
from app.models.ops import DeliveryPerson, DeliveryTracking
from app.models.user import User
from app.schemas.admin import DeliveryPersonIn, DeliveryPersonPatchIn
from app.services.phone import normalize_phone
from app.producers.events import emit_delivery_location
from package.common.errors import BadRequestError, ConflictError, NotFoundError
from package.common.utils import hash_password, utc_now
from package.logger import get_logger

logger = get_logger(__name__)


def _phone_keys(phone: str) -> set[str]:
    raw = (phone or "").strip()
    norm = normalize_phone(raw)
    digits = "".join(c for c in norm if c.isdigit())
    last10 = digits[-10:] if len(digits) >= 10 else digits
    return {k for k in (raw, norm, last10, f"+91{last10}", f"91{last10}") if k}


def _find_person_by_phone(session: Session, phone: str) -> DeliveryPerson | None:
    keys = _phone_keys(phone)
    for p in session.exec(select(DeliveryPerson)).all():
        if p.phone in keys or "".join(c for c in (p.phone or "") if c.isdigit())[-10:] in {
            "".join(c for c in k if c.isdigit())[-10:] for k in keys if k
        }:
            return p
    return None


def _ensure_delivery_user(
    session: Session,
    *,
    name: str,
    phone: str,
    password: str | None,
) -> User:
    phone = normalize_phone(phone)
    user = session.exec(select(User).where(User.phone == phone)).first()
    if user and user.role != UserRole.DELIVERY:
        raise ConflictError("Phone already used by another account type")
    if password is not None:
        password = password.strip()
        if len(password) < 6:
            raise BadRequestError("Password must be at least 6 characters")
    if user:
        if password is not None:
            user.password_hash = hash_password(password)
        if name.strip():
            user.name = name.strip()
        user.role = UserRole.DELIVERY
        user.is_active = True
        user.terms_accepted = True
        session.add(user)
        session.commit()
        session.refresh(user)
        return user
    if not password:
        raise BadRequestError("Password is required for new rider login")
    user = User(
        phone=phone,
        name=name.strip() or "Rider",
        password_hash=hash_password(password),
        role=UserRole.DELIVERY,
        terms_accepted=True,
        is_active=True,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def list_persons(session: Session):
    return list(session.exec(select(DeliveryPerson).order_by(DeliveryPerson.created_at.desc())).all())


def create_person(session: Session, body: DeliveryPersonIn) -> DeliveryPerson:
    phone = normalize_phone(body.phone)
    name = (body.name or "").strip() or "Rider"
    password = getattr(body, "password", None)
    user = _ensure_delivery_user(session, name=name, phone=phone, password=password or None)

    person = _find_person_by_phone(session, phone)
    if person:
        person.name = name
        person.phone = phone
        person.user_id = user.id
        person.vehicle_number = body.vehicle_number
        person.default_trip_cost = body.default_trip_cost
        person.is_available = body.is_available
        session.add(person)
        session.commit()
        session.refresh(person)
        logger.info("delivery person updated id=%s user_id=%s", person.id, user.id)
        return person

    person = DeliveryPerson(
        user_id=user.id,
        name=name,
        phone=phone,
        vehicle_number=body.vehicle_number,
        default_trip_cost=body.default_trip_cost,
        is_available=body.is_available,
    )
    session.add(person)
    session.commit()
    session.refresh(person)
    logger.info("delivery person created id=%s user_id=%s", person.id, user.id)
    return person


def patch_person(session: Session, person_id: int, body: DeliveryPersonPatchIn) -> DeliveryPerson:
    p = session.get(DeliveryPerson, person_id)
    if not p:
        raise NotFoundError("Delivery person not found")
    data = body.model_dump(exclude_unset=True)
    password = data.pop("password", None)
    if "phone" in data and data["phone"] is not None:
        data["phone"] = normalize_phone(str(data["phone"]))
    for k, v in data.items():
        setattr(p, k, v)
    session.add(p)
    session.commit()
    session.refresh(p)

    if password is not None:
        user = _ensure_delivery_user(session, name=p.name, phone=p.phone, password=password)
        p.user_id = user.id
        p.phone = user.phone
        session.add(p)
        session.commit()
        session.refresh(p)
    elif p.user_id:
        user = session.get(User, p.user_id)
        if user:
            if "name" in data:
                user.name = p.name
            if "phone" in data:
                phone = normalize_phone(p.phone)
                other = session.exec(select(User).where(User.phone == phone)).first()
                if other and other.id != user.id:
                    raise ConflictError("Phone already used by another account")
                user.phone = phone
                p.phone = phone
            session.add(user)
            session.add(p)
            session.commit()
            session.refresh(p)

    return p


def live(session: Session):
    return list(session.exec(select(DeliveryTracking)).all())


def update_location(session: Session, order_id: int, lat: float, lng: float, eta: int | None = None):
    track = session.exec(select(DeliveryTracking).where(DeliveryTracking.order_id == order_id)).first()
    if not track:
        raise NotFoundError("Tracking not found")
    track.rider_lat = lat
    track.rider_lng = lng
    if eta is not None:
        track.eta_minutes = eta
    track.updated_at = utc_now()
    session.add(track)
    session.commit()
    session.refresh(track)
    emit_delivery_location(
        order_id,
        {
            "lat": lat,
            "lng": lng,
            "eta_minutes": track.eta_minutes,
            "delivery_person_id": track.delivery_person_id,
        },
    )
    return track
