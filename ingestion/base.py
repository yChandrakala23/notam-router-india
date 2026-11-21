"""Common adapter interface for NOTAM sources.

Owner: Person A.

Every source (AAI summaries, autorouter, FAA, ICAO) implements
:class:`SourceAdapter`.  ``fetch()`` returns a list of :class:`RawNotam`
objects; the adapter never writes to the database.  Storage is done by
``ingestion.store`` so that deduplication and run logging are identical for
every source.

Raw text is kept exactly as received (``raw_text``).  ``content_hash`` may be
computed on a normalised form (e.g. without PDF page furniture) so that
re-fetching the same NOTAM is idempotent.
"""

from __future__ import annotations

import hashlib
import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Iterable, Optional

log = logging.getLogger("ingestion")

# Indian ICAO location prefixes (methodology §3): VI*, VA*, VE*, VO*.
INDIAN_LOCATION = re.compile(r"^V[AEIO][A-Z]{2}$")
INDIAN_FIRS = frozenset({"VIDF", "VABF", "VECF", "VOMF"})

# raw_notam.raw_format values understood by the processor.
RAW_FORMATS = frozenset({
    "icao_text",        # standard ICAO NOTAM text (FAA formattedText, ICAO 'all')
    "aai_summary",      # block from an AAI monthly summary PDF
    "autorouter_json",  # autorouter JSON record (commercial, keep local)
})

# Higher rank wins when several sources describe the same NOTAM identity.
SOURCE_RANK = {"aai_summary": 1, "icao_text": 3, "autorouter_json": 3}


def is_indian_location(code: str | None) -> bool:
    return bool(code) and bool(INDIAN_LOCATION.match(code.strip().upper()))


def is_indian_fir(code: str | None) -> bool:
    return bool(code) and code.strip().upper() in INDIAN_FIRS


def sha256_text(text: str) -> str:
    """Default content hash: SHA-256 of whitespace-normalised text."""
    normalised = " ".join(text.split()).upper()
    return hashlib.sha256(normalised.encode("utf-8")).hexdigest()


@dataclass
class RawNotam:
    """One NOTAM exactly as obtained from a source."""

    source: str                    # data_source.name
    raw_text: str                  # unchanged payload
    raw_format: str                # one of RAW_FORMATS
    notam_id: Optional[str] = None  # e.g. A0100/26 when known
    nof: Optional[str] = None       # issuing NOTAM office when known
    source_url: Optional[str] = None
    location_hint: Optional[str] = None  # e.g. AAI section heading / FAA location
    fetched_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    content_hash: Optional[str] = None

    def __post_init__(self) -> None:
        if self.raw_format not in RAW_FORMATS:
            raise ValueError(f"Unknown raw_format {self.raw_format!r}")
        if self.fetched_at.tzinfo is None:
            raise ValueError("fetched_at must be timezone-aware (UTC)")
        if not self.content_hash:
            self.content_hash = sha256_text(self.raw_text)


class SourceNotConfigured(RuntimeError):
    """Raised when credentials / settings for a source are missing."""


class SourceAdapter(ABC):
    """Base class for all NOTAM sources."""

    #: data_source.name
    name: str = "base"
    #: data_source.access_type ('api', 'pdf', 'file')
    access_type: str = "api"
    #: data_source.base_url (informational)
    base_url: Optional[str] = None
    #: minimum minutes between two successful fetches (0 = every cycle)
    min_interval_min: float = 0

    def is_configured(self) -> bool:
        """True when the adapter has what it needs (keys, files...)."""
        return True

    @abstractmethod
    def fetch(self) -> list[RawNotam]:
        """Fetch NOTAMs.  Must not write to the database."""

    # Helpers shared by adapters ------------------------------------------

    @staticmethod
    def filter_indian(records: Iterable[RawNotam]) -> list[RawNotam]:
        """Keep records whose location hint is Indian (or unknown)."""
        kept = []
        for record in records:
            hint = (record.location_hint or "").upper()
            if not hint or is_indian_location(hint) or is_indian_fir(hint):
                kept.append(record)
        return kept
