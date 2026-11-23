"""SQLite storage for raw SMARD values.

SQLite is a complete database in a single file (here ``data/emi.sqlite``). It
ships with Python (module ``sqlite3``), so no server has to be installed.

Tables (more follow in later steps):

* ``series`` - the catalogue from ``emi.smard.series``: one row per series.
* ``observations`` - the raw values, exactly as SMARD delivers them, in their
  native resolution. Hourly and quarter-hourly values of the same series live
  side by side; turning quarter-hours into hours is the job of ``cleaning``.

Conventions:

* ``ts_utc`` is the *start* of the interval in UTC milliseconds since 1970,
  the same format SMARD uses. No time zones inside the database.
* Only known values are stored. ``null`` from the API ("not published yet")
  is skipped, so a missing row means "no value".
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable
from pathlib import Path

import pandas as pd

from emi.smard.series import REGION, SERIES, Series

# `IF NOT EXISTS` makes the script safe to run on every start: existing tables
# (and their data) are left alone.
SCHEMA = """
CREATE TABLE IF NOT EXISTS series (
    key        TEXT PRIMARY KEY,      -- project name, e.g. 'price'
    filter_id  INTEGER NOT NULL,      -- SMARD filter ID, e.g. 4169
    region     TEXT NOT NULL,         -- 'DE-LU'
    label      TEXT NOT NULL,
    unit       TEXT NOT NULL,         -- 'EUR/MWh' or 'MWh'
    kind       TEXT NOT NULL          -- 'price', 'actual' or 'forecast'
);

CREATE TABLE IF NOT EXISTS observations (
    series_key TEXT NOT NULL REFERENCES series(key),
    resolution TEXT NOT NULL,         -- 'hour' or 'quarterhour'
    ts_utc     INTEGER NOT NULL,      -- interval start, UTC epoch milliseconds
    value      REAL NOT NULL,
    -- One value per series, resolution and point in time. This key is what
    -- makes the upsert below work.
    PRIMARY KEY (series_key, resolution, ts_utc)
);
"""


def connect(path: Path | str) -> sqlite3.Connection:
    """Open (or create) the database at ``path`` and make sure the schema exists.

    ``":memory:"`` gives a throwaway database in RAM, handy for tests.
    """
    if str(path) != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    # SQLite only checks REFERENCES (foreign keys) if this is switched on,
    # once per connection. Then a value for an unknown series is rejected.
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    return conn


def sync_series(conn: sqlite3.Connection, series: Iterable[Series] = SERIES.values()) -> None:
    """Write the series catalogue into the ``series`` table (insert or update)."""
    rows = [(s.key, s.filter_id, REGION, s.label, s.unit, s.kind) for s in series]
    # `with conn:` wraps everything in one transaction: either all rows are
    # written, or (on an error) none.
    with conn:
        conn.executemany(
            """
            INSERT INTO series (key, filter_id, region, label, unit, kind)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT (key) DO UPDATE SET
                filter_id = excluded.filter_id, region = excluded.region,
                label = excluded.label, unit = excluded.unit, kind = excluded.kind
            """,
            rows,
        )


def upsert_observations(
    conn: sqlite3.Connection,
    series_key: str,
    resolution: str,
    points: Iterable[tuple[int, float | None]],
) -> int:
    """Store ``(ts_ms, value)`` pairs, e.g. straight from ``SmardClient.fetch_chunk``.

    "Upsert" = insert, or update if the row already exists. Running the same
    import twice therefore changes nothing, and a corrected value from SMARD
    replaces the old one. ``None`` values are skipped.

    Returns the number of values written.
    """
    rows = [(series_key, resolution, int(ts), v) for ts, v in points if v is not None]
    with conn:
        conn.executemany(
            """
            INSERT INTO observations (series_key, resolution, ts_utc, value)
            VALUES (?, ?, ?, ?)
            ON CONFLICT (series_key, resolution, ts_utc) DO UPDATE SET value = excluded.value
            """,
            rows,
        )
    return len(rows)


def read_observations(
    conn: sqlite3.Connection,
    series_key: str,
    resolution: str,
    start: pd.Timestamp | None = None,
    end: pd.Timestamp | None = None,
) -> pd.Series:
    """Values of one series in ``[start, end)`` as a float series with a UTC index.

    ``start``/``end`` must be timezone-aware; ``None`` means "no limit".
    """
    sql = "SELECT ts_utc, value FROM observations WHERE series_key = ? AND resolution = ?"
    params: list[object] = [series_key, resolution]
    if start is not None:
        sql += " AND ts_utc >= ?"
        params.append(_to_ms(start))
    if end is not None:
        sql += " AND ts_utc < ?"
        params.append(_to_ms(end))
    rows = conn.execute(sql + " ORDER BY ts_utc", params).fetchall()

    index = pd.to_datetime([ts for ts, _ in rows], unit="ms", utc=True)
    return pd.Series([v for _, v in rows], index=index, dtype="float64", name=series_key)


def _to_ms(ts: pd.Timestamp) -> int:
    """Timezone-aware timestamp -> UTC epoch milliseconds."""
    ts = pd.Timestamp(ts)
    if ts.tzinfo is None:
        raise ValueError(f"timestamp {ts} must be timezone-aware")
    return int(ts.value // 1_000_000)  # pandas counts in nanoseconds
