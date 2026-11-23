"""Tests for emi.db. Each test gets a fresh in-memory database (no files left behind)."""

import sqlite3

import pandas as pd
import pytest

from emi import db

H = 3_600_000  # one hour in ms
Q = H // 4  # one quarter-hour in ms
T0 = 1_767_225_600_000  # 2026-01-01 00:00 UTC


@pytest.fixture
def conn():
    """A fresh database with the series catalogue already loaded."""
    conn = db.connect(":memory:")
    db.sync_series(conn)
    yield conn
    conn.close()


def _count(conn):
    return conn.execute("SELECT COUNT(*) FROM observations").fetchone()[0]


def test_connect_creates_file_and_is_reopenable(tmp_path):
    path = tmp_path / "sub" / "emi.sqlite"  # parent folder does not exist yet
    conn = db.connect(path)
    db.sync_series(conn)
    db.upsert_observations(conn, "price", "hour", [(T0, 50.0)])
    conn.close()

    # Opening again must keep the data (schema creation does not wipe tables).
    conn = db.connect(path)
    assert db.read_observations(conn, "price", "hour").tolist() == [50.0]
    conn.close()


def test_sync_series_is_idempotent(conn):
    db.sync_series(conn)  # second time, on top of the fixture
    keys = {k for (k,) in conn.execute("SELECT key FROM series")}
    assert "price" in keys
    assert conn.execute("SELECT filter_id FROM series WHERE key = 'price'").fetchone() == (4169,)


def test_upsert_twice_changes_nothing(conn):
    points = [(T0, 1.0), (T0 + H, 2.0)]
    db.upsert_observations(conn, "price", "hour", points)
    db.upsert_observations(conn, "price", "hour", points)
    assert _count(conn) == 2


def test_upsert_replaces_corrected_value(conn):
    db.upsert_observations(conn, "price", "hour", [(T0, 1.0)])
    db.upsert_observations(conn, "price", "hour", [(T0, 9.0)])
    assert db.read_observations(conn, "price", "hour").tolist() == [9.0]


def test_upsert_skips_none(conn):
    written = db.upsert_observations(conn, "price", "hour", [(T0, 1.0), (T0 + H, None)])
    assert written == 1
    assert _count(conn) == 1


def test_hour_and_quarterhour_live_side_by_side(conn):
    db.upsert_observations(conn, "load", "hour", [(T0, 400.0)])
    db.upsert_observations(conn, "load", "quarterhour", [(T0 + i * Q, 100.0) for i in range(4)])
    assert len(db.read_observations(conn, "load", "hour")) == 1
    assert len(db.read_observations(conn, "load", "quarterhour")) == 4


def test_read_range_is_half_open_and_utc(conn):
    db.upsert_observations(conn, "price", "hour", [(T0 + i * H, float(i)) for i in range(5)])
    start = pd.Timestamp("2026-01-01 01:00", tz="UTC")
    # Same instant as 03:00 UTC, given in German time: must be converted, not misread.
    end = pd.Timestamp("2026-01-01 04:00", tz="Europe/Berlin")
    s = db.read_observations(conn, "price", "hour", start, end)
    assert s.tolist() == [1.0, 2.0]  # 01:00 and 02:00; 03:00 (= end) is excluded
    assert str(s.index.tz) == "UTC"


def test_read_rejects_naive_timestamp(conn):
    with pytest.raises(ValueError, match="timezone-aware"):
        db.read_observations(conn, "price", "hour", start=pd.Timestamp("2026-01-01"))


def test_unknown_series_is_rejected(conn):
    with pytest.raises(sqlite3.IntegrityError):
        db.upsert_observations(conn, "no_such_series", "hour", [(T0, 1.0)])
