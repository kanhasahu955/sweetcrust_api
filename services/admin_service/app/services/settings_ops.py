from __future__ import annotations

from sqlmodel import Session, select

from app.models.ops import BakerySettings
from app.schemas.admin import SettingsUpdateIn
from package.common.utils import utc_now
from package.logger import get_logger

logger = get_logger(__name__)


def get_settings_row(session: Session) -> BakerySettings:
    row = session.exec(select(BakerySettings)).first()
    if not row:
        row = BakerySettings()
        session.add(row)
        session.commit()
        session.refresh(row)
        logger.info("seeded default bakery_settings")
    return row


def patch_settings(session: Session, body: SettingsUpdateIn) -> BakerySettings:
    row = get_settings_row(session)
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(row, k, v)
    row.updated_at = utc_now()
    session.add(row)
    session.commit()
    session.refresh(row)
    logger.info("bakery settings updated")
    return row
