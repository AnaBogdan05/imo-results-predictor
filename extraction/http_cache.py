"""Polite HTTP client shared by the crawlers.

Every response is cached under data/cache/, so a page is never requested twice.
Requests identify the project with a descriptive user agent and are spaced by
a fixed delay.
"""
import hashlib
import time
from pathlib import Path
from urllib.parse import urlparse

import requests

ROOT = Path(__file__).resolve().parents[1]
CACHE_DIR = ROOT / "data" / "cache"

USER_AGENT = (
    "imo-results-predictor/0.1 (MSc Data Science student project, UNSTPB; "
    "https://github.com/AnaBogdan05/imo-results-predictor)"
)
DELAY_SECONDS = 3.0

_session = requests.Session()
_session.headers["User-Agent"] = USER_AGENT
_last_request = 0.0


def cache_path(url: str, suffix: str = "") -> Path:
    host = urlparse(url).netloc
    digest = hashlib.sha1(url.encode()).hexdigest()[:16]
    return CACHE_DIR / host / f"{digest}{suffix}"


def fetch(url: str, suffix: str = ".html", refresh: bool = False) -> bytes:
    """Return the body of `url`, downloading it only if it is not cached yet."""
    global _last_request
    path = cache_path(url, suffix)
    if path.exists() and not refresh:
        return path.read_bytes()

    wait = DELAY_SECONDS - (time.monotonic() - _last_request)
    if wait > 0:
        time.sleep(wait)
    response = _session.get(url, timeout=60)
    _last_request = time.monotonic()
    response.raise_for_status()

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(response.content)
    return response.content
