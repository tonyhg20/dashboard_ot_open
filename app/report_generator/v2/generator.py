"""
Executive Report v2 — ReportV2Generator.

Pipeline: 4 SQL queries on ``abiertas`` → compute KPIs → compute chart data
→ Jinja2 template render (Monarch dark theme, zero JS).

Usage::

    gen = ReportV2Generator()
    html = gen.generate_report()

Data structures (exported for type hints)::

    KpiCard        — one metric card with value, DoD %, trend, sparkline
    ChartSeries    — named series of values with color
    ChartData      — container for all 4 chart datasets
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field, asdict
from datetime import timedelta
from pathlib import Path

import pandas as pd
from jinja2 import Environment, FileSystemLoader

from app.db import get_db_connection, get_db_completas_connection

log = logging.getLogger(__name__)

# ── Public Data Structures ───────────────────────────────────────────────────


@dataclass
class KpiCard:
    """One KPI card with current value, day-over-day change, and 7-day sparkline."""

    id: str  # "total" | "in" | "tc" | "ra"
    name: str  # "Total IN+TC" | "Instalaciones" | "Trouble Calls" | "Recolección"
    value: int
    change_pct: str  # "+5.2%" | "-2.1%" | "--"
    trend: str  # "up" | "down" | "flat"
    sparkline_data: list[int]  # 7 values
    color: str  # hex accent
    bg: str  # hex card background


@dataclass
class ChartSeries:
    """Single series inside a chart — name, values, color, optional marker shape."""

    name: str
    values: list[int]
    color: str
    marker: str = ""  # "square" | "triangle" (only for line chart)


@dataclass
class ChartData:
    """Container for all 4 chart datasets consumed by ``report.html``."""

    lineas: dict = field(default_factory=lambda: {"labels": [], "series": []})
    barras_ra: dict = field(default_factory=lambda: {"labels": [], "values": [], "color": ""})
    fechaorden: dict = field(default_factory=lambda: {"categories": [], "series": []})
    hub: dict = field(default_factory=lambda: {"hubs": [], "categories": [], "values": {}, "colors": {}})


# ── KPI Category Config ──────────────────────────────────────────────────────

KPI_CATEGORIES: dict[str, dict] = {
    "total": {"name": "Total IN+TC", "tipos": ["IN", "TC"], "color": "#22d3ee", "bg": "#1a2122"},
    "in": {"name": "Instalaciones", "tipos": ["IN"], "color": "#fb923c", "bg": "#1a2122"},
    "tc": {"name": "Trouble Calls", "tipos": ["TC"], "color": "#f87171", "bg": "#1a2122"},
    "ra": {"name": "Recolección", "tipos": ["RA"], "color": "#c084fc", "bg": "#1a2122"},
}

# ── Tipo Mapping ──────────────────────────────────────────────────────────────
# Raw ``tipo`` values in ``abiertas`` → short metric codes.
_TIPO_MAP_SQL = """
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
    END
"""

_HUB_COLORS: dict[str, str] = {
    "IN": "#fb923c",
    "TC": "#f87171",
    "RA": "#c084fc",
}

# Hubs cubiertos por el reporte (demostración — datos ficticios). El
# resto de la tabla abiertas queda fuera del alcance del reporte.
DEFAULT_HUBS = ["ZAP", "VIL", "TUX", "SOT", "GRA"]

# SQL literal reutilizable para filtrar por los hubs del reporte.
_HUBS_SQL = "('" + "', '".join(DEFAULT_HUBS) + "')"


# ── ReportV2Generator ────────────────────────────────────────────────────────


class ReportV2Generator:
    """Pipeline: SQL → compute KPIs → compute chart data → Jinja2 → HTML string.

    Parameters
    ----------
    db_conn : psycopg2 connection, optional
        Reusable database connection.  If omitted, a new connection is created
        via ``app.db.get_db_connection()``.
    """

    def __init__(self, db_conn=None):
        self.conn = db_conn or get_db_connection()
        self.template_env = Environment(
            loader=FileSystemLoader(Path(__file__).parent / "templates"),
            autoescape=False,
        )

    # ── Public API ─────────────────────────────────────────────────────────

    def generate_report(
        self,
        hub_ids: list[str] | None = None,
        period: str = "last_7_days",
    ) -> str:
        """Run the full report pipeline and return the rendered HTML string.

        Steps
        -----
        1. Execute 4 SQL queries on ``abiertas``.
        2. Compute 4 KPI values with DoD % and 7-day sparklines.
        3. Compute 4 chart datasets (lineas, barras RA, fechaorden, hub).
        4. Render ``report.html`` with the computed data.

        Parameters
        ----------
        hub_ids : list[str] | None
            Optional hub filter.  When ``None``, data for all hubs is returned.
        period : str
            Reporting period label (e.g. ``"last_7_days"``).

        Returns
        -------
        str
            Full HTML document ready for Playwright screenshot.
        """
        self._hub_ids = hub_ids
        self._period = period
        df_7d = self._query_abiertas_7d()
        df_12d = self._query_abiertas_12d()
        df_hub_latest = self._query_per_hub_latest()
        df_fechaorden = self._query_by_fechaorden()
        df_backlog_evol = self._query_backlog_evolution()
        df_backlog_aging = self._query_backlog_aging()
        df_inst_completadas = self._query_instalaciones_completadas()
        df_avg_days = self._query_avg_days()
        df_asignadas = self._query_asignadas()

        kpis = self.compute_kpis(df_7d)
        chart_data = self.compute_chart_data(df_7d, df_12d, df_hub_latest, df_fechaorden)
        extra_data = self.compute_extra_data(df_backlog_evol, df_backlog_aging, df_inst_completadas)
        avg_days = self.compute_avg_days(df_avg_days)
        asignadas = self.compute_asignadas(df_asignadas)

        max_day = df_7d["dia"].max() if not df_7d.empty else None
        report_date = max_day.strftime("%Y-%m-%d") if max_day is not None else "—"

        template = self.template_env.get_template("report.html")
        html = template.render(
            kpis=[asdict(k) for k in kpis],
            chart_lineas=chart_data["lineas"],
            chart_barras_ra=chart_data["barras_ra"],
            chart_fechaorden=chart_data["fechaorden"],
            chart_hub=chart_data["hub"],
            chart_backlog_evol=extra_data["backlog_evol"],
            chart_backlog_aging=extra_data["backlog_aging"],
            avg_days=avg_days,
            asignadas=asignadas,
            report_date=report_date,
            period="Últimos 7 días",
        )
        return html

    # ── SQL Queries ────────────────────────────────────────────────────────

    def _query_abiertas_7d(self) -> pd.DataFrame:
        """Returns 7 days of IN/TC/RA counts per day (all hubs).

        Returns
        -------
        pd.DataFrame
            Columns: ``dia``, ``hub``, ``tipo``, ``count``.
        """
        query = f"""
            SELECT dia::date AS dia, hub, {_TIPO_MAP_SQL} AS metric, COUNT(*) AS count
            FROM abiertas
            WHERE hub IN {_HUBS_SQL}
              AND dia >= (SELECT MAX(dia::date) FROM abiertas WHERE hub IN {_HUBS_SQL}) - INTERVAL '6 days'
              AND tipo IS NOT NULL AND tipo != ''
            GROUP BY dia::date, hub, metric
            ORDER BY dia::date
        """
        return pd.read_sql(query, self.conn)

    def _query_abiertas_12d(self) -> pd.DataFrame:
        """Returns RA counts per day for the last 12 days.

        Returns
        -------
        pd.DataFrame
            Columns: ``dia``, ``count``.
        """
        query = f"""
            SELECT dia::date AS dia, COUNT(*) AS count
            FROM abiertas
            WHERE {_TIPO_MAP_SQL} = 'RA'
              AND hub IN {_HUBS_SQL}
              AND dia >= (SELECT MAX(dia::date) FROM abiertas WHERE hub IN {_HUBS_SQL}) - INTERVAL '11 days'
              AND tipo IS NOT NULL AND tipo != ''
            GROUP BY dia::date
            ORDER BY dia::date
        """
        return pd.read_sql(query, self.conn)

    def _query_per_hub_latest(self) -> pd.DataFrame:
        """Returns IN, TC, RA per hub for the most recent day.

        Returns
        -------
        pd.DataFrame
            Columns: ``hub``, ``tipo``, ``count``.
        """
        query = f"""
            SELECT hub, {_TIPO_MAP_SQL} AS metric, COUNT(*) AS count
            FROM abiertas
            WHERE hub IN {_HUBS_SQL}
              AND dia::date = (SELECT MAX(dia::date) FROM abiertas WHERE hub IN {_HUBS_SQL})
              AND tipo IS NOT NULL AND tipo != ''
            GROUP BY hub, metric
            ORDER BY hub, metric
        """
        return pd.read_sql(query, self.conn)

    def _query_by_fechaorden(self) -> pd.DataFrame:
        """Returns IN and TC counts grouped by ``fechaorden``.

        Returns
        -------
        pd.DataFrame
            Columns: ``fechaorden``, ``tipo``, ``count``.
        """
        query = f"""
            SELECT fechaorden::date AS fechaorden, {_TIPO_MAP_SQL} AS metric, COUNT(*) AS count
            FROM abiertas
            WHERE {_TIPO_MAP_SQL} IN ('IN', 'TC')
              AND hub IN {_HUBS_SQL}
              AND fechaorden IS NOT NULL
              AND dia::date = (SELECT MAX(dia::date) FROM abiertas WHERE hub IN {_HUBS_SQL})
              AND tipo IS NOT NULL AND tipo != ''
            GROUP BY fechaorden::date, metric
            ORDER BY fechaorden::date
        """
        return pd.read_sql(query, self.conn)

    # ── Nuevas queries: Evolución del backlog ────────────────────────────────

    def _query_backlog_evolution(self) -> pd.DataFrame:
        """Returns IN y TC abiertas por día para los últimos 23 días (excluye RA).

        Returns
        -------
        pd.DataFrame
            Columns: ``dia``, ``metric``, ``count``.
        """
        query = f"""
            SELECT dia::date AS dia, {_TIPO_MAP_SQL} AS metric, COUNT(*) AS count
            FROM abiertas
            WHERE hub IN {_HUBS_SQL}
              AND {_TIPO_MAP_SQL} IN ('IN', 'TC')
              AND dia >= (SELECT MAX(dia::date) FROM abiertas WHERE hub IN {_HUBS_SQL}) - INTERVAL '22 days'
              AND tipo IS NOT NULL AND tipo != ''
            GROUP BY dia::date, metric
            ORDER BY dia::date, metric
        """
        return pd.read_sql(query, self.conn)

    def _query_backlog_aging(self) -> pd.DataFrame:
        """Returns distribución de antigüedad del backlog por tipo (IN, TC, RA).

        Toma el último día disponible y calcula cuántos días lleva cada
        orden abierta desde ``fechaorden``.

        Returns
        -------
        pd.DataFrame
            Columns: ``rango``, ``tipo``, ``count``.
        """
        query = f"""
            WITH ultimo_dia AS (
                SELECT MAX(dia::date) AS max_dia FROM abiertas WHERE hub IN {_HUBS_SQL}
            ),
            ordenes_hoy AS (
                SELECT fechaorden::date AS fecha, tipo
                FROM abiertas, ultimo_dia
                WHERE hub IN {_HUBS_SQL}
                  AND dia::date = ultimo_dia.max_dia
                  AND tipo IS NOT NULL AND tipo != ''
            )
            SELECT
                CASE
                    WHEN (SELECT max_dia FROM ultimo_dia) - fecha <= 1 THEN '0-1 dias'
                    WHEN (SELECT max_dia FROM ultimo_dia) - fecha <= 3 THEN '2-3 dias'
                    WHEN (SELECT max_dia FROM ultimo_dia) - fecha <= 7 THEN '4-7 dias'
                    WHEN (SELECT max_dia FROM ultimo_dia) - fecha <= 15 THEN '8-15 dias'
                    WHEN (SELECT max_dia FROM ultimo_dia) - fecha <= 30 THEN '16-30 dias'
                    ELSE '+30 dias'
                END AS rango,
                CASE
                    WHEN tipo IN ('Cambio de Domicilio','Cambio de Equipo',
                                  'Cambio de Servicios','Cambio de Ubicacion',
                                  'Instalacion') THEN 'IN'
                    WHEN tipo IN ('Trouble Call Telefonia','Trouble Call Cablemodem',
                                  'Trouble Call Video','Trouble Call House Check',
                                  'Trouble Call') THEN 'TC'
                    WHEN tipo = 'Recoleccion Acometida' THEN 'RA'
                    ELSE 'Otro'
                END AS metric,
                COUNT(*) AS count
            FROM ordenes_hoy
            GROUP BY rango, metric
            ORDER BY rango, metric
        """
        return pd.read_sql(query, self.conn)

    def _query_instalaciones_completadas(self) -> pd.DataFrame:
        """Returns instalaciones completadas desde la tabla ``completas``.

        La tabla ``completas`` (DB completas) contiene las órdenes ya
        completadas por fecha solicitada para los hubs del reporte.

        Returns
        -------
        pd.DataFrame
            Columns: ``fecha``, ``count``.
        """
        try:
            conn_completas = get_db_completas_connection()
            query = f"""
                SELECT fechasolicitada::date AS fecha, COUNT(*) AS count
                FROM completas
                WHERE tipo = 'Instalacion'
                  AND hub IN {_HUBS_SQL}
                  AND fechasolicitada IS NOT NULL
                  AND fechasolicitada >= CURRENT_DATE - INTERVAL '30 days'
                GROUP BY fechasolicitada::date
                ORDER BY fechasolicitada::date
            """
            df = pd.read_sql(query, conn_completas)
            conn_completas.close()
            return df
        except Exception as exc:
            log.warning("No se pudo consultar DB completas: %s", exc)
            return pd.DataFrame(columns=["fecha", "count"])

    def _query_asignadas(self) -> pd.DataFrame:
        """Returns total and assigned counts for IN and TC on the latest day.

        Assigned = ``tecnico`` IS NOT NULL AND ``tecnico`` != 'SADMIN'.

        Returns
        -------
        pd.DataFrame
            Columns: ``metric``, ``total``, ``asignadas``.
        """
        query = f"""
            WITH ultimo_dia AS (
                SELECT MAX(dia::date) AS max_dia FROM abiertas WHERE hub IN {_HUBS_SQL}
            ),
            totales AS (
                SELECT {_TIPO_MAP_SQL} AS metric, COUNT(*) AS total
                FROM abiertas, ultimo_dia
                WHERE hub IN {_HUBS_SQL}
                  AND dia::date = ultimo_dia.max_dia
                  AND tipo IS NOT NULL AND tipo != ''
                GROUP BY metric
            ),
            campo AS (
                SELECT {_TIPO_MAP_SQL} AS metric, COUNT(*) AS asignadas
                FROM abiertas, ultimo_dia
                WHERE hub IN {_HUBS_SQL}
                  AND dia::date = ultimo_dia.max_dia
                  AND fechasolicitada::date = CURRENT_DATE
                  AND tecnico IS NOT NULL AND tecnico != 'SADMIN'
                  AND tipo IS NOT NULL AND tipo != ''
                GROUP BY metric
            )
            SELECT
                t.metric,
                t.total,
                COALESCE(c.asignadas, 0) AS asignadas
            FROM totales t
            LEFT JOIN campo c ON t.metric = c.metric
            WHERE t.metric IN ('IN', 'TC')
            ORDER BY t.metric
        """
        return pd.read_sql(query, self.conn)

    def _query_avg_days(self) -> pd.DataFrame:
        """Returns average days (dia - fechaorden) for IN and TC for recent days.

        Returns data for up to 3 recent days so we can compute DoD trends.

        Returns
        -------
        pd.DataFrame
            Columns: ``metric``, ``dia``, ``avg_days``.
        """
        query = f"""
            WITH daily_data AS (
                SELECT {_TIPO_MAP_SQL} AS metric,
                       dia::date AS dia,
                       dia::date - fechaorden::date AS days_diff
                FROM abiertas
                WHERE hub IN {_HUBS_SQL}
                  AND dia::date >= (SELECT MAX(dia::date) FROM abiertas WHERE hub IN {_HUBS_SQL}) - INTERVAL '2 days'
                  AND fechaorden IS NOT NULL
                  AND tipo IS NOT NULL AND tipo != ''
            )
            SELECT metric, dia, ROUND(AVG(days_diff)::numeric, 1) AS avg_days
            FROM daily_data
            WHERE metric IN ('IN', 'TC')
            GROUP BY metric, dia
            ORDER BY metric, dia DESC
        """
        return pd.read_sql(query, self.conn)

    # ── KPI Computation ────────────────────────────────────────────────────

    def compute_kpis(self, df_7d: pd.DataFrame) -> list[KpiCard]:
        """Compute 4 KPI cards from 7-day abiertas data.

        Parameters
        ----------
        df_7d : pd.DataFrame
            DataFrame returned by ``_query_abiertas_7d()``.

        Returns
        -------
        list[KpiCard]
            Four KPI cards: total (IN+TC), IN, TC, RA.
        """
        if df_7d.empty:
            return [
                KpiCard(id=k, name=v["name"], value=0, change_pct="--",
                        trend="flat", sparkline_data=[], color=v["color"], bg=v["bg"])
                for k, v in KPI_CATEGORIES.items()
            ]

        max_day = df_7d["dia"].max()
        # Find the previous day that actually has data
        unique_days = sorted(df_7d["dia"].unique(), reverse=True)
        prev_day = unique_days[1] if len(unique_days) > 1 else None
        today = df_7d[df_7d["dia"] == max_day]
        yesterday = df_7d[df_7d["dia"] == prev_day] if prev_day is not None else pd.DataFrame(columns=df_7d.columns)

        kpis: list[KpiCard] = []
        for kid, kcfg in KPI_CATEGORIES.items():
            today_val = today[today["metric"].isin(kcfg["tipos"])]["count"].sum()
            yesterday_val = yesterday[yesterday["metric"].isin(kcfg["tipos"])]["count"].sum()

            # Compute DoD %
            if yesterday_val > 0:
                pct = ((today_val - yesterday_val) / yesterday_val) * 100
                change_pct = f"+{pct:.1f}%" if pct > 0 else f"{pct:.1f}%"
                trend = "up" if pct > 0 else "down"
            else:
                change_pct = "--" if today_val == 0 else "+100%"
                trend = "up" if today_val > 0 else "flat"

            # 7-day sparkline (últimos 7 días con datos)
            sparkline: list[int] = []
            recent_days = sorted(df_7d["dia"].unique(), reverse=True)[:7]
            recent_days.reverse()  # chronological
            for day in recent_days:
                day_data = df_7d[df_7d["dia"] == day]
                val = day_data[day_data["metric"].isin(kcfg["tipos"])]["count"].sum()
                sparkline.append(int(val))

            kpis.append(KpiCard(
                id=kid,
                name=kcfg["name"],
                value=int(today_val),
                change_pct=change_pct,
                trend=trend,
                sparkline_data=sparkline,
                color=kcfg["color"],
                bg=kcfg["bg"],
            ))

        return kpis

    def compute_asignadas(self, df: pd.DataFrame) -> dict:
        """Compute assigned counts and percentages for IN and TC.

        Expects a DataFrame with columns ``metric``, ``total``, ``asignadas``
        (from ``_query_asignadas``). Returns a dict with:

        - ``in_asignadas``, ``tc_asignadas`` — assigned count
        - ``in_total``, ``tc_total`` — total count
        - ``in_pct``, ``tc_pct`` — assigned % (float or None if total is 0)
        """
        result: dict[str, int | float | None] = {
            "in_asignadas": 0, "in_total": 0, "in_pct": None,
            "tc_asignadas": 0, "tc_total": 0, "tc_pct": None,
        }
        if df.empty:
            return result

        for metric_key in ("IN", "TC"):
            result_key = "in" if metric_key == "IN" else "tc"
            row = df[df["metric"] == metric_key]
            if row.empty:
                continue

            total = int(row.iloc[0]["total"])
            asignadas = int(row.iloc[0]["asignadas"])
            result[f"{result_key}_total"] = total
            result[f"{result_key}_asignadas"] = asignadas
            if total > 0:
                result[f"{result_key}_pct"] = round((asignadas / total) * 100, 1)

        return result

    def compute_avg_days(self, df_avg: pd.DataFrame) -> dict:
        """Compute average days for IN and TC with day-over-day trend.

        Expects a DataFrame with columns ``metric``, ``dia``, ``avg_days``
        (at least today's data). Returns a dict with:

        - ``in_avg``, ``tc_avg`` — latest day average (float or None)
        - ``in_trend``, ``tc_trend`` — ``"up"``, ``"down"``, or ``"flat"``
        - ``in_change``, ``tc_change`` — absolute change vs previous day (float or None)
        """
        result: dict[str, float | None | str] = {
            "in_avg": None, "tc_avg": None,
            "in_trend": "flat", "tc_trend": "flat",
            "in_change": None, "tc_change": None,
        }
        if df_avg.empty:
            return result

        for metric_key in ("IN", "TC"):
            result_key = "in" if metric_key == "IN" else "tc"
            metric_df = df_avg[df_avg["metric"] == metric_key].sort_values("dia", ascending=False)
            if metric_df.empty:
                continue

            # Today's value
            today = float(metric_df.iloc[0]["avg_days"])
            result[f"{result_key}_avg"] = today

            # Compare with previous day (if available)
            if len(metric_df) > 1:
                yesterday = float(metric_df.iloc[1]["avg_days"])
                change = round(today - yesterday, 1)
                result[f"{result_key}_change"] = change
                if change > 0:
                    result[f"{result_key}_trend"] = "up"
                elif change < 0:
                    result[f"{result_key}_trend"] = "down"
                else:
                    result[f"{result_key}_trend"] = "flat"

        return result

    # ── Chart Data Computation ─────────────────────────────────────────────

    def compute_chart_data(
        self,
        df_7d: pd.DataFrame,
        df_12d: pd.DataFrame,
        df_hub_latest: pd.DataFrame,
        df_fechaorden: pd.DataFrame,
    ) -> dict:
        """Build all 4 chart datasets from the query results.

        Parameters
        ----------
        df_7d : pd.DataFrame
            7-day abiertas data (``_query_abiertas_7d``).
        df_12d : pd.DataFrame
            12-day RA data (``_query_abiertas_12d``).
        df_hub_latest : pd.DataFrame
            Per-hub latest-day data (``_query_per_hub_latest``).
        df_fechaorden : pd.DataFrame
            Fechaorden-grouped data (``_query_by_fechaorden``).

        Returns
        -------
        dict
            Keys match the 4 chart sections: ``lineas``, ``barras_ra``,
            ``fechaorden``, ``hub``.
        """
        chart_data = ChartData()

        # ── 1. Lineas IN+TC (7-day line chart — solo días con datos) ──────
        if not df_7d.empty:
            unique_days = sorted(df_7d["dia"].unique(), reverse=True)
            # Take at most 7 most recent days with actual data
            recent_days = unique_days[:7]
            recent_days.reverse()  # chronological left→right
            labels: list[str] = []
            in_vals: list[int] = []
            tc_vals: list[int] = []

            for day in recent_days:
                labels.append(day.strftime("%Y-%m-%d"))
                day_df = df_7d[df_7d["dia"] == day]
                in_vals.append(int(day_df[day_df["metric"] == "IN"]["count"].sum()))
                tc_vals.append(int(day_df[day_df["metric"] == "TC"]["count"].sum()))

            chart_data.lineas = {
                "labels": labels,
                "series": [
                    {"name": "IN", "values": in_vals, "color": "#fb923c", "marker": "square"},
                    {"name": "TC", "values": tc_vals, "color": "#f87171", "marker": "triangle"},
                ],
            }

        # ── 2. Barras RA (3 barras: d0, d-4, d-8 reales) ───────────────────
        ra_labels: list[str] = []
        ra_values: list[int] = []
        if not df_12d.empty:
            ra_sorted = df_12d.sort_values("dia")
            max_ra_day = ra_sorted["dia"].max()
            targets = [max_ra_day, max_ra_day - timedelta(days=4), max_ra_day - timedelta(days=8)]
            unique_ra_days = ra_sorted["dia"].unique()
            for target in targets:
                # Find closest available day
                closest_day = min(unique_ra_days, key=lambda d: abs((d - target).days))
                row = ra_sorted[ra_sorted["dia"] == closest_day].iloc[0]
                ra_labels.append(row["dia"].strftime("%Y-%m-%d"))
                ra_values.append(int(row["count"]))

        chart_data.barras_ra = {
            "labels": ra_labels,
            "values": ra_values,
            "color": "#c084fc",
        }

        # ── 3. Barras IN+TC por fechaorden (grouped bars) ──────────────────
        if not df_fechaorden.empty:
            fo_categories = sorted(df_fechaorden["fechaorden"].unique())
            fo_in: list[int] = []
            fo_tc: list[int] = []

            for cat in fo_categories:
                cat_df = df_fechaorden[df_fechaorden["fechaorden"] == cat]
                fo_in.append(int(cat_df[cat_df["metric"] == "IN"]["count"].sum()))
                fo_tc.append(int(cat_df[cat_df["metric"] == "TC"]["count"].sum()))

            chart_data.fechaorden = {
                "categories": [str(c) for c in fo_categories],
                "series": [
                    {"name": "IN", "values": fo_in, "color": "#fb923c"},
                    {"name": "TC", "values": fo_tc, "color": "#f87171"},
                ],
            }

        # ── 4. Barras por Hub (ZAP / VIL horizontal bars) ──────────────────
        if not df_hub_latest.empty:
            hubs = sorted(df_hub_latest["hub"].unique())
            hub_categories = ["IN", "TC", "RA"]
            hub_values: dict[str, dict[str, int]] = {}

            for hub in hubs:
                hub_df = df_hub_latest[df_hub_latest["hub"] == hub]
                hub_values[hub] = {}
                for cat in hub_categories:
                    val = hub_df[hub_df["metric"] == cat]["count"].sum()
                    hub_values[hub][cat] = int(val)

            chart_data.hub = {
                "hubs": hubs,
                "categories": hub_categories,
                "values": hub_values,
                "colors": dict(_HUB_COLORS),
            }

        return asdict(chart_data)

    # ── Nuevos cálculos: backlog evolution, aging, alerta ────────────────────

    def compute_extra_data(
        self,
        df_backlog_evol: pd.DataFrame,
        df_backlog_aging: pd.DataFrame,
        df_inst_completadas: pd.DataFrame,
    ) -> dict:
        """Compute extra chart data for backlog evolution, aging, and alert.

        Returns
        -------
        dict
            Keys: ``backlog_evol``, ``backlog_aging``, ``alerta_instalaciones``.
        """
        result: dict = {}

        # ── 1. Backlog Evolution (line chart, 2 series: IN y TC) ────
        if not df_backlog_evol.empty:
            df_evol = df_backlog_evol.copy()
            days = sorted(df_evol["dia"].unique())
            labels = [d.strftime("%Y-%m-%d") for d in days]

            in_vals = []
            tc_vals = []
            for d in days:
                day_df = df_evol[df_evol["dia"] == d]
                in_vals.append(int(day_df[day_df["metric"] == "IN"]["count"].sum()))
                tc_vals.append(int(day_df[day_df["metric"] == "TC"]["count"].sum()))

            result["backlog_evol"] = {
                "labels": labels,
                "series": [
                    {"name": "IN", "values": in_vals, "color": "#fb923c", "marker": "square"},
                    {"name": "TC", "values": tc_vals, "color": "#f87171", "marker": "triangle"},
                ],
            }
        else:
            result["backlog_evol"] = {"labels": [], "series": []}

        # ── 2. Backlog Aging (stacked 100%: rangos × tipo) ─────────────
        RANGO_ORDER = ["0-1 dias", "2-3 dias", "4-7 dias", "8-15 dias", "16-30 dias", "+30 dias"]
        TIPOS = ["IN", "TC", "RA"]
        TIPO_COLORS = {"IN": "#fb923c", "TC": "#f87171", "RA": "#c084fc"}

        if not df_backlog_aging.empty:
            # Pivot: rangos como categorías, tipos como series
            aging_pivot = df_backlog_aging.pivot_table(
                index="rango", columns="metric", values="count", aggfunc="sum", fill_value=0
            )
            # Filtrar solo tipos que nos interesan
            categories = [r for r in RANGO_ORDER if r in aging_pivot.index]
            series_list = []
            totals_list = []
            for r in categories:
                total_r = 0
                for t in TIPOS:
                    if t in aging_pivot.columns:
                        total_r += int(aging_pivot.loc[r, t])
                totals_list.append(total_r)
            for t in TIPOS:
                if t in aging_pivot.columns:
                    vals = [int(aging_pivot.loc[r, t]) for r in categories]
                    series_list.append({
                        "name": t,
                        "values": vals,
                        "color": TIPO_COLORS[t],
                    })
            result["backlog_aging"] = {
                "categories": categories,
                "series": series_list,
                "totals": totals_list,
            }
        else:
            result["backlog_aging"] = {"categories": [], "series": [], "totals": []}

        return result

