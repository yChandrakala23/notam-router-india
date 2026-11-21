"""Pydantic request and response models for the NOTAM API."""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str
    database: str


# ---------------------------------------------------------------------------
# Person A: GET /notams/relevant, GET /notams/freshness
# (query validation itself lives in api.relevance.validate_query so that the
#  Python function and the HTTP endpoint enforce identical rules)
# ---------------------------------------------------------------------------


class ValidDuring(BaseModel):
    start: Optional[str]
    end: Optional[str] = Field(None, description="null = PERM / open-ended")
    end_estimated: bool = False
    permanent: bool = False


class RelevantNotamProperties(BaseModel):
    event_id: Optional[int] = None
    notam_id: Optional[str] = None
    nof: Optional[str] = None
    action: Optional[str] = None
    severity: Optional[str] = Field(None, description="BLOCKING | RESTRICTIVE | ADVISORY")
    category: Optional[str] = None
    q_code: Optional[str] = None
    icao_location: Optional[str] = None
    fir_code: Optional[str] = None
    lower_fl: Optional[int] = None
    upper_fl: Optional[int] = None
    valid_during: ValidDuring
    radius_nm: Optional[float] = None
    geom_source: Optional[str] = None
    match_reason: Optional[str] = Field(None, description="AERODROME | CORRIDOR | FIR_WIDE")
    distance_nm: Optional[float] = None
    e_text: Optional[str] = None
    schedule_text: Optional[str] = None
    classifier_conf: Optional[float] = None
    classifier_method: Optional[str] = None
    classifier_reason: Optional[str] = None
    classifier_keyword: Optional[str] = None
    classifier_uncertainty: list[str] = Field(default_factory=list)
    center_lat: Optional[float] = Field(None, description="circle centre (Q-line circles)")
    center_lon: Optional[float] = None
    raw_text: Optional[str] = None


class RelevantNotamFeature(BaseModel):
    type: str = "Feature"
    id: Optional[int] = None
    geometry: Optional[dict[str, Any]] = Field(None, description="GeoJSON Polygon (EPSG:4326) or null")
    properties: RelevantNotamProperties


class RelevantNotamsResponse(BaseModel):
    type: str = "FeatureCollection"
    features: list[RelevantNotamFeature]
    metadata: dict[str, Any]


class SourceFreshness(BaseModel):
    name: str
    access_type: Optional[str] = None
    active: Optional[bool] = None
    last_success_at: Optional[datetime] = None
    last_attempt_at: Optional[datetime] = None
    last_status: Optional[str] = None
    last_records_fetched: Optional[int] = None
    minutes_since_success: Optional[float] = None
    is_stale: bool = True


class FreshnessResponse(BaseModel):
    sources: list[SourceFreshness]
    any_stale: bool
    checked_at: datetime
