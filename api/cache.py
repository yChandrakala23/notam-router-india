"""Optional Redis cache for hot relevance queries (SHOULD-level feature).

Owner: Person A.

* Enabled only when REDIS_URL is set, the ``redis`` package is installed and
  the server answers PING; otherwise every call is a silent no-op.
* Keys include a *data version* (latest ingestion run id + latest event
  update), so a new ingestion cycle automatically invalidates old answers.
* TTL defaults to 300 s.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from typing import Any, Optional

log = logging.getLogger("api.cache")
_client = None
_disabled = False
TTL_SECONDS = int(os.getenv("NOTAM_CACHE_TTL", "300"))

DATA_VERSION_SQL = """
SELECT COALESCE((SELECT max(run_id) FROM ingestion_run), 0) || ':' ||
       COALESCE((SELECT extract(epoch FROM max(updated_at))::bigint FROM notam_event), 0)
"""


def _get_client():
    global _client, _disabled
    if _disabled:
        return None
    if _client is not None:
        return _client
    url = os.getenv("REDIS_URL")
    if not url:
        _disabled = True
        return None
    try:
        import redis

        client = redis.Redis.from_url(url, socket_connect_timeout=0.3, socket_timeout=0.3)
        client.ping()
        _client = client
        return client
    except Exception as exc:  # package missing / server down
        log.info("Redis cache disabled: %s", type(exc).__name__)
        _disabled = True
        return None


def make_key(prefix: str, params: dict, data_version: str) -> str:
    payload = json.dumps(params, sort_keys=True, default=str)
    digest = hashlib.sha256(f"{data_version}|{payload}".encode()).hexdigest()[:32]
    return f"notam:{prefix}:{digest}"


def get(key: str) -> Optional[Any]:
    client = _get_client()
    if client is None:
        return None
    try:
        value = client.get(key)
        return json.loads(value) if value else None
    except Exception:
        return None


def set(key: str, value: Any, ttl: int = TTL_SECONDS) -> None:  # noqa: A001
    client = _get_client()
    if client is None:
        return
    try:
        client.setex(key, ttl, json.dumps(value, default=str))
    except Exception:
        pass


def enabled() -> bool:
    return _get_client() is not None
