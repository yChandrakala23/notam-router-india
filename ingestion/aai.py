"""AAI AIM India monthly NOTAM summary adapter.

Owner: Person A.

Downloads the public monthly NOTAM Summary PDFs published by the Airports
Authority of India (AIM India) and splits them into one raw record per NOTAM.

URL pattern (observed on aim-india.aai.aero, verify if it changes)::

    https://aim-india.aai.aero/sites/default/files/notam_files/<Region>_<S>_<YYYY>_<MM>.pdf
    e.g. Delhi_A_2026_10.pdf, Chennai_C_2026_03.pdf

AIM India has no documented open API (methodology §3); the summaries are
public documents.  Fetch politely (a handful of PDFs per month) and respect the
portal's terms.  Research use only, not for operational flight planning.

Usage::

    # download Oct/Nov 2026 A-series summaries for all regions to data/raw/*.jsonl
    python -m ingestion.aai --months 2026-10 2026-11 --save-jsonl

    # the scheduler (ingestion.scheduler) stores them in PostgreSQL
"""

from __future__ import annotations

import argparse
import io
import json
import logging
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from ingestion.base import RawNotam, SourceAdapter
from parsing.aai_summary import (
    REGION_NOF,
    content_hash as aai_content_hash,
    parse_summary_records,
    region_from_url,
)

log = logging.getLogger("ingestion.aai")

BASE_URL = "https://aim-india.aai.aero/sites/default/files/notam_files/"
SOURCE_NAME = "AAI_AIM_INDIA"
REGIONS = ("Delhi", "Mumbai", "Chennai", "Kolkata")
RAW_DIR = Path("data/raw")

NOTAM_START = re.compile(r"(?m)^([A-Z]\d{4}/\d{2})\s+")


# --------------------------------------------------------------------------
# PDF helpers (kept from the original module)
# --------------------------------------------------------------------------


def download_pdf(url: str, timeout: float = 60.0) -> bytes:
    """Download an AAI NOTAM summary PDF."""
    import httpx  # imported lazily so offline use needs no httpx

    response = httpx.get(url, timeout=timeout, follow_redirects=True)
    response.raise_for_status()
    content_type = response.headers.get("content-type", "").lower()
    if "pdf" not in content_type and not response.content.startswith(b"%PDF"):
        raise ValueError(f"Expected PDF but received content-type={content_type}")
    return response.content


def extract_pdf_text(pdf_bytes: bytes) -> str:
    """Extract text from all pages of a PDF."""
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(pdf_bytes))
    return "\n".join((page.extract_text() or "") for page in reader.pages)


def extract_notam_blocks(text: str) -> list[tuple[str, str]]:
    """Split summary text into [(notam_id, raw_text), ...] in document order."""
    matches = list(NOTAM_START.finditer(text))
    records = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        raw_text = text[match.start():end].strip()
        if raw_text:
            records.append((match.group(1), raw_text))
    return records


def make_content_hash(raw_text: str, nof: str | None = None) -> str:
    """Content hash of one block (page furniture ignored, see aai_summary)."""
    return aai_content_hash(nof, raw_text)


def summary_url(region: str, series: str, year: int, month: int) -> str:
    return f"{BASE_URL}{region.title()}_{series.upper()}_{year:04d}_{month:02d}.pdf"


def _to_raw_notams(blocks: list[dict]) -> list[RawNotam]:
    """Attach NOF, location hint and content hash (stateful, document order)."""
    parsed = parse_summary_records(blocks)
    out = []
    for block, info in zip(blocks, parsed):
        region = region_from_url(block.get("source_url"))
        nof = REGION_NOF.get(region, (None, None))[0]
        fetched = block.get("fetched_at")
        if isinstance(fetched, str):
            fetched = datetime.fromisoformat(fetched)
        out.append(
            RawNotam(
                source=SOURCE_NAME,
                raw_text=block["raw_text"],
                raw_format="aai_summary",
                notam_id=block.get("notam_id") or info.notam_id,
                nof=nof,
                source_url=block.get("source_url"),
                location_hint=info.location,
                fetched_at=fetched or datetime.now(timezone.utc),
                content_hash=make_content_hash(block["raw_text"], nof),
            )
        )
    return out


def parse_aai_pdf(pdf_url: str, *, source: str = SOURCE_NAME) -> list[RawNotam]:
    """Download one summary PDF and return its raw NOTAM records."""
    text = extract_pdf_text(download_pdf(pdf_url))
    fetched_at = datetime.now(timezone.utc)
    blocks = [
        {"notam_id": nid, "raw_text": raw, "source_url": pdf_url,
         "fetched_at": fetched_at}
        for nid, raw in extract_notam_blocks(text)
    ]
    records = _to_raw_notams(blocks)
    for record in records:
        record.source = source
    return records


# --------------------------------------------------------------------------
# Adapter
# --------------------------------------------------------------------------


def _default_months(now: datetime | None = None) -> list[tuple[int, int]]:
    now = now or datetime.now(timezone.utc)
    prev = (now.year - 1, 12) if now.month == 1 else (now.year, now.month - 1)
    return [prev, (now.year, now.month)]


class AaiAdapter(SourceAdapter):
    """AIM India monthly summaries (live download or saved JSONL snapshots)."""

    name = SOURCE_NAME
    access_type = "pdf"
    base_url = BASE_URL
    # Monthly documents: fetching once a day is plenty and keeps load on the
    # AAI portal negligible.
    min_interval_min = 24 * 60

    def __init__(
        self,
        regions: Iterable[str] = REGIONS,
        series: Iterable[str] = ("A",),
        months: Iterable[tuple[int, int]] | None = None,
        *,
        offline_dir: Path | str | None = None,
        pause_s: float = 1.0,
    ) -> None:
        self.regions = [r.title() for r in regions]
        self.series = [s.upper() for s in series]
        self.months = list(months) if months else _default_months()
        self.offline_dir = Path(offline_dir) if offline_dir else None
        self.pause_s = pause_s
        self.failures: list[str] = []
        if self.offline_dir is not None:
            self.min_interval_min = 0

    def fetch(self) -> list[RawNotam]:
        if self.offline_dir is not None:
            return self.fetch_offline(self.offline_dir)
        records: list[RawNotam] = []
        for region in self.regions:
            for series in self.series:
                for year, month in self.months:
                    url = summary_url(region, series, year, month)
                    try:
                        records.extend(parse_aai_pdf(url))
                        log.info("AAI %s: ok", url.rsplit("/", 1)[-1])
                    except Exception as exc:  # 404 = not published yet, etc.
                        self.failures.append(f"{url.rsplit('/', 1)[-1]}: {exc}")
                        log.warning("AAI %s: %s", url.rsplit("/", 1)[-1], exc)
                    time.sleep(self.pause_s)
        return records

    @staticmethod
    def fetch_offline(directory: Path | str = RAW_DIR) -> list[RawNotam]:
        """Replay saved ``aai_*.jsonl`` snapshots (document order kept)."""
        blocks: list[dict] = []
        for path in sorted(Path(directory).glob("aai_*.jsonl")):
            with path.open(encoding="utf-8") as handle:
                for line in handle:
                    if line.strip():
                        blocks.append(json.loads(line))
        return _to_raw_notams(blocks)


def save_jsonl(records: list[RawNotam], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for r in records:
            handle.write(json.dumps({
                "notam_id": r.notam_id,
                "raw_text": r.raw_text,
                "source": r.source,
                "source_url": r.source_url,
                "fetched_at": r.fetched_at.isoformat(),
                "content_hash": r.content_hash,
            }, ensure_ascii=False) + "\n")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Download AAI monthly NOTAM summaries")
    parser.add_argument("--regions", nargs="+", default=list(REGIONS))
    parser.add_argument("--series", nargs="+", default=["A"])
    parser.add_argument("--months", nargs="+", help="YYYY-MM (default: previous + current)")
    parser.add_argument("--save-jsonl", action="store_true",
                        help="write data/raw/aai_<region>_<yyyy>_<mm>.jsonl (skips existing)")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    months = (
        [tuple(int(x) for x in m.split("-")) for m in args.months]
        if args.months else _default_months()
    )
    for region in args.regions:
        for series in args.series:
            for year, month in months:
                suffix = "" if series.upper() == "A" else f"_{series.lower()}"
                out = RAW_DIR / f"aai_{region.lower()}{suffix}_{year}_{month:02d}.jsonl"
                if args.save_jsonl and out.exists():
                    print(f"SKIP {out} (already saved)")
                    continue
                url = summary_url(region, series, year, month)
                try:
                    records = parse_aai_pdf(url)
                except Exception as exc:
                    print(f"FAILED {url.rsplit('/', 1)[-1]}: {exc}")
                    continue
                print(f"{url.rsplit('/', 1)[-1]}: {len(records)} NOTAM blocks")
                if args.save_jsonl:
                    save_jsonl(records, out)
                    print(f"  saved {out}")
                time.sleep(1.0)


if __name__ == "__main__":
    main()
