"""Minimal HTTP client for the SMARD chart data API.

SMARD (www.smard.de) is the electricity market platform of the German Federal
Network Agency. It offers its chart data as plain JSON files over HTTPS, no
login or API key needed.

The API works in two steps:

1. ``{base}/{filter}/{region}/index_{resolution}.json`` lists the start
   timestamps of all available weekly chunks.
2. ``{base}/{filter}/{region}/{filter}_{region}_{resolution}_{ts}.json``
   returns the values of one chunk as ``[[timestamp_ms, value | null], ...]``.

Glossary:

* **filter** - SMARD's numeric ID of a data series, e.g. 4169 = day-ahead price.
  See ``series.py`` for the full list.
* **region** - market area, here always "DE-LU" (Germany + Luxembourg).
* **resolution** - time step of the values: "quarterhour", "hour", ...
* **chunk** - one data file. SMARD splits each series into files of one week.
* **timestamp_ms** - point in time as milliseconds since 1970-01-01 00:00 UTC
  ("Unix time"). It marks the *start* of the interval: the value at 14:00 is
  valid from 14:00 to 15:00.
* **null** - no value (yet), e.g. because the hour lies in the future.

Finished chunks are cached on disk. The newest chunk is always re-downloaded,
because it still receives new values.
"""

# Lets us write type hints like `Path | None` everywhere, and evaluates them
# lazily (they are documentation for humans and tools, not checked at runtime).
from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from typing import Literal

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

BASE_URL = "https://www.smard.de/app/chart_data"

# `Literal[...]` restricts a value to exactly these strings. Python does not
# enforce it at runtime, but editors and linters warn about typos such as "hourly".
Resolution = Literal["quarterhour", "hour", "day", "week", "month", "year"]


class SmardError(RuntimeError):
    """Raised when the SMARD API returns something unusable.

    Network problems, HTTP errors and malformed files all end up as this one
    exception type, so callers only need a single ``except SmardError``.
    """


def _default_session(retries: int) -> requests.Session:
    """Create an HTTP session that automatically retries temporary failures.

    A ``Session`` keeps the connection to the server open between requests,
    which is faster than reconnecting for every single file.
    """
    session = requests.Session()
    retry = Retry(
        total=retries,  # give up after this many retries
        # Wait longer before each retry (about 0.5 s, 1 s, 2 s, ...) so we do not
        # hammer a server that is already struggling.
        backoff_factor=0.5,
        # Only retry errors that are usually temporary:
        # 429 = "too many requests", 5xx = server-side errors.
        # A 404 ("not found") is permanent, so it fails immediately.
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET",),  # we only ever read data
    )
    # Use this retry rule for every URL starting with https://
    session.mount("https://", HTTPAdapter(max_retries=retry))
    # Tell the server politely who is asking (instead of the generic library name).
    session.headers["User-Agent"] = "energy-market-insights"
    return session


class SmardClient:
    """Downloads SMARD time series, with an optional on-disk cache.

    Typical use::

        client = SmardClient(cache_dir=Path("data/smard_cache"))
        prices = client.fetch_range(4169, start, end)
    """

    def __init__(
        self,
        *,  # everything after `*` must be passed by name: SmardClient(cache_dir=...)
        cache_dir: Path | None = None,  # None = no caching, always download
        session: requests.Session | None = None,  # tests pass their own session here
        timeout: float = 30.0,  # seconds to wait for an answer before giving up
        retries: int = 3,
        base_url: str = BASE_URL,
    ) -> None:
        self.cache_dir = cache_dir
        # `a or b` returns `a` if it is set, otherwise `b`.
        self.session = session or _default_session(retries)
        self.timeout = timeout
        # Strip a trailing "/" so that f"{base_url}/..." never produces "//".
        self.base_url = base_url.rstrip("/")

    # -- low level -----------------------------------------------------------
    # These methods map 1:1 to the two API steps described at the top of the file.

    def _get_json(self, url: str) -> dict:
        """Download ``url`` and parse the JSON answer into a Python dict."""
        try:
            response = self.session.get(url, timeout=self.timeout)
            # Turns HTTP error codes (404, 500, ...) into an exception.
            # Without this line an error page would be treated like data.
            response.raise_for_status()
            return response.json()
        # RequestException = any network/HTTP problem,
        # ValueError = the answer was not valid JSON.
        except (requests.RequestException, ValueError) as exc:
            # Re-raise as our own error type. `from exc` keeps the original
            # error attached, so the full cause is still visible when debugging.
            raise SmardError(f"request to {url} failed: {exc}") from exc

    def chunk_timestamps(self, filter_id: int, region: str, resolution: Resolution) -> list[int]:
        """Start timestamps (UTC ms) of all chunks, oldest first.

        This is API step 1, the "table of contents" of a series.
        """
        url = f"{self.base_url}/{filter_id}/{region}/index_{resolution}.json"
        timestamps = self._get_json(url).get("timestamps")
        # An empty list usually means a wrong filter ID or region.
        if not timestamps:
            raise SmardError(f"no chunks listed for filter {filter_id} / {region} / {resolution}")
        return sorted(int(t) for t in timestamps)

    def fetch_chunk(
        self, filter_id: int, region: str, resolution: Resolution, ts: int, *, cache: bool = True
    ) -> list[tuple[int, float | None]]:
        """Raw ``(timestamp_ms, value)`` pairs of one chunk.

        This is API step 2. ``ts`` is the chunk's start timestamp from
        :meth:`chunk_timestamps`. With ``cache=True`` (and a ``cache_dir`` set)
        the file is read from disk if it was downloaded before, otherwise it is
        downloaded and saved for next time.
        """
        # Same file name as on the server, e.g. "4169_DE-LU_hour_1794178800000.json"
        name = f"{filter_id}_{region}_{resolution}_{ts}.json"
        cache_file = self.cache_dir / name if self.cache_dir else None

        if cache and cache_file is not None and cache_file.is_file():
            # Cache hit: read from disk, no network needed.
            payload = json.loads(cache_file.read_text())
        else:
            # Cache miss (or caching disabled): download ...
            payload = self._get_json(f"{self.base_url}/{filter_id}/{region}/{name}")
            # ... and store the file for next time.
            if cache and cache_file is not None:
                cache_file.parent.mkdir(parents=True, exist_ok=True)
                cache_file.write_text(json.dumps(payload))

        # The file looks like {"series": [[timestamp_ms, value], ...], ...}
        series = payload.get("series")
        if series is None:
            raise SmardError(f"chunk {name} has no 'series' field")
        # Normalise the types: timestamps -> int, values -> float, null stays None.
        return [(int(t), None if v is None else float(v)) for t, v in series]

    # -- convenience ---------------------------------------------------------

    def fetch_range(
        self,
        filter_id: int,
        start: pd.Timestamp,
        end: pd.Timestamp,
        *,
        region: str = "DE-LU",
        resolution: Resolution = "hour",
    ) -> pd.Series:
        """Values in ``[start, end)`` as a float series with a UTC index.

        ``[start, end)`` means: ``start`` is included, ``end`` is not. Asking for
        2026-01-01 00:00 to 2026-01-02 00:00 returns exactly the 24 hours of
        January 1st. Ranges can therefore be chained without gaps or overlaps.

        This method hides the chunk logic: it works out which weekly files cover
        the requested range, fetches only those, and glues them together.

        Missing values (``null`` in the API, e.g. not yet published) become NaN.
        """
        # 1. Validate the input and convert everything to UTC.
        start, end = _as_utc(start), _as_utc(end)
        if start >= end:
            raise ValueError("start must be before end")

        # 2. Get the table of contents. The last entry is the current week.
        all_ts = self.chunk_timestamps(filter_id, region, resolution)
        newest = all_ts[-1]
        start_ms, end_ms = _to_ms(start), _to_ms(end)

        # 3. Download only the chunks that overlap [start, end).
        points: list[tuple[int, float | None]] = []
        for ts, next_ts in _with_next(all_ts):
            # A chunk covers [ts, next_ts). Skip it if it starts at or after
            # the end of our range, or if it is over before our range begins.
            if ts >= end_ms or (next_ts is not None and next_ts <= start_ms):
                continue
            # Never cache the newest chunk: SMARD still adds values to it, so a
            # cached copy would keep its gaps forever.
            points.extend(self.fetch_chunk(filter_id, region, resolution, ts, cache=ts != newest))

        # 4. Turn the list of pairs into a pandas Series (values with a time index).
        #    unit="ms": the numbers are milliseconds; utc=True: they are in UTC.
        #    None values become NaN ("not a number", pandas' marker for missing data).
        index = pd.to_datetime([t for t, _ in points], unit="ms", utc=True)
        values = pd.Series([v for _, v in points], index=index, dtype="float64")

        # 5. Clean up: drop duplicate timestamps (should not happen, but cheap
        #    insurance), sort by time, and cut to exactly [start, end).
        values = values[~values.index.duplicated(keep="last")].sort_index()
        return values[(values.index >= start) & (values.index < end)]


# -- helpers ------------------------------------------------------------------
# The leading underscore marks these as internal: not meant to be used outside
# this module.


def _as_utc(ts: pd.Timestamp | str) -> pd.Timestamp:
    """Convert a timezone-aware timestamp to UTC; reject naive timestamps.

    A "naive" timestamp has no timezone, e.g. ``2026-03-01 00:00``. That is
    ambiguous: German time and UTC differ by one or two hours. Instead of
    guessing (and silently shifting all data), we raise an error.
    """
    ts = pd.Timestamp(ts)
    if ts.tzinfo is None:
        raise ValueError(f"timestamp {ts} must be timezone-aware")
    return ts.tz_convert("UTC")


def _to_ms(ts: pd.Timestamp) -> int:
    """Timestamp -> milliseconds since 1970 (the format SMARD uses).

    pandas stores time internally in nanoseconds (``ts.value``), and
    1 ms = 1,000,000 ns.
    """
    return int(ts.value // 1_000_000)


def _with_next(items: list[int]) -> Iterable[tuple[int, int | None]]:
    """Pair every item with its successor: [A, B, C] -> (A, B), (B, C), (C, None).

    Used to know where each chunk ends (= where the next one starts).
    The last chunk has no successor, hence ``None``.
    """
    return zip(items, [*items[1:], None], strict=True)
