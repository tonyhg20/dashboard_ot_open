"""
Executive Report — ReportGenerator orchestrator.

The ``ReportGenerator`` class coordinates the full report pipeline:

    1. Fetch data via SQL queries (psycopg2, raw SQL — consistent with codebase)
    2. Generate charts by calling chart modules (imported from ``.charts``)
    3. Compute KPI metrics and insights from fetched data
    4. Render the Jinja2 template to an HTML string
    5. Return a ``ReportResult`` dataclass

Thread-safety
-------------
All chart generation uses matplotlib's Agg backend set in ``.charts.styles``.
Each chart call opens a fresh figure in a local ``chart_context`` and closes
it on return.  No shared figure state.

No filesystem writes
--------------------
Charts are rendered to in-memory ``BytesIO`` buffers → base64 PNG data URIs.
Templates are rendered to strings.  No temporary files are created.
"""

from __future__ import annotations

import io
import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any

import psycopg2.extras
import pandas as pd
from jinja2 import Environment, FileSystemLoader, BaseLoader, select_autoescape

from .charts import (
    create_bar_chart,
    create_bullet_chart,
    create_donut,
    create_small_multiples,
    create_sparkline,
    create_trend_chart,
)

log = logging.getLogger(__name__)

# ── Jinja2 environment ─────────────────────────────────────────────────────

_TEMPLATE_DIR = __file__.rsplit("/", 1)[0] + "/templates"

_jinja_env = Environment(
    loader=FileSystemLoader(_TEMPLATE_DIR),
    autoescape=select_autoescape(["html", "xml"]),
)

# ── Helpers ────────────────────────────────────────────────────────────────


def _data_uri(raw_b64: str) -> str:
    """Prefix a raw base64 string with the PNG data-URI scheme."""
    return f"data:image/png;base64,{raw_b64}"


def _compute_period_label(dia: date) -> str:
    """Return a human-readable label for the last 5 days."""
    start = dia - timedelta(days=4)
    months_short = [
        "Ene", "Feb", "Mar", "Abr", "May", "Jun",
        "Jul", "Ago", "Sep", "Oct", "Nov", "Dic",
    ]
    if start.month == dia.month:
        return f"Últimos 5 días: {start.day}-{dia.day} {months_short[dia.month - 1]} {dia.year}"
    return (
        f"Últimos 5 días: {start.day} {months_short[start.month - 1]} - "
        f"{dia.day} {months_short[dia.month - 1]} {dia.year}"
    )


# ── ReportResult ───────────────────────────────────────────────────────────


@dataclass
class ReportResult:
    """Container returned by ``ReportGenerator.generate_report()``."""

    html: str
    subject: str
    metrics: dict[str, Any] = field(default_factory=dict)
    charts: dict[str, Any] = field(default_factory=dict)
    period: str = "weekly"
    generated_at: str = ""


# ── ReportGenerator ────────────────────────────────────────────────────────


class ReportGenerator:
    """Orchestrator: SQL → charts → Jinja2 → HTML string.

    Parameters
    ----------
    db_config : dict
        psycopg2 connection parameters (``host``, ``port``, ``database``,
        ``user``, ``password``).  Pass ``app.db.DB_CONFIG`` directly.
    logo_base64 : str | None
        Optional base64-encoded logo PNG (raw, without the ``data:`` prefix).
        Will be inserted as ``data:image/png;base64,...`` in the email header.
    """

    def __init__(
        self,
        db_config: dict[str, Any],
        *,
        logo_base64: str | None = None,
    ):
        self._db = dict(db_config)
        self._logo_uri = (
            _data_uri(logo_base64) if logo_base64 else None
        )

    # ── Public API ─────────────────────────────────────────────────────────

    def generate_report(
        self,
        hub_ids: list[str],
        period: str = "weekly",
        dia: date | None = None,
    ) -> ReportResult:
        """Run the full report pipeline and return the result.

        Parameters
        ----------
        hub_ids : list[str]
            Hub codes (e.g. ``["ZAP", "VIL"]``).
        period : str
            ``"weekly"`` (default) or ``"monthly"``.
        dia : date | None
            Reference date.  ``None`` → latest available date in the database.

        Returns
        -------
        ReportResult
        """
        if dia is None:
            dia = self._resolve_latest_date(hub_ids)

        # 1. Fetch data
        daily_df = self.query_daily_trends(hub_ids, dia)
        hub_daily_df = self.query_hub_daily(hub_ids, dia)
        summary = self.query_period_summary(hub_ids, dia)
        hub_comp = self.query_hub_comparison(hub_ids, dia)

        # 2. Compute KPIs
        metrics = self._compute_kpis(daily_df, summary, hub_comp)

        # 3. Generate charts
        charts = self._generate_charts(
            daily_df, hub_daily_df, summary, hub_comp, hub_ids, dia,
        )

        # 4. Build insights
        insights = self._build_insights(metrics, hub_comp, dia)

        # 5. Build context
        period_label = _compute_period_label(dia)
        subject = f"Executive Report — OS Open — {period_label}"
        now_str = datetime.now().strftime("%d/%m/%Y %H:%M")

        # Date range for template
        start = dia - timedelta(days=4)
        months_full = [
            "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
            "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
        ]
        if start.month == dia.month:
            date_range = f"{start.day} al {dia.day} {months_full[dia.month - 1]}, {dia.year}"
        else:
            date_range = (
                f"{start.day} {months_full[start.month - 1]} al "
                f"{dia.day} {months_full[dia.month - 1]}, {dia.year}"
            )

        # Format KPIs for the template
        kpi_list = [
            {
                "name": "Total OS",
                "value": str(metrics["total_os"]),
                "sparkline": charts.get("sparkline_os"),
                "trend": metrics.get("os_trend", "flat"),
                "change": metrics.get("os_change_pct", "0%"),
            },
            {
                "name": "Instalaciones",
                "value": str(metrics["in_count"]),
                "sparkline": charts.get("sparkline_in"),
                "trend": metrics.get("in_trend", "flat"),
                "change": metrics.get("in_change_pct", "0%"),
            },
            {
                "name": "Trouble Calls",
                "value": str(metrics["tc_count"]),
                "sparkline": charts.get("sparkline_tc"),
                "trend": metrics.get("tc_trend", "flat"),
                "change": metrics.get("tc_change_pct", "0%"),
            },
            {
                "name": "IN/TC Ratio",
                "value": f"{metrics['in_tc_ratio']:.1f}",
                "sparkline": None,
                "trend": (
                    "up"
                    if metrics.get("ratio_change", 0) > 0
                    else "down" if metrics.get("ratio_change", 0) < 0
                    else "flat"
                ),
                "change": (
                    f"+{metrics['ratio_change']:.1f}"
                    if metrics.get("ratio_change", 0) > 0
                    else f"{metrics['ratio_change']:.1f}"
                    if metrics.get("ratio_change", 0) < 0
                    else "0.0"
                ),
            },
        ]

        context: dict[str, Any] = {
            "report_title": "Executive Report",
            "period_label": period_label,
            "date_range": date_range,
            "date": dia.strftime("%d %B %Y"),
            "hubs": sorted(hub_ids),
            "kpis": kpi_list,
            "daily_totals": metrics.get("daily_totals", []),
            "charts": {
                "trend": charts.get("trend"),
                "comparison": charts.get("comparison"),
                "distribution": charts.get("distribution"),
                "hub_tc": charts.get("hub_tc"),
                "hub_daily": charts.get("hub_daily"),
            },
            "insights": insights,
            "logo": self._logo_uri,
            "generated_at": now_str,
            "period": period,
        }

        # 6. Render HTML
        html = _jinja_env.get_template("executive.html").render(**context)

        return ReportResult(
            html=html,
            subject=subject,
            metrics=metrics,
            charts=charts,
            period=period,
            generated_at=now_str,
        )

    # ── SQL Queries ────────────────────────────────────────────────────────

    def query_daily_trends(
        self,
        hub_ids: list[str],
        dia: date,
    ) -> pd.DataFrame:
        """Daily counts of IN/TC/Rx/RA/Dx for the last 5 days (all hubs combined).

        Returns
        -------
        pd.DataFrame
            Columns: ``date``, ``metric``, ``value``.
        """
        import psycopg2  # noqa: PLC0415

        start = dia - timedelta(days=4)

        sql = """
            SELECT
                dia::date AS date,
                CASE
                    WHEN tipo IN ('Cambio de Domicilio','Cambio de Equipo',
                                  'Cambio de Servicios','Cambio de Ubicacion',
                                  'Instalacion')
                        THEN 'IN'
                    WHEN tipo IN ('Trouble Call Telefonia','Trouble Call Cablemodem',
                                  'Trouble Call Video','Trouble Call House Check',
                                  'Trouble Call')
                        THEN 'TC'
                    WHEN tipo = 'Reconexion Pago' THEN 'Rx'
                    WHEN tipo = 'No Pago - Filtro de Video' THEN 'Dx'
                    WHEN tipo = 'Recoleccion Acometida' THEN 'RA'
                    ELSE 'Otro'
                END AS metric,
                COUNT(*) AS value
            FROM abiertas
            WHERE hub = ANY(%(hubs)s)
              AND dia::date >= %(start)s
              AND dia::date <= %(end)s
              AND tipo IS NOT NULL AND tipo != ''
            GROUP BY dia::date, metric
            ORDER BY dia::date, metric
        """

        rows: list[dict[str, Any]] = []
        conn = psycopg2.connect(**self._db)
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(sql, {
                    "hubs": hub_ids,
                    "start": start,
                    "end": dia,
                })
                for row in cur:
                    metric = row["metric"]
                    if metric != "Otro":
                        rows.append({
                            "date": row["date"],
                            "metric": metric,
                            "value": row["value"],
                        })
        finally:
            conn.close()

        if not rows:
            return pd.DataFrame(columns=["date", "metric", "value"])

        df = pd.DataFrame(rows)
        df["date"] = pd.to_datetime(df["date"])
        return df

    def query_hub_daily(
        self,
        hub_ids: list[str],
        dia: date,
    ) -> pd.DataFrame:
        """Daily counts per hub AND metric for the last 5 days.

        Returns
        -------
        pd.DataFrame
            Columns: ``date``, ``hub``, ``metric``, ``value``.
        """
        import psycopg2  # noqa: PLC0415

        start = dia - timedelta(days=4)

        sql = """
            SELECT
                dia::date AS date,
                hub,
                CASE
                    WHEN tipo IN ('Cambio de Domicilio','Cambio de Equipo',
                                  'Cambio de Servicios','Cambio de Ubicacion',
                                  'Instalacion')
                        THEN 'IN'
                    WHEN tipo IN ('Trouble Call Telefonia','Trouble Call Cablemodem',
                                  'Trouble Call Video','Trouble Call House Check',
                                  'Trouble Call')
                        THEN 'TC'
                    WHEN tipo = 'Reconexion Pago' THEN 'Rx'
                    WHEN tipo = 'No Pago - Filtro de Video' THEN 'Dx'
                    WHEN tipo = 'Recoleccion Acometida' THEN 'RA'
                    ELSE 'Otro'
                END AS metric,
                COUNT(*) AS value
            FROM abiertas
            WHERE hub = ANY(%(hubs)s)
              AND dia::date >= %(start)s
              AND dia::date <= %(end)s
              AND tipo IS NOT NULL AND tipo != ''
            GROUP BY dia::date, hub, metric
            ORDER BY dia::date, hub, metric
        """

        rows: list[dict[str, Any]] = []
        conn = psycopg2.connect(**self._db)
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(sql, {
                    "hubs": hub_ids,
                    "start": start,
                    "end": dia,
                })
                for row in cur:
                    metric = row["metric"]
                    if metric != "Otro":
                        rows.append({
                            "date": row["date"],
                            "hub": row["hub"],
                            "metric": metric,
                            "value": row["value"],
                        })
        finally:
            conn.close()

        if not rows:
            return pd.DataFrame(columns=["date", "hub", "metric", "value"])

        df = pd.DataFrame(rows)
        df["date"] = pd.to_datetime(df["date"])
        return df

    def query_period_summary(
        self,
        hub_ids: list[str],
        dia: date,
    ) -> dict[str, int]:
        """Total counts per category for a given date.

        Returns
        -------
        dict
            Keys: ``"IN"``, ``"TC"``, ``"Rx"``, ``"Dx"``, ``"RA"``, ``"total"``.
        """
        import psycopg2  # noqa: PLC0415

        sql = """
            SELECT
                COUNT(*) FILTER (WHERE tipo IN ('Cambio de Domicilio','Cambio de Equipo',
                                                 'Cambio de Servicios','Cambio de Ubicacion',
                                                 'Instalacion')) AS in_count,
                COUNT(*) FILTER (WHERE tipo IN ('Trouble Call Telefonia','Trouble Call Cablemodem',
                                                 'Trouble Call Video','Trouble Call House Check',
                                                 'Trouble Call')) AS tc_count,
                COUNT(*) FILTER (WHERE tipo = 'Reconexion Pago') AS rx_count,
                COUNT(*) FILTER (WHERE tipo = 'No Pago - Filtro de Video') AS dx_count,
                COUNT(*) FILTER (WHERE tipo = 'Recoleccion Acometida') AS ra_count
            FROM abiertas
            WHERE hub = ANY(%(hubs)s)
              AND dia::date = %(dia)s
        """

        conn = psycopg2.connect(**self._db)
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(sql, {"hubs": hub_ids, "dia": dia})
                row = cur.fetchone()
        finally:
            conn.close()

        if row is None:
            return {"IN": 0, "TC": 0, "Rx": 0, "Dx": 0, "RA": 0, "total": 0}

        result = {
            "IN": row["in_count"] or 0,
            "TC": row["tc_count"] or 0,
            "Rx": row["rx_count"] or 0,
            "Dx": row["dx_count"] or 0,
            "RA": row["ra_count"] or 0,
        }
        result["total"] = sum(result.values())
        return result

    def query_hub_comparison(
        self,
        hub_ids: list[str],
        dia: date,
    ) -> pd.DataFrame:
        """Per-hub category breakdown for a given date.

        Returns
        -------
        pd.DataFrame
            Columns: ``hub``, ``metric``, ``value``.
        """
        import psycopg2  # noqa: PLC0415

        sql = """
            SELECT
                hub,
                COUNT(*) FILTER (WHERE tipo IN ('Cambio de Domicilio','Cambio de Equipo',
                                                 'Cambio de Servicios','Cambio de Ubicacion',
                                                 'Instalacion')) AS in_count,
                COUNT(*) FILTER (WHERE tipo IN ('Trouble Call Telefonia','Trouble Call Cablemodem',
                                                 'Trouble Call Video','Trouble Call House Check',
                                                 'Trouble Call')) AS tc_count,
                COUNT(*) FILTER (WHERE tipo = 'Reconexion Pago') AS rx_count,
                COUNT(*) FILTER (WHERE tipo = 'No Pago - Filtro de Video') AS dx_count,
                COUNT(*) FILTER (WHERE tipo = 'Recoleccion Acometida') AS ra_count
            FROM abiertas
            WHERE hub = ANY(%(hubs)s)
              AND dia::date = %(dia)s
            GROUP BY hub
            ORDER BY hub
        """

        conn = psycopg2.connect(**self._db)
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(sql, {"hubs": hub_ids, "dia": dia})
                raw = cur.fetchall()
        finally:
            conn.close()

        rows: list[dict[str, Any]] = []
        for row in raw:
            for metric, col in [("IN", "in_count"), ("TC", "tc_count"),
                                ("Rx", "rx_count"), ("Dx", "dx_count"),
                                ("RA", "ra_count")]:
                rows.append({
                    "hub": row["hub"],
                    "metric": metric,
                    "value": row[col] or 0,
                })

        return pd.DataFrame(rows) if rows else pd.DataFrame(columns=["hub", "metric", "value"])

    # ── Private helpers ────────────────────────────────────────────────────

    def _resolve_latest_date(self, hub_ids: list[str]) -> date:
        """Find the latest ``dia`` present in ``abiertas`` for the given hubs."""
        import psycopg2  # noqa: PLC0415

        sql = "SELECT MAX(dia::date) AS max_dia FROM abiertas WHERE hub = ANY(%(hubs)s)"

        conn = psycopg2.connect(**self._db)
        try:
            with conn.cursor() as cur:
                cur.execute(sql, {"hubs": hub_ids})
                row = cur.fetchone()
        finally:
            conn.close()

        if row and row[0]:
            return row[0]
        return date.today()

    def _compute_kpis(
        self,
        daily_df: pd.DataFrame,
        summary: dict[str, int],
        hub_comp: pd.DataFrame,
    ) -> dict[str, Any]:
        """Derive all KPI metrics from fetched data.

        Uses day-over-day comparison (last day vs previous day).
        """
        result: dict[str, Any] = {}

        # Basic counts from period summary (latest day)
        result["total_os"] = summary.get("total", 0)
        result["in_count"] = summary.get("IN", 0)
        result["tc_count"] = summary.get("TC", 0)
        result["dx_count"] = summary.get("Dx", 0)
        result["rx_count"] = summary.get("Rx", 0)
        result["ra_count"] = summary.get("RA", 0)

        # IN/TC ratio
        tc = result["tc_count"]
        result["in_tc_ratio"] = round(result["in_count"] / tc, 2) if tc > 0 else 0.0

        # Day-over-day changes from daily_df
        if not daily_df.empty:
            days = sorted(daily_df["date"].unique())
            if len(days) >= 2:
                latest_day = days[-1]
                prev_day = days[-2]

                def _day_sum(df: pd.DataFrame, d: pd.Timestamp, metric: str | None = None) -> float:
                    if metric:
                        mask = (df["date"] == d) & (df["metric"] == metric)
                    else:
                        mask = df["date"] == d
                    return float(df.loc[mask, "value"].sum())

                latest_total = _day_sum(daily_df, latest_day)
                prev_total = _day_sum(daily_df, prev_day)

                # OS trend
                if prev_total > 0:
                    pct = ((latest_total - prev_total) / prev_total) * 100
                    result["os_change_pct"] = f"{pct:+.0f}%"
                    result["os_trend"] = "up" if pct > 2 else "down" if pct < -2 else "flat"
                else:
                    result["os_change_pct"] = "0%"
                    result["os_trend"] = "flat"

                # IN trend
                latest_in = _day_sum(daily_df, latest_day, "IN")
                prev_in = _day_sum(daily_df, prev_day, "IN")
                if prev_in > 0:
                    pct = ((latest_in - prev_in) / prev_in) * 100
                    result["in_change_pct"] = f"{pct:+.0f}%"
                    result["in_trend"] = "up" if pct > 2 else "down" if pct < -2 else "flat"
                else:
                    result["in_change_pct"] = "0%"
                    result["in_trend"] = "flat"

                # TC trend
                latest_tc = _day_sum(daily_df, latest_day, "TC")
                prev_tc = _day_sum(daily_df, prev_day, "TC")
                if prev_tc > 0:
                    pct = ((latest_tc - prev_tc) / prev_tc) * 100
                    result["tc_change_pct"] = f"{pct:+.0f}%"
                    result["tc_trend"] = "up" if pct > 2 else "down" if pct < -2 else "flat"
                else:
                    result["tc_change_pct"] = "0%"
                    result["tc_trend"] = "flat"

                # Ratio day-over-day change
                latest_in_sum = _day_sum(daily_df, latest_day, "IN")
                latest_tc_sum = _day_sum(daily_df, latest_day, "TC")
                prev_in_sum = _day_sum(daily_df, prev_day, "IN")
                prev_tc_sum = _day_sum(daily_df, prev_day, "TC")

                latest_ratio = latest_in_sum / latest_tc_sum if latest_tc_sum > 0 else 0
                prev_ratio = prev_in_sum / prev_tc_sum if prev_tc_sum > 0 else 0
                result["ratio_change"] = round(latest_ratio - prev_ratio, 2)
            else:
                # Only one day of data — no day-over-day comparison possible
                result["os_change_pct"] = "0%"
                result["os_trend"] = "flat"
                result["in_change_pct"] = "0%"
                result["in_trend"] = "flat"
                result["tc_change_pct"] = "0%"
                result["tc_trend"] = "flat"
                result["ratio_change"] = 0.0
        else:
            # No daily data
            result["os_change_pct"] = "0%"
            result["os_trend"] = "flat"
            result["in_change_pct"] = "0%"
            result["in_trend"] = "flat"
            result["tc_change_pct"] = "0%"
            result["tc_trend"] = "flat"
            result["ratio_change"] = 0.0

        # Daily totals for the template
        months_short = [
            "Ene", "Feb", "Mar", "Abr", "May", "Jun",
            "Jul", "Ago", "Sep", "Oct", "Nov", "Dic",
        ]
        daily_totals: list[dict[str, Any]] = []
        if not daily_df.empty:
            day_totals = daily_df.groupby("date")["value"].sum().sort_index()
            for d, total in day_totals.items():
                daily_totals.append({
                    "date": f"{d.day} {months_short[d.month - 1]}",
                    "total": int(total),
                })
        result["daily_totals"] = daily_totals

        return result

    def _generate_charts(
        self,
        daily_df: pd.DataFrame,
        hub_daily_df: pd.DataFrame,
        summary: dict[str, int],
        hub_comp: pd.DataFrame,
        hub_ids: list[str],
        dia: date,
    ) -> dict[str, Any]:
        """Generate all charts, returning a dict of data-URI base64 strings."""
        charts: dict[str, Any] = {}

        # ── Sparklines from daily_df (5-day overall values) ──────────────
        if not daily_df.empty:
            os_daily = (
                daily_df.groupby("date")["value"]
                .sum()
                .sort_index()
                .tolist()
            )
            if os_daily:
                charts["sparkline_os"] = _data_uri(
                    create_sparkline(os_daily)["base64"]
                )

            in_daily = (
                daily_df[daily_df["metric"] == "IN"]
                .groupby("date")["value"]
                .sum()
                .sort_index()
                .tolist()
            )
            if in_daily:
                from .charts.styles import CATEGORY_COLORS  # noqa: PLC0415
                charts["sparkline_in"] = _data_uri(
                    create_sparkline(in_daily, color=CATEGORY_COLORS["IN"])["base64"]
                )

            tc_daily = (
                daily_df[daily_df["metric"] == "TC"]
                .groupby("date")["value"]
                .sum()
                .sort_index()
                .tolist()
            )
            if tc_daily:
                charts["sparkline_tc"] = _data_uri(
                    create_sparkline(tc_daily, color=CATEGORY_COLORS["TC"])["base64"]
                )

        # ── Trend chart from daily_df ────────────────────────────────────
        if not daily_df.empty:
            charts["trend"] = _data_uri(
                create_trend_chart(daily_df)["base64"]
            )

        # ── Hub daily chart (grouped bars per hub per day) ──────────────
        if not hub_daily_df.empty:
            tc_daily_hub = hub_daily_df[hub_daily_df["metric"] == "TC"].copy()
            if not tc_daily_hub.empty:
                tc_daily_hub["category"] = (
                    tc_daily_hub["date"].dt.strftime("%d/%m") + " " + tc_daily_hub["hub"]
                )
                charts["hub_daily"] = _data_uri(
                    create_bar_chart(
                        tc_daily_hub[["category", "value"]],
                        horizontal=False,
                        figsize=(3.0, 1.8),
                    )["base64"]
                )

        # ── Hub comparison (small multiples) ─────────────────────────────
        if not hub_comp.empty and len(hub_ids) > 1:
            charts["comparison"] = _data_uri(
                create_small_multiples(hub_comp)["base64"]
            )

        # ── Distribution donut ───────────────────────────────────────────
        dist_rows = [
            {"category": k, "value": v}
            for k, v in summary.items()
            if k in ("IN", "TC", "Rx", "Dx", "RA") and v > 0
        ]
        if dist_rows:
            dist_df = pd.DataFrame(dist_rows)
            charts["distribution"] = _data_uri(
                create_donut(dist_df, category_col="category", value_col="value")["base64"]
            )

        # ── Hub TC comparison bar ────────────────────────────────────────
        if not hub_comp.empty:
            tc_by_hub = hub_comp[hub_comp["metric"] == "TC"].copy()
            if not tc_by_hub.empty:
                tc_by_hub["category"] = tc_by_hub["hub"]
                tc_by_hub["label"] = tc_by_hub["hub"]
                charts["hub_tc"] = _data_uri(
                    create_bar_chart(
                        tc_by_hub[["category", "value"]],
                        horizontal=False,
                        figsize=(2.0, 1.5),
                    )["base64"]
                )

        return charts

    def _build_insights(
        self,
        metrics: dict[str, Any],
        hub_comp: pd.DataFrame,
        dia: date,
    ) -> list[str]:
        """Generate auto‑narrative insights from KPIs and hub data."""
        insights: list[str] = []

        # IN change
        in_pct = metrics.get("in_change_pct", "0%")
        in_trend = metrics.get("in_trend", "flat")
        if in_trend == "up":
            insights.append(
                f"IN incrementó {in_pct} vs día anterior — "
                "tendencia positiva en instalaciones"
            )
        elif in_trend == "down":
            insights.append(
                f"IN disminuyó {in_pct} vs día anterior — "
                "requiere atención en el proceso de instalaciones"
            )

        # TC change
        tc_pct = metrics.get("tc_change_pct", "0%")
        tc_trend = metrics.get("tc_trend", "flat")
        if tc_trend == "up":
            insights.append(
                f"TC aumentó {tc_pct} vs día anterior — "
                "incremento en Trouble Calls que puede indicar problemas de calidad"
            )
        elif tc_trend == "down":
            insights.append(
                f"TC se redujo {tc_pct} vs día anterior — "
                "mejora en indicadores de calidad"
            )

        # IN/TC ratio
        ratio = metrics.get("in_tc_ratio", 0)
        ratio_change = metrics.get("ratio_change", 0)
        if ratio > 0:
            if ratio_change > 0:
                insights.append(
                    f"Ratio IN/TC mejora a {ratio:.2f} "
                    f"(+{ratio_change:.2f} vs día anterior)"
                )
            elif ratio_change < 0:
                insights.append(
                    f"Ratio IN/TC se reduce a {ratio:.2f} "
                    f"({ratio_change:.2f} vs día anterior)"
                )
            else:
                insights.append(
                    f"Ratio IN/TC se mantiene en {ratio:.2f}"
                )

        # Hub comparison insights
        if not hub_comp.empty:
            metrics_in_data = hub_comp["metric"].unique()
            if "TC" in metrics_in_data:
                tc_by_hub = hub_comp[hub_comp["metric"] == "TC"]
                if len(tc_by_hub) > 1:
                    max_tc_row = tc_by_hub.loc[tc_by_hub["value"].idxmax()]
                    min_tc_row = tc_by_hub.loc[tc_by_hub["value"].idxmin()]
                    if max_tc_row["value"] > min_tc_row["value"]:
                        insights.append(
                            f"TC más alto en {max_tc_row['hub']} "
                            f"({int(max_tc_row['value'])}), "
                            f"más bajo en {min_tc_row['hub']} "
                            f"({int(min_tc_row['value'])})"
                        )

            if "IN" in metrics_in_data:
                in_by_hub = hub_comp[hub_comp["metric"] == "IN"]
                if len(in_by_hub) > 1:
                    max_in_row = in_by_hub.loc[in_by_hub["value"].idxmax()]
                    min_in_row = in_by_hub.loc[in_by_hub["value"].idxmin()]
                    if max_in_row["value"] > min_in_row["value"]:
                        insights.append(
                            f"Mayor volumen de IN en {max_in_row['hub']} "
                            f"({int(max_in_row['value'])}), "
                            f"menor en {min_in_row['hub']} "
                            f"({int(min_in_row['value'])})"
                        )

        if not insights:
            insights.append("No hay datos suficientes para generar conclusiones automáticas.")

        return insights
