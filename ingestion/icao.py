"""ICAO API Data Service NOTAM adapter (Indian locations / FIRs).

Owner: Person A.

Status: implemented against the ICAO API Data Service "notams-realtime-list"
endpoint (``api_key``, ``format=json``, ``locations=...``), whose records carry
the full ICAO NOTAM text in the ``all`` field.  **Not exercised live**:
ICAO_API_KEY is empty in the project .env and the free tier is limited, so
verify the endpoint and field names when a key is available.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone

from dotenv import load_dotenv

from ingestion.base import RawNotam, SourceAdapter, SourceNotConfigured, is_indian_location

load_dotenv()
log = logging.getLogger("ingestion.icao")

BASE_URL = "https://applications.icao.int/dataservices/api/notams-realtime-list"
SOURCE_NAME = "ICAO_API"
DEFAULT_LOCATIONS = ["VIDF", "VABF", "VECF", "VOMF",
                     "VIDP", "VABB", "VOBL", "VOMM", "VECC", "VISR"]


class IcaoAdapter(SourceAdapter):
    name = SOURCE_NAME
    access_type = "api"
    base_url = BASE_URL

    def __init__(self, locations=DEFAULT_LOCATIONS):
        self.locations = list(locations)

    def is_configured(self) -> bool:
        return bool(os.getenv("ICAO_API_KEY"))

    def fetch(self) -> list[RawNotam]:
        if not self.is_configured():
            raise SourceNotConfigured("ICAO_API_KEY not set")
        import httpx

        params = {
            "api_key": os.environ["ICAO_API_KEY"],
            "format": "json",
            "criticality": "",
            "locations": ",".join(self.locations),
        }
        response = httpx.get(BASE_URL, params=params, timeout=60.0)
        response.raise_for_status()
        now = datetime.now(timezone.utc)
        out = []
        for item in response.json() or []:
            text = item.get("all")
            location = (item.get("location") or "").upper()
            if not text:
                continue
            if location and not is_indian_location(location) and location not in self.locations:
                continue
            out.append(RawNotam(
                source=SOURCE_NAME,
                raw_text=text,
                raw_format="icao_text",
                notam_id=item.get("id"),
                source_url=BASE_URL,
                location_hint=location or None,
                fetched_at=now,
            ))
        return out


if __name__ == "__main__":
    adapter = IcaoAdapter()
    print("configured" if adapter.is_configured() else
          "ICAO adapter not configured (set ICAO_API_KEY in .env)")
