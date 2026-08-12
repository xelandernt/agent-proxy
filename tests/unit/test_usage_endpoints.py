from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException

from proxy.app.usage.endpoints import MAX_SERIES_POINTS, _resolve_bucket, _window
from proxy.app.usage.service import bucket_count


def test_bucket_count_includes_partially_covered_boundary_buckets() -> None:
    start = datetime(2026, 1, 1, 12, 0, 30, tzinfo=UTC)
    end = start + timedelta(minutes=1)

    assert bucket_count(start, end, "minute") == 2


def test_series_rejects_excessive_point_count() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    end = start + timedelta(minutes=MAX_SERIES_POINTS + 1)

    with pytest.raises(HTTPException, match="maximum") as error:
        _resolve_bucket(start, end, "minute")

    assert error.value.status_code == 422


def test_usage_window_rejects_more_than_one_year() -> None:
    start = datetime(2025, 1, 1, tzinfo=UTC)
    end = start + timedelta(days=367)

    with pytest.raises(HTTPException, match="cannot exceed") as error:
        _window(start, end)

    assert error.value.status_code == 422
