from __future__ import annotations

import pandas as pd

from app import _linear_projection
from app import compute_data_quality_summary
from app import filter_dataset
from app import format_compact_currency
from app import split_pipe_values


def test_split_pipe_values_trims_and_drops_empty_tokens() -> None:
    series = pd.Series(["Action| Drama", "Comedy|", None, "", "Thriller | Mystery"])
    result = split_pipe_values(series).tolist()

    assert result == ["Action", "Drama", "Comedy", "Thriller", "Mystery"]


def test_format_compact_currency_handles_ranges() -> None:
    assert format_compact_currency(2_500_000_000) == "$2.50B"
    assert format_compact_currency(8_250_000) == "$8.25M"
    assert format_compact_currency(54_000) == "$54.00K"
    assert format_compact_currency(999) == "$999"


def test_filter_dataset_by_year_and_exact_genre_match() -> None:
    df = pd.DataFrame(
        {
            "id": [1, 2, 3, 4],
            "release_year": [2010, 2015, 2020, 2021],
            "genres": ["Action|Adventure", "Drama", "Comedy|Action", "Action (Sci-Fi)?|Drama"],
        }
    )

    filtered = filter_dataset(df, (2012, 2021), ["Action (Sci-Fi)?"])

    assert len(filtered) == 1
    assert int(filtered.iloc[0]["id"]) == 4


def test_linear_projection_appends_projected_horizon() -> None:
    projection = _linear_projection([2018, 2019, 2020], [10.0, 20.0, 30.0], horizon=3)

    assert len(projection) == 6
    assert projection["series"].tolist() == [
        "Historical",
        "Historical",
        "Historical",
        "Projected",
        "Projected",
        "Projected",
    ]
    assert projection.iloc[-1]["year"] == 2023


def test_compute_data_quality_summary_core_metrics() -> None:
    df = pd.DataFrame(
        {
            "release_date": pd.to_datetime(["2020-01-01", None, "2020-03-01", "2020-04-01", "2020-05-01"]),
            "budget": [100, 0, 120, 150, 200],
            "revenue": [200, 0, 240, 300, 10_000],
            "profit": [100, 0, 120, 150, 9_800],
            "vote_average": [6.5, 7.0, None, 8.0, 7.5],
        }
    )

    summary = compute_data_quality_summary(df)

    assert summary["total_rows"] == 5
    assert summary["duplicate_rows"] == 0
    assert summary["invalid_dates"] == 1
    assert summary["invalid_financial"] == 1
    assert summary["missing_cells"] == 2
    assert isinstance(summary["missing_table"], pd.DataFrame)
