"""
Trend line chart — one line per metric (IN, TC, Rx, RA, Dx) over time.

Input expects a **long-form** DataFrame::

    date        metric  value
    2026-06-01  IN      142
    2026-06-01  TC       38
    2026-06-01  RA       12
    2026-06-08  IN      156
    …

Each metric gets its own coloured line with point markers, a **light area fill**
below, and value labels at every data point (Latinometrics style).
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from .styles import (
    CATEGORY_COLORS,
    CATEGORY_LABELS,
    _chart_to_base64,
    add_data_labels,
    chart_context,
)


def create_trend_chart(
    df: pd.DataFrame,
    *,
    figsize: tuple[float, float] | None = None,
    style: dict[str, Any] | None = None,
    area_alpha: float = 0.05,
) -> dict:
    """Generate a multi-metric trend line chart.

    Parameters
    ----------
    df : pd.DataFrame
        Long-form data with columns ``["date", "metric", "value"]``.
        ``date`` is cast to datetime; ``metric`` values should match keys in
        ``CATEGORY_COLORS`` (``IN``, ``TC``, ``Rx``, ``RA``, ``Dx``).
    figsize : tuple[float, float] | None
        Figure size in inches.  Default ``(5.0, 2.33)`` → 750 × 350 px at
        150 dpi.
    style : dict | None
        Optional ``rcParams`` overrides on top of the editorial style.
    area_alpha : float
        Opacity of the area fill beneath each line.

    Returns
    -------
    dict
        ``{"base64": …, "format": "png", "width": …, "height": …}``
    """
    if figsize is None:
        figsize = (5.0, 2.33)

    # ── Validate & prepare data ───────────────────────────────────────────
    required = {"date", "metric", "value"}
    if not required.issubset(df.columns):
        msg = f"trend_chart requires columns {required}, got {list(df.columns)}"
        raise ValueError(msg)

    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values(["metric", "date"])

    metrics_in_data: list[str] = sorted(df["metric"].unique())

    with chart_context(overrides=style):
        import matplotlib.dates as mdates  # noqa: PLC0415
        import matplotlib.pyplot as plt  # noqa: PLC0415

        fig, ax = plt.subplots(figsize=figsize)

        for metric in metrics_in_data:
            subset = df[df["metric"] == metric]
            x = np.asarray(subset["date"].values, dtype="datetime64[us]")
            y = subset["value"].values.astype(float)
            color = CATEGORY_COLORS.get(metric, "#333333")
            label = CATEGORY_LABELS.get(metric, metric)

            # ── Line ──────────────────────────────────────────────────────
            ax.plot(
                x, y,
                color=color,
                linewidth=1.5,
                marker="o",
                markersize=4,
                label=label,
                solid_capstyle="round",
            )

            # ── Area fill ─────────────────────────────────────────────────
            if len(x) > 1:
                ax.fill_between(
                    x.astype("datetime64[D]").astype(object),
                    y,
                    alpha=area_alpha,
                    color=color,
                    linewidth=0,
                )

            # ── Data labels at each point ────────────────────────────────
            for xi, yi in zip(x, y):
                ax.annotate(
                    f"{int(yi)}",
                    xy=(xi, yi),
                    xytext=(0, 8),
                    textcoords="offset points",
                    color=color,
                    fontsize=6,
                    fontweight="bold",
                    ha="center",
                    va="bottom",
                )

        # ── Axes polish ───────────────────────────────────────────────────
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
        ax.yaxis.set_major_locator(plt.MaxNLocator(integer=True))
        ax.yaxis.get_offset_text().set_visible(False)

        # Light horizontal grid lines (editorial style)
        ax.grid(axis="y", alpha=0.35, linewidth=0.4)

        # Legend — minimal, at top-right inside the chart
        if len(metrics_in_data) > 1:
            ax.legend(
                loc="upper right",
                frameon=False,
                fontsize=7,
                handlelength=1.0,
                handletextpad=0.5,
            )

        fig.autofmt_xdate()

        return _chart_to_base64(fig)
