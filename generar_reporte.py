"""
Generador de reportes gráficos para HUBs ZAP y VIL.

Genera 4 imágenes PNG:
  1. Líneas ZAP — evolución diaria de IN, TC, RA
  2. Líneas VIL — evolución diaria de IN, TC, RA
  3. Barras ZAP — panel ppal IN+TC + minigráfico RA aparte
  4. Barras VIL — panel ppal IN+TC + minigráfico RA aparte

Uso: python generar_reporte.py
Requiere: pip install matplotlib psycopg2-binary
"""

import os
import psycopg2
from datetime import datetime
import matplotlib
matplotlib.use("Agg")  # Sin display
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np

# ─── Configuración DB ───────────────────────────────────────────────
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", "5432")),
    "dbname": os.getenv("DB_NAME", "abiertas"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASS", "changeme"),
}

# Clasificación desde metrics.py
TIPOS_IN = [
    "Cambio de Domicilio", "Cambio de Equipo",
    "Cambio de Servicios", "Cambio de Ubicacion", "Instalacion",
]
TIPOS_TC = [
    "Trouble Call Telefonia", "Trouble Call Cablemodem",
    "Trouble Call Video", "Trouble Call House Check", "Trouble Call",
]
TIPO_RA = "Recoleccion Acometida"

# ─── Paleta Monarch (ámbar/cian) ────────────────────────────────────
COLORS = {
    "IN": "#f59e0b",   # amber-500
    "TC": "#06b6d4",   # cyan-500
    "RA": "#10b981",   # emerald-500
    "bg": "#0f172a",   # slate-900
    "surface": "#1e293b",
    "grid": "#334155",
    "text": "#e2e8f0",
    "accent": "#fbbf24",
}

# ─── Queries ────────────────────────────────────────────────────────

QUERY_LINEAS = """
    SELECT
        dia::date AS day,
        SUM(CASE WHEN tipo = ANY(%s) THEN 1 ELSE 0 END) AS in_count,
        SUM(CASE WHEN tipo = ANY(%s) THEN 1 ELSE 0 END) AS tc_count,
        SUM(CASE WHEN tipo = %s THEN 1 ELSE 0 END) AS ra_count
    FROM abiertas
    WHERE hub = %s AND hub IS NOT NULL AND hub != ''
    GROUP BY dia::date
    ORDER BY dia::date
"""

QUERY_BARRAS = """
    SELECT
        fechaorden::date AS fecha,
        SUM(CASE WHEN tipo = ANY(%s) THEN 1 ELSE 0 END) AS in_count,
        SUM(CASE WHEN tipo = ANY(%s) THEN 1 ELSE 0 END) AS tc_count,
        SUM(CASE WHEN tipo = %s THEN 1 ELSE 0 END) AS ra_count
    FROM abiertas
    WHERE hub = %s AND hub IS NOT NULL AND hub != ''
      AND fechaorden IS NOT NULL
    GROUP BY fechaorden::date
    ORDER BY fechaorden::date
"""


def fetch_data(hub: str):
    """Retorna (lineas, barras) para un HUB."""
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    cur.execute(QUERY_LINEAS, (TIPOS_IN, TIPOS_TC, TIPO_RA, hub))
    lineas = cur.fetchall()

    cur.execute(QUERY_BARRAS, (TIPOS_IN, TIPOS_TC, TIPO_RA, hub))
    barras = cur.fetchall()

    cur.close()
    conn.close()
    return lineas, barras


# ─── Estilo global ──────────────────────────────────────────────────

def set_style():
    """Aplica el tema oscuro Monarch."""
    plt.rcParams.update({
        "figure.facecolor": COLORS["bg"],
        "axes.facecolor": COLORS["surface"],
        "axes.edgecolor": COLORS["grid"],
        "axes.labelcolor": COLORS["text"],
        "axes.titlecolor": COLORS["text"],
        "xtick.color": COLORS["text"],
        "ytick.color": COLORS["text"],
        "grid.color": COLORS["grid"],
        "grid.alpha": 0.3,
        "legend.facecolor": COLORS["surface"],
        "legend.edgecolor": COLORS["grid"],
        "legend.labelcolor": COLORS["text"],
        "text.color": COLORS["text"],
        "font.family": "sans-serif",
        "font.size": 10,
    })


# ─── Helpers ────────────────────────────────────────────────────────

def hide_y_axis(ax):
    """Elimina el eje Y y su línea de base."""
    ax.set_yticklabels([])
    ax.tick_params(left=False)
    ax.set_ylabel("")
    ax.spines["left"].set_visible(False)


# ─── Gráfico de Líneas ──────────────────────────────────────────────

def grafico_lineas(hub: str, data, output_path: str):
    """Evolución diaria de IN, TC, RA con etiquetas de valor."""
    if not data:
        print(f"  ⚠ No hay data de líneas para {hub}")
        return False

    fechas = [r[0] for r in data]
    in_vals = [r[1] for r in data]
    tc_vals = [r[2] for r in data]
    ra_vals = [r[3] for r in data]

    set_style()
    fig, ax = plt.subplots(figsize=(12, 6))

    lines = [
        (fechas, in_vals, COLORS["IN"], "IN", "o"),
        (fechas, tc_vals, COLORS["TC"], "TC", "s"),
        (fechas, ra_vals, COLORS["RA"], "RA", "^"),
    ]

    for xs, ys, color, label, marker in lines:
        ax.plot(xs, ys, color=color, marker=marker, linewidth=2, label=label)
        ax.fill_between(xs, ys, alpha=0.06, color=color)

        # Etiqueta de valor sobre cada punto
        for x, y in zip(xs, ys):
            if y > 0:
                ax.annotate(
                    str(y),
                    (x, y),
                    textcoords="offset points",
                    xytext=(0, 10),
                    ha="center",
                    fontsize=7,
                    color=color,
                    fontweight="bold",
                )

    hide_y_axis(ax)

    ax.set_title(f"HUB {hub} — OS Abiertas — Evolución Diaria", fontsize=14, fontweight="bold", pad=15)
    ax.set_xlabel("Día", fontsize=11)
    ax.legend(framealpha=0.9, loc="upper left")
    ax.grid(True, linestyle="--", alpha=0.3)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d/%m"))
    fig.autofmt_xdate()

    plt.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight", facecolor=COLORS["bg"])
    plt.close(fig)
    print(f"  ✅ {output_path}")
    return True


# ─── Gráfico de Barras ──────────────────────────────────────────────

def grafico_barras(hub: str, data, output_path: str):
    """Distribución de órdenes por fechaorden — panel ppal IN+TC, minigráfico RA."""
    if not data:
        print(f"  ⚠ No hay data de barras para {hub}")
        return False

    fechas = [r[0] for r in data]
    in_vals = [r[1] for r in data]
    tc_vals = [r[2] for r in data]
    ra_vals = [r[3] for r in data]

    set_style()
    fig, (ax_main, ax_ra) = plt.subplots(
        2, 1, figsize=(14, 8), sharex=True,
        gridspec_kw={"height_ratios": [2, 1]},
        constrained_layout=True,
    )

    x = np.arange(len(fechas))

    # ── Panel superior: IN + TC ──
    width = 0.3
    bars_in = ax_main.bar(
        x - width / 2, in_vals, width, color=COLORS["IN"], label="IN", edgecolor="none",
    )
    bars_tc = ax_main.bar(
        x + width / 2, tc_vals, width, color=COLORS["TC"], label="TC", edgecolor="none",
    )

    ax_main.bar_label(bars_in, fontsize=6, color=COLORS["text"], fontweight="bold", padding=2)
    ax_main.bar_label(bars_tc, fontsize=6, color=COLORS["text"], fontweight="bold", padding=2)
    hide_y_axis(ax_main)

    ax_main.set_title(
        f"HUB {hub} — OS Abiertas — Órdenes por Fecha",
        fontsize=14, fontweight="bold", pad=12,
    )
    ax_main.legend(framealpha=0.9, loc="upper left")
    ax_main.grid(True, axis="y", linestyle="--", alpha=0.3)

    # ── Panel inferior: solo RA ──
    bars_ra = ax_ra.bar(x, ra_vals, 0.5, color=COLORS["RA"], label="RA", edgecolor="none")
    ax_ra.bar_label(bars_ra, fontsize=7, color=COLORS["RA"], fontweight="bold", padding=2)
    hide_y_axis(ax_ra)

    ax_ra.set_ylabel("RA", fontsize=10, fontweight="bold", color=COLORS["RA"], labelpad=8)
    ax_ra.legend(framealpha=0.9, loc="upper left", fontsize=8)
    ax_ra.grid(True, axis="y", linestyle="--", alpha=0.3)

    # ── Eje X compartido ──
    ax_ra.set_xlabel("Fecha de Orden", fontsize=11)
    ax_ra.set_xticks(x)
    ax_ra.set_xticklabels(
        [d.strftime("%d/%m") for d in fechas],
        rotation=45, ha="right", fontsize=8,
    )

    fig.savefig(output_path, dpi=150, bbox_inches="tight", facecolor=COLORS["bg"])
    plt.close(fig)
    print(f"  ✅ {output_path}")
    return True


# ─── Main ────────────────────────────────────────────────────────────

def main():
    os.makedirs("reportes", exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    hubs = ["ZAP", "VIL"]

    for hub in hubs:
        print(f"\n📊 Procesando HUB {hub}...")
        lineas, barras = fetch_data(hub)

        grafico_lineas(hub, lineas, f"reportes/{hub}_lineas_{timestamp}.png")
        grafico_barras(hub, barras, f"reportes/{hub}_barras_{timestamp}.png")

    print(f"\n✅ Reporte completado — {4} imágenes en reportes/")


if __name__ == "__main__":
    main()
