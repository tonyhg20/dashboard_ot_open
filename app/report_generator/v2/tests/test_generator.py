"""
Unit tests for v2 report generator — KPI computation and chart data assembly.
"""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import pytest

from app.report_generator.v2.generator import (
    KPI_CATEGORIES,
    KpiCard,
    ReportV2Generator,
)


class TestComputeKpis:
    """Test ``ReportV2Generator.compute_kpis()``.

    The method accepts a DataFrame with columns ``dia``, ``hub``, ``metric``,
    ``count``. It returns 4 ``KpiCard`` instances (total IN+TC, IN, TC, RA)
    with value, DoD %, trend direction, and 7-day sparkline.
    """

    def test_all_kpis_with_data(self) -> None:
        """Happy path: all categories have current + previous day data.

        Creates 7 days of monotonically increasing data for every
        categoria × hub combination so every KPI has positive values
        and a non-trivial DoD change.
        """
        max_day = date(2026, 7, 6)

        rows: list[dict] = []
        for i in range(7):
            d = max_day - timedelta(days=6 - i)
            rows.extend([
                {"dia": d, "hub": "ZAP", "metric": "IN", "count": 100 + i * 10},
                {"dia": d, "hub": "VIL", "metric": "IN", "count": 80 + i * 10},
                {"dia": d, "hub": "ZAP", "metric": "TC", "count": 60 + i * 5},
                {"dia": d, "hub": "VIL", "metric": "TC", "count": 50 + i * 5},
                {"dia": d, "hub": "ZAP", "metric": "RA", "count": 30 + i * 3},
                {"dia": d, "hub": "VIL", "metric": "RA", "count": 25 + i * 3},
            ])

        df = pd.DataFrame(rows)
        gen = ReportV2Generator.__new__(ReportV2Generator)
        kpis = gen.compute_kpis(df)

        assert len(kpis) == 4, "should return exactly 4 KPI cards"

        for kpi in kpis:
            assert isinstance(kpi, KpiCard)
            assert kpi.value > 0, f"{kpi.id} value should be positive, got {kpi.value}"
            assert kpi.change_pct != "", f"{kpi.id} change_pct should not be empty"
            assert kpi.trend in (
                "up",
                "down",
                "flat",
            ), f"{kpi.id} trend should be up/down/flat, got {kpi.trend!r}"
            assert len(kpi.sparkline_data) == 7, (
                f"{kpi.id} sparkline should have exactly 7 data points, "
                f"got {len(kpi.sparkline_data)}"
            )

    def test_kpi_ids_and_order(self) -> None:
        """KPI cards should be returned in the same order as KPI_CATEGORIES."""
        max_day = date(2026, 7, 6)
        rows = [
            {"dia": max_day, "hub": "ZAP", "metric": "IN", "count": 50},
            {"dia": max_day, "hub": "VIL", "metric": "TC", "count": 30},
            {"dia": max_day, "hub": "ZAP", "metric": "RA", "count": 10},
            {"dia": max_day - timedelta(days=1), "hub": "ZAP", "metric": "IN", "count": 40},
            {"dia": max_day - timedelta(days=1), "hub": "VIL", "metric": "TC", "count": 25},
            {"dia": max_day - timedelta(days=1), "hub": "ZAP", "metric": "RA", "count": 8},
        ]

        df = pd.DataFrame(rows)
        gen = ReportV2Generator.__new__(ReportV2Generator)
        kpis = gen.compute_kpis(df)

        expected_ids = list(KPI_CATEGORIES.keys())
        assert [k.id for k in kpis] == expected_ids, (
            f"KPI order should match {expected_ids}, got {[k.id for k in kpis]}"
        )

    def test_zero_data_kpi(self) -> None:
        """Edge case: no data for a specific KPI category.

        When RA tipo has zero records, the RA card should show value 0
        and change_pct "--".
        """
        max_day = date(2026, 7, 6)
        rows = [
            # Only IN data — no RA or TC
            {"dia": max_day, "hub": "ZAP", "metric": "IN", "count": 100},
            {"dia": max_day - timedelta(days=1), "hub": "ZAP", "metric": "IN", "count": 80},
        ]

        df = pd.DataFrame(rows)
        gen = ReportV2Generator.__new__(ReportV2Generator)
        kpis = gen.compute_kpis(df)

        ra_kpi = [k for k in kpis if k.id == "ra"][0]
        assert ra_kpi.value == 0, f"RA value should be 0, got {ra_kpi.value}"
        assert ra_kpi.change_pct in ("--",), (
            f"RA change_pct should be '--' when no data, got {ra_kpi.change_pct!r}"
        )
        assert ra_kpi.trend == "flat", "RA trend should be 'flat' with no data"

        # Other KPIs with data should still have positive values
        in_kpi = [k for k in kpis if k.id == "in"][0]
        assert in_kpi.value > 0
        assert in_kpi.change_pct != ""

    def test_empty_dataframe(self) -> None:
        """Edge case: empty DataFrame — all KPIs should return empty/zero."""
        df = pd.DataFrame(columns=["dia", "hub", "metric", "count"])
        gen = ReportV2Generator.__new__(ReportV2Generator)
        kpis = gen.compute_kpis(df)

        assert len(kpis) == 4
        for kpi in kpis:
            assert kpi.value == 0
            assert kpi.change_pct == "--"
            assert kpi.trend == "flat"
            assert kpi.sparkline_data == []

    def test_single_day_only(self) -> None:
        """Edge case: only one day of data — DoD should show '--' or no change."""
        max_day = date(2026, 7, 6)
        rows = [
            {"dia": max_day, "hub": "ZAP", "metric": "IN", "count": 100},
            {"dia": max_day, "hub": "ZAP", "metric": "TC", "count": 50},
            {"dia": max_day, "hub": "ZAP", "metric": "RA", "count": 20},
        ]

        df = pd.DataFrame(rows)
        gen = ReportV2Generator.__new__(ReportV2Generator)
        kpis = gen.compute_kpis(df)

        for kpi in kpis:
            # Yesterday val is 0, today val > 0 → "+100%"
            assert kpi.value >= 0
            if kpi.id == "ra":
                # Yesterday would be 0, but we have today data
                pass

        # Single day: total kpi should have value 150 (IN+TC)
        total_kpi = [k for k in kpis if k.id == "total"][0]
        assert total_kpi.value == 150
        # change_pct should be "+100%" since yesterday is 0 and today > 0
        assert total_kpi.change_pct == "+100%"

    def test_down_trend_on_decrease(self) -> None:
        """When today's value is lower than yesterday, trend should be 'down'."""
        max_day = date(2026, 7, 6)
        rows = [
            {"dia": max_day, "hub": "ZAP", "metric": "IN", "count": 50},
            {"dia": max_day - timedelta(days=1), "hub": "ZAP", "metric": "IN", "count": 100},
        ]

        df = pd.DataFrame(rows)
        gen = ReportV2Generator.__new__(ReportV2Generator)
        kpis = gen.compute_kpis(df)

        in_kpi = [k for k in kpis if k.id == "in"][0]
        assert in_kpi.trend == "down", "IN trend should be 'down' when value decreased"
        assert "-" in in_kpi.change_pct, (
            f"IN change_pct should be negative, got {in_kpi.change_pct!r}"
        )


class TestComputeChartData:
    """Test ``ReportV2Generator.compute_chart_data()``.

    The method accepts 4 DataFrames and returns a dict with 4 top-level keys
    matching the chart sections in the template.
    """

    def test_chart_data_structure(self) -> None:
        """Assert returned dict has all 4 datasets with correct top-level keys."""
        max_day = date(2026, 7, 6)

        # Build 12 days of data for all chart variants
        rows: list[dict] = []
        for i in range(12):
            d = max_day - timedelta(days=11 - i)
            for hub in ["ZAP", "VIL"]:
                for tipo in ["IN", "TC", "RA"]:
                    rows.append({"dia": d, "hub": hub, "metric": tipo, "count": 50 + i * 5})

        # Extra rows for per-hub latest (3 unique hub/tipo combos)
        rows.extend([
            {"dia": max_day, "hub": "ZAP", "metric": "IN", "count": 100},
            {"dia": max_day, "hub": "VIL", "metric": "TC", "count": 80},
            {"dia": max_day, "hub": "ZAP", "metric": "RA", "count": 30},
        ])

        df_7d = pd.DataFrame(rows[:72])  # first 72 rows (12 days)
        df_12d = pd.DataFrame(rows[:72])  # same — has RA data across 12 days
        df_hub = pd.DataFrame(rows[-3:])  # latest-day per-hub data
        df_fechaorden = pd.DataFrame([
            {"fechaorden": max_day, "metric": "IN", "count": 100},
            {"fechaorden": max_day, "metric": "TC", "count": 80},
        ])

        gen = ReportV2Generator.__new__(ReportV2Generator)
        chart_data = gen.compute_chart_data(df_7d, df_12d, df_hub, df_fechaorden)

        # All 4 chart keys must be present
        assert "lineas" in chart_data, "Missing 'lineas' key in chart_data"
        assert "barras_ra" in chart_data, "Missing 'barras_ra' key in chart_data"
        assert "fechaorden" in chart_data, "Missing 'fechaorden' key in chart_data"
        assert "hub" in chart_data, "Missing 'hub' key in chart_data"

    def test_lineas_chart_structure(self) -> None:
        """Lineas chart should have labels and two series (IN, TC)."""
        max_day = date(2026, 7, 6)
        rows = []
        for i in range(7):
            d = max_day - timedelta(days=6 - i)
            for hub in ["ZAP", "VIL"]:
                for tipo in ["IN", "TC", "RA"]:
                    rows.append({"dia": d, "hub": hub, "metric": tipo, "count": 50 + i * 5})

        df_7d = pd.DataFrame(rows)
        gen = ReportV2Generator.__new__(ReportV2Generator)
        chart_data = gen.compute_chart_data(
            df_7d, pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
        )

        lineas = chart_data["lineas"]
        assert len(lineas["labels"]) == 7, "Should have 7 day labels"
        assert len(lineas["series"]) == 2, "Should have 2 series (IN, TC)"

        series_names = {s["name"] for s in lineas["series"]}
        assert series_names == {"IN", "TC"}, f"Expected IN, TC series, got {series_names}"

        for series in lineas["series"]:
            assert len(series["values"]) == 7, (
                f"Series {series['name']} should have 7 values"
            )
            assert "color" in series
            assert "marker" in series

    def test_barras_ra_empty_when_no_data(self) -> None:
        """Barras RA should be empty when df_12d has no data."""
        max_day = date(2026, 7, 6)
        rows = [
            {"dia": max_day, "hub": "ZAP", "metric": "IN", "count": 100},
            {"dia": max_day - timedelta(days=1), "hub": "ZAP", "metric": "IN", "count": 80},
        ]

        df_7d = pd.DataFrame(rows)
        df_12d = pd.DataFrame(columns=["dia", "count"])  # empty RA data

        gen = ReportV2Generator.__new__(ReportV2Generator)
        chart_data = gen.compute_chart_data(
            df_7d, df_12d, pd.DataFrame(), pd.DataFrame()
        )

        assert chart_data["barras_ra"]["labels"] == []
        assert chart_data["barras_ra"]["values"] == []

    def test_fechaorden_empty_when_no_data(self) -> None:
        """Fechaorden chart should remain default when df_fechaorden is empty."""
        max_day = date(2026, 7, 6)
        rows = [
            {"dia": max_day, "hub": "ZAP", "metric": "IN", "count": 100},
        ]

        df_7d = pd.DataFrame(rows)
        gen = ReportV2Generator.__new__(ReportV2Generator)
        chart_data = gen.compute_chart_data(
            df_7d, pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
        )

        assert chart_data["fechaorden"]["categories"] == []
        assert chart_data["fechaorden"]["series"] == []

    def test_hub_empty_when_no_data(self) -> None:
        """Hub chart should remain default when df_hub_latest is empty."""
        max_day = date(2026, 7, 6)
        rows = [
            {"dia": max_day, "hub": "ZAP", "metric": "IN", "count": 100},
        ]

        df_7d = pd.DataFrame(rows)
        gen = ReportV2Generator.__new__(ReportV2Generator)
        chart_data = gen.compute_chart_data(
            df_7d, pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
        )

        assert chart_data["hub"]["hubs"] == []
        assert chart_data["hub"]["values"] == {}


class TestComputeAvgDays:
    """Test ``ReportV2Generator.compute_avg_days()``.

    The method accepts a DataFrame with columns ``metric``, ``dia``, ``avg_days``
    and returns a dict with avg values + DoD trends.
    """

    def test_both_metrics_with_trend(self) -> None:
        """Happy path: both metrics with today + yesterday data."""
        today = date(2026, 7, 17)
        yesterday = date(2026, 7, 16)
        df = pd.DataFrame([
            {"metric": "IN", "dia": today, "avg_days": 8.8},
            {"metric": "IN", "dia": yesterday, "avg_days": 8.5},
            {"metric": "TC", "dia": today, "avg_days": 4.5},
            {"metric": "TC", "dia": yesterday, "avg_days": 4.8},
        ])
        gen = ReportV2Generator.__new__(ReportV2Generator)
        result = gen.compute_avg_days(df)

        assert result["in_avg"] == 8.8
        assert result["in_trend"] == "up"
        assert result["in_change"] == 0.3
        assert result["tc_avg"] == 4.5
        assert result["tc_trend"] == "down"
        assert result["tc_change"] == -0.3

    def test_only_today_data(self) -> None:
        """Edge case: only one day of data — trends should be flat/None."""
        today = date(2026, 7, 17)
        df = pd.DataFrame([
            {"metric": "IN", "dia": today, "avg_days": 8.8},
            {"metric": "TC", "dia": today, "avg_days": 4.5},
        ])
        gen = ReportV2Generator.__new__(ReportV2Generator)
        result = gen.compute_avg_days(df)

        assert result["in_avg"] == 8.8
        assert result["in_trend"] == "flat"
        assert result["in_change"] is None
        assert result["tc_avg"] == 4.5
        assert result["tc_trend"] == "flat"
        assert result["tc_change"] is None

    def test_only_in_available(self) -> None:
        """Edge case: only IN data."""
        today = date(2026, 7, 17)
        df = pd.DataFrame([
            {"metric": "IN", "dia": today, "avg_days": 2.1},
        ])
        gen = ReportV2Generator.__new__(ReportV2Generator)
        result = gen.compute_avg_days(df)

        assert result["in_avg"] == 2.1
        assert result["tc_avg"] is None

    def test_only_tc_available(self) -> None:
        """Edge case: only TC data."""
        today = date(2026, 7, 17)
        df = pd.DataFrame([
            {"metric": "TC", "dia": today, "avg_days": 5.3},
        ])
        gen = ReportV2Generator.__new__(ReportV2Generator)
        result = gen.compute_avg_days(df)

        assert result["tc_avg"] == 5.3
        assert result["in_avg"] is None

    def test_empty_dataframe(self) -> None:
        """Edge case: no data at all."""
        df = pd.DataFrame(columns=["metric", "dia", "avg_days"])
        gen = ReportV2Generator.__new__(ReportV2Generator)
        result = gen.compute_avg_days(df)

        assert result["in_avg"] is None
        assert result["tc_avg"] is None
        assert result["in_trend"] == "flat"
        assert result["tc_trend"] == "flat"

    def test_flat_trend(self) -> None:
        """When today equals yesterday, trend should be 'flat'."""
        today = date(2026, 7, 17)
        yesterday = date(2026, 7, 16)
        df = pd.DataFrame([
            {"metric": "IN", "dia": today, "avg_days": 5.0},
            {"metric": "IN", "dia": yesterday, "avg_days": 5.0},
        ])
        gen = ReportV2Generator.__new__(ReportV2Generator)
        result = gen.compute_avg_days(df)

        assert result["in_avg"] == 5.0
        assert result["in_trend"] == "flat"
        assert result["in_change"] == 0.0

    def test_down_trend(self) -> None:
        """When today is lower than yesterday, trend should be 'down'."""
        today = date(2026, 7, 17)
        yesterday = date(2026, 7, 16)
        df = pd.DataFrame([
            {"metric": "TC", "dia": today, "avg_days": 3.2},
            {"metric": "TC", "dia": yesterday, "avg_days": 4.1},
        ])
        gen = ReportV2Generator.__new__(ReportV2Generator)
        result = gen.compute_avg_days(df)

        assert result["tc_avg"] == 3.2
        assert result["tc_trend"] == "down"
        assert result["tc_change"] == -0.9


class TestComputeAsignadas:
    """Test ``ReportV2Generator.compute_asignadas()``.

    The method accepts a DataFrame with columns ``metric``, ``total``,
    ``asignadas`` and returns a dict with counts + percentages.
    """

    def test_both_metrics_with_data(self) -> None:
        """Happy path: IN and TC both have assigned and total data."""
        df = pd.DataFrame([
            {"metric": "IN", "total": 200, "asignadas": 175},
            {"metric": "TC", "total": 150, "asignadas": 130},
        ])
        gen = ReportV2Generator.__new__(ReportV2Generator)
        result = gen.compute_asignadas(df)

        assert result["in_asignadas"] == 175
        assert result["in_total"] == 200
        assert result["in_pct"] == 87.5
        assert result["tc_asignadas"] == 130
        assert result["tc_total"] == 150
        assert result["tc_pct"] == pytest.approx(86.7, rel=0.1)

    def test_all_assigned(self) -> None:
        """Edge case: all orders are assigned."""
        df = pd.DataFrame([
            {"metric": "IN", "total": 100, "asignadas": 100},
            {"metric": "TC", "total": 50, "asignadas": 50},
        ])
        gen = ReportV2Generator.__new__(ReportV2Generator)
        result = gen.compute_asignadas(df)

        assert result["in_pct"] == 100.0
        assert result["tc_pct"] == 100.0

    def test_none_assigned(self) -> None:
        """Edge case: no orders are assigned."""
        df = pd.DataFrame([
            {"metric": "IN", "total": 100, "asignadas": 0},
            {"metric": "TC", "total": 50, "asignadas": 0},
        ])
        gen = ReportV2Generator.__new__(ReportV2Generator)
        result = gen.compute_asignadas(df)

        assert result["in_asignadas"] == 0
        assert result["in_pct"] == 0.0
        assert result["tc_asignadas"] == 0
        assert result["tc_pct"] == 0.0

    def test_only_in_available(self) -> None:
        """Edge case: only IN data — TC defaults."""
        df = pd.DataFrame([
            {"metric": "IN", "total": 50, "asignadas": 40},
        ])
        gen = ReportV2Generator.__new__(ReportV2Generator)
        result = gen.compute_asignadas(df)

        assert result["in_asignadas"] == 40
        assert result["in_pct"] == 80.0
        assert result["tc_asignadas"] == 0
        assert result["tc_total"] == 0
        assert result["tc_pct"] is None

    def test_empty_dataframe(self) -> None:
        """Edge case: no data at all."""
        df = pd.DataFrame(columns=["metric", "total", "asignadas"])
        gen = ReportV2Generator.__new__(ReportV2Generator)
        result = gen.compute_asignadas(df)

        assert result["in_asignadas"] == 0
        assert result["in_total"] == 0
        assert result["in_pct"] is None
        assert result["tc_asignadas"] == 0
        assert result["tc_total"] == 0
        assert result["tc_pct"] is None
