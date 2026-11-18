"""Tests for the SMARD client. No network: all HTTP calls are mocked with `responses`.

How mocking works here: the `responses` library intercepts every HTTP request
made with `requests`. Each test registers fake answers for specific URLs
(``responses.get(url, json=...)``). A request to a URL that was *not*
registered raises an error, so the tests also prove that no unnecessary
downloads happen. Benefits: fast, reproducible, and independent of whether
smard.de is reachable.
"""

import pandas as pd
import pytest
import responses

from emi.smard import SERIES, SmardClient, SmardError

BASE = "https://www.smard.de/app/chart_data"
H = 3_600_000  # one hour in ms (60 * 60 * 1000)
WEEK = 168 * H  # one week = 168 hours
# An arbitrary start time, rounded down to a full hour (`%` = remainder of a division).
T0 = 1_700_000_000_000 - (1_700_000_000_000 % H)


# -- helpers that build fake URLs and fake API answers -------------------------


def _index_url(f=4169, region="DE-LU", res="hour"):
    """URL of the table of contents (API step 1)."""
    return f"{BASE}/{f}/{region}/index_{res}.json"


def _chunk_url(ts, f=4169, region="DE-LU", res="hour"):
    """URL of one weekly data file (API step 2)."""
    return f"{BASE}/{f}/{region}/{f}_{region}_{res}_{ts}.json"


def _chunk(ts, n=168, value=lambda i: float(i), nulls_from=None):
    """Fake chunk with ``n`` hourly values starting at ``ts``.

    By default the i-th hour has the value i (0.0, 1.0, 2.0, ...), which makes
    it easy to check *which* hours ended up in the result. From index
    ``nulls_from`` on, values are null (like future hours in the real API).
    """
    return {
        "series": [
            [ts + i * H, None if nulls_from is not None and i >= nulls_from else value(i)]
            for i in range(n)
        ]
    }


def _utc(ms):
    """Milliseconds since 1970 -> pandas Timestamp in UTC."""
    return pd.Timestamp(ms, unit="ms", tz="UTC")


# -- tests ---------------------------------------------------------------------


def test_series_catalogue_is_consistent():
    """The catalogue has no copy-paste errors."""
    ids = [s.filter_id for s in SERIES.values()]
    assert len(ids) == len(set(ids)), "duplicate filter id"  # a set drops duplicates
    assert SERIES["price"].aggregation == "mean"
    assert SERIES["load"].aggregation == "sum"
    assert {s.key for s in SERIES.values() if s.renewable} == {
        "wind_onshore",
        "wind_offshore",
        "solar",
        "biomass",
        "hydro",
        "other_renewable",
    }


# `@responses.activate` switches on the HTTP interception for this one test.
@responses.activate
def test_fetch_range_spans_chunks_and_clips():
    """A range across two weekly files is glued together and cut exactly."""
    weeks = [T0, T0 + WEEK, T0 + 2 * WEEK]
    responses.get(_index_url(), json={"timestamps": weeks})
    responses.get(_chunk_url(weeks[0]), json=_chunk(weeks[0]))
    # Second week has values 1000, 1001, ... so we can tell the weeks apart.
    responses.get(_chunk_url(weeks[1]), json=_chunk(weeks[1], value=lambda i: 1000.0 + i))
    # weeks[2] lies after `end` and must not be requested (responses would raise)

    client = SmardClient(retries=0)
    # From hour 100 of week 1 to hour 10 of week 2 (end excluded).
    s = client.fetch_range(4169, _utc(T0 + 100 * H), _utc(T0 + WEEK + 10 * H))

    assert len(s) == 68 + 10  # hours 100..167 of week 1 + hours 0..9 of week 2
    assert s.index[0] == _utc(T0 + 100 * H)  # start is included
    assert s.index[-1] == _utc(T0 + WEEK + 9 * H)  # end is excluded
    assert s.iloc[0] == 100.0
    assert s.iloc[-1] == 1009.0
    assert str(s.index.tz) == "UTC"


@responses.activate
def test_nulls_become_nan():
    """``null`` in the API becomes NaN in pandas (instead of crashing or becoming 0)."""
    responses.get(_index_url(), json={"timestamps": [T0]})
    responses.get(_chunk_url(T0), json=_chunk(T0, nulls_from=24))

    s = SmardClient(retries=0).fetch_range(4169, _utc(T0), _utc(T0 + WEEK))

    assert s.notna().sum() == 24  # first day has values
    assert s.isna().sum() == 144  # remaining 6 days are missing


# `tmp_path` is a pytest "fixture": pytest creates a fresh empty temporary
# folder for this test and passes its path in. It is cleaned up automatically.
@responses.activate
def test_finished_chunks_are_cached_newest_is_not(tmp_path):
    """Old weeks are downloaded once; the current week is downloaded every time."""
    weeks = [T0, T0 + WEEK]
    responses.get(_index_url(), json={"timestamps": weeks})
    old = responses.get(_chunk_url(weeks[0]), json=_chunk(weeks[0]))
    new = responses.get(_chunk_url(weeks[1]), json=_chunk(weeks[1]))
    client = SmardClient(cache_dir=tmp_path, retries=0)

    # Ask for the same data twice.
    for _ in range(2):
        client.fetch_range(4169, _utc(T0), _utc(T0 + 2 * WEEK))

    assert old.call_count == 1  # second time it came from the cache
    assert new.call_count == 2  # newest week: always fresh
    assert (tmp_path / f"4169_DE-LU_hour_{weeks[0]}.json").is_file()
    assert not (tmp_path / f"4169_DE-LU_hour_{weeks[1]}.json").exists()


@responses.activate
def test_http_error_raises_smard_error():
    """An HTTP error (here 404 "not found") surfaces as our own SmardError."""
    responses.get(_index_url(), status=404)
    # `pytest.raises` passes only if the code inside raises this exception,
    # and `match` checks that its message contains "failed".
    with pytest.raises(SmardError, match="failed"):
        SmardClient(retries=0).chunk_timestamps(4169, "DE-LU", "hour")


@responses.activate
def test_empty_index_raises():
    """An empty table of contents (e.g. wrong filter ID) is an error, not empty data."""
    responses.get(_index_url(), json={"timestamps": []})
    with pytest.raises(SmardError, match="no chunks"):
        SmardClient(retries=0).chunk_timestamps(4169, "DE-LU", "hour")


def test_naive_timestamps_are_rejected():
    """Timestamps without a timezone are refused, because they are ambiguous."""
    with pytest.raises(ValueError, match="timezone-aware"):
        SmardClient().fetch_range(4169, pd.Timestamp("2026-01-01"), pd.Timestamp("2026-01-02"))
