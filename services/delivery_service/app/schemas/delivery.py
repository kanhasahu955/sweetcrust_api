from __future__ import annotations

from typing import Optional

from pydantic import Field

from package.common.schemas import APIModel


class AvailabilityIn(APIModel):
    is_available: bool


class RiderLocationIn(APIModel):
    lat: float
    lng: float
    order_id: Optional[int] = None
    eta_minutes: Optional[int] = None
    distance_km: Optional[float] = Field(default=None, ge=0)


class RiderStatusIn(APIModel):
    status: str
