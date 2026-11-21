"""FAA NOTAM API adapter (filtered to Indian locations VI*, VA*, VE*, VO*).

Owner: Person A.

Status: implemented against the FAA NOTAM API v1 documentation
(``GET https://external-api.faa.gov/notamapi/v1/notams`` with ``client_id`` /
``client_secret`` headers, ``responseFormat=geoJson``).  **Not exercised
against the live service**: FAA_API_CLIENT_ID / FAA_API_CLIENT_SECRET are empty
in the project .env, and FAA is migrating to the NOTAM Management Service
(NMS), so endpoint and field names must be verified when a key is issued.

The ICAO-format text (``notamTranslation[type=ICAO].formattedText``) is stored
as raw_text so that the standard Q-line parser handles it.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone

from dotenv import load_dotenv

from ingestion.base import (
    RawNotam,
    SourceAdapter,
    SourceNotConfigured,
    is_indian_fir,
    is_indian_location,
)

load_dotenv()
log = logging.getLogger("ingestion.faa")

BASE_URL = "https://external-api.faa.gov/notamapi/v1/notams"
SOURCE_NAME = "FAA_NOTAM_API"
DEFAULT_LOCATIONS = ["VIDP", "VABB", "VOBL", "VOMM", "VECC", "VISR", "VOHS"]


def extract_icao_text(item: dict) -> tuple[str | None, dict]:
    """Return (ICAO formatted text, core notam dict) from one GeoJSON feature."""
    core = (item.get("properties") or {}).get("coreNOTAMData") or {}
    notam = core.get("notam") or {}
    for translation in core.get("notamTranslation") or []:
        if (translation.get("type") or "").upper() == "ICAO" and translation.get("formattedText"):
            return translation["formattedText"], notam
    return None, notam


class FaaAdapter(SourceAdapter):
    name = SOURCE_NAME
    access_type = "api"
    base_url = BASE_URL

    def __init__(self, locations=DEFAULT_LOCATIONS, page_size: int = 1000):
        self.locations = list(locations)
        self.page_size = page_size

    def is_configured(self) -> bool:
        return bool(os.getenv("FAA_API_CLIENT_ID") and os.getenv("FAA_API_CLIENT_SECRET"))

    def fetch(self) -> list[RawNotam]:
        if not self.is_configured():
            raise SourceNotConfigured("FAA_API_CLIENT_ID / FAA_API_CLIENT_SECRET not set")
        import httpx

        headers = {
            "client_id": os.environ["FAA_API_CLIENT_ID"],
            "client_secret": os.environ["FAA_API_CLIENT_SECRET"],
        }
        now = datetime.now(timezone.utc)
        out: list[RawNotam] = []
        with httpx.Client(timeout=60.0, headers=headers) as client:
            for location in self.locations:
                page = 1
                while True:
                    response = client.get(BASE_URL, params={
                        "icaoLocation": location,
                        "responseFormat": "geoJson",
                        "pageSize": self.page_size,
                        "pageNum": page,
                    })
                    response.raise_for_status()
                    payload = response.json()
                    for item in payload.get("items", []):
                        out.extend(self._to_raw(item, now))
                    if page >= int(payload.get("totalPages") or 1):
                        break
                    page += 1
        return out

    def _to_raw(self, item: dict, fetched_at: datetime) -> list[RawNotam]:
        text, notam = extract_icao_text(item)
        location = (notam.get("icaoLocation") or notam.get("location") or "").upper()
        fir = (notam.get("affectedFIR") or "").upper()
        if not (is_indian_location(location) or is_indian_fir(fir)):
            return []
        if not text:
            log.warning("FAA item %s has no ICAO text; skipped", notam.get("id"))
            return []
        return [RawNotam(
            source=SOURCE_NAME,
            raw_text=text,
            raw_format="icao_text",
            notam_id=notam.get("number"),
            source_url=BASE_URL,
            location_hint=location or fir,
            fetched_at=fetched_at,
        )]


if __name__ == "__main__":
    adapter = FaaAdapter()
    if not adapter.is_configured():
        print("FAA adapter not configured (set FAA_API_CLIENT_ID and FAA_API_CLIENT_SECRET in .env)")
    else:
        rows = adapter.fetch()
        print(f"Fetched {len(rows)} Indian NOTAMs from FAA")
        print(json.dumps([r.notam_id for r in rows[:20]]))
