
"""Autorouter NOTAM API adapter.

Owner: Person A.  Research use only.  Keep commercial NOTAM data private
(``data/autorouter/`` is git-ignored).  Credentials are read from .env and are
never printed or logged.

Two ways to use it:

* ``python -m ingestion.autorouter`` - fetch the airports below and save
  private JSONL snapshots in ``data/autorouter/`` (original behaviour).
* :class:`AutorouterAdapter` - used by the scheduler; live API or the saved
  snapshots (``offline_dir``), returns ``RawNotam`` objects whose raw_text is
  the canonical JSON record.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

import json
from datetime import datetime, timezone

from dotenv import load_dotenv

from ingestion.base import RawNotam, SourceAdapter, SourceNotConfigured
from parsing.autorouter_record import canonical_json, notam_id_of

load_dotenv()

BASE_URL = "https://api.autorouter.aero/v1.0"
OUTPUT_DIR = Path("data/autorouter")

# Test-corridor airports (DEL, BOM, BLR, MAA, CCU, SXR) + HYD.
AIRPORTS = ["VIDP", "VABB", "VECC", "VOMM", "VOHY", "VOBL", "VISR"]


def get_access_token(client: httpx.Client) -> str:
    """Request an OAuth2 client-credentials token."""
    username = os.getenv("AUTOROUTER_USER")
    password = os.getenv("AUTOROUTER_PASSWORD")

    if not username or not password:
        raise SourceNotConfigured(
            "Set AUTOROUTER_USER and AUTOROUTER_PASSWORD in .env"
        )

    response = client.post(
        f"{BASE_URL}/oauth2/token",
        data={
            "grant_type": "client_credentials",
            "client_id": username,
            "client_secret": password,
        },
    )
    response.raise_for_status()

    token = response.json().get("access_token")
    if not token:
        raise RuntimeError("Autorouter did not return an access token.")

    return token


def fetch_notams(
    client: httpx.Client,
    token: str,
    airport: str,
    limit: int = 100,
) -> list[dict]:
    """Fetch all NOTAM pages for one Item-A airport identifier."""
    headers = {"Authorization": f"Bearer {token}"}
    offset = 0
    records: list[dict] = []

    while True:
        response = client.get(
            f"{BASE_URL}/notam",
            headers=headers,
            params={
                "itemas": f'["{airport}"]',
                "offset": offset,
                "limit": limit,
            },
        )
        response.raise_for_status()
        payload = response.json()

        rows = payload.get("rows", [])
        records.extend(rows)

        total = payload.get("total", 0)
        print(
            f"{airport}: fetched {len(records)} / {total} records"
        )

        if not rows or len(records) >= total:
            break

        offset += len(rows)

        # Be polite to the API.
        time.sleep(0.2)

    return records


def save_jsonl(airport: str, records: list[dict]) -> Path:
    """Save a private local snapshot, one JSON object per line."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_DIR / f"{airport.lower()}_notams.jsonl"

    with path.open("w", encoding="utf-8") as file:
        for record in records:
            file.write(json.dumps(record, ensure_ascii=False) + "\n")

    return path


SOURCE_NAME = "AUTOROUTER"


def to_raw_notam(record: dict, fetched_at: datetime) -> RawNotam:
    raw = canonical_json(record)
    items = record.get("itema") or []
    return RawNotam(
        source=SOURCE_NAME,
        raw_text=raw,
        raw_format="autorouter_json",
        notam_id=notam_id_of(record),
        nof=(record.get("nof") or None),
        source_url=f"{BASE_URL}/notam",
        location_hint=items[0] if items else record.get("fir"),
        fetched_at=fetched_at,
        content_hash=None,  # computed from the canonical JSON
    )


class AutorouterAdapter(SourceAdapter):
    """autorouter.aero NOTAM API (or saved private snapshots)."""

    name = SOURCE_NAME
    access_type = "api"
    base_url = BASE_URL

    def __init__(self, airports=AIRPORTS, *, offline_dir: Path | str | None = None):
        self.airports = list(airports)
        self.offline_dir = Path(offline_dir) if offline_dir else None

    def is_configured(self) -> bool:
        if self.offline_dir is not None:
            return self.offline_dir.exists()
        return bool(os.getenv("AUTOROUTER_USER") and os.getenv("AUTOROUTER_PASSWORD"))

    def fetch(self) -> list[RawNotam]:
        if self.offline_dir is not None:
            return self.fetch_offline(self.offline_dir)
        now = datetime.now(timezone.utc)
        out: list[RawNotam] = []
        import httpx

        with httpx.Client(timeout=45.0) as client:
            token = get_access_token(client)
            for airport in self.airports:
                for record in fetch_notams(client, token, airport):
                    out.append(to_raw_notam(record, now))
        return self.filter_indian(out)

    @staticmethod
    def fetch_offline(directory: Path | str = OUTPUT_DIR) -> list[RawNotam]:
        out = []
        for path in sorted(Path(directory).glob("*_notams.jsonl")):
            fetched = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
            with path.open(encoding="utf-8") as handle:
                for line in handle:
                    if line.strip():
                        out.append(to_raw_notam(json.loads(line), fetched))
        return out


def main() -> None:
    import httpx

    with httpx.Client(timeout=45.0) as client:
        token = get_access_token(client)

        for airport in AIRPORTS:
            records = fetch_notams(client, token, airport)
            output_path = save_jsonl(airport, records)

            unique_ids = {
                record.get("id")
                for record in records
                if record.get("id") is not None
            }

            print(
                f"Saved {len(records)} records "
                f"({len(unique_ids)} unique IDs) to {output_path}"
            )


if __name__ == "__main__":
    main()
