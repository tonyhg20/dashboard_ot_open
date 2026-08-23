"""
Comparison bar chart — hub vs hub, period vs period, category vs category.

Input expects a DataFrame::

    category    value   color       label
    ZAP         312     #0D9488     ZAP
    VIL         245     #F97316     VIL

The chart auto-selects horizontal bars when there are >= 6 categories,
vertical columns otherwise.  Value labels are drawn at the end of each bar.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from .styles import CATEGORY_COLORS, _chart_to_base64, chart_context


def create_bar_chart(
    df: pd.DataFrame,
    *,
    figsize: tuple[float, float] | None = None,
    style: dict[str, Any] | None = None,
    horizontal: bool | None = None,
) -> dict:
    """Generate a clean comparison bar / column chart.

    Parameters
    ----------
    df : pd.DataFrame
        Must include columns ``category`` (str) and ``value`` (numeric).
        Optional columns:
            ``color`` — per-bar colour (str hex, e.g. ``#2E5984``).
            ``label`` — displayed label (defaults to ``category``).
    figsize : tuple[float, float] | None
        Inches.  Default ``(4.0, 2.0)`` → 600 × 300 px at 150 dpi.
    style : dict | None
        Optional ``rcParams`` overrides.
    horizontal : bool | None
        Force horizontal bars (``True``) or vertical columns (``False``).
        Auto-detected when ``None``: horizontal if >= 6 rows.

    Returns
    -------
    dict
        ``{"base64": …, "format": "png", "width": …, "height": …}``
    """
    if figsize is None:
        figsize = (4.0, 2.0)

    required = {"category", "value"}
    if not required.issubset(df.columns):
        msg = f"bar_chart requires columns {required}, got {list(df.columns)}"
        raise ValueError(msg)

    df = df.copy()
    n = len(df)

    if horizontal is None:
        horizontal = n >= 6

    with chart_context(overrides=style):
        import matplotlib.pyplot as plt  # noqa: PLC0415

        fig, ax = plt.subplots(figsize=figsize)

        categories = df["category"].tolist()
        values = df["value"].values.astype(float)
        colors = df.get("color", default=None)
        labels = df.get("label", default=categories)

        if horizontal:
            # ── Horizontal bars ───────────────────────────────────────────
            y_pos = np.arange(n)
            bar_height = max(0.3, min(0.55, 1.8 / n))

            default_color = CATEGORY_COLORS.get("IN", "#0D9488")
            bars = ax.barh(
                y_pos,
                values,
                height=bar_height,
                color=colors if colors is not None else default_color,
                edgecolor="none",
                linewidth=0,
                zorder=3,
            )

            ax.set_yticks(y_pos)
            ax.set_yticklabels(labels, fontsize=8)
            ax.invert_yaxis()  # first category at top

            # Value labels at bar end
            for bar, val in zip(bars, values):
                ax.text(
                    bar.get_width() + max(values) * 0.01,
                    bar.get_y() + bar.get_height() / 2,
                    f"{int(val)}" if val == int(val) else f"{val:.1f}",
                    ha="left",
                    va="center",
                    fontsize=7.5,
                    fontweight="bold",
                    color="#1A1A1A",
                )

            ax.set_xlim(0, values.max() * 1.15)
            ax.grid(axis="x", alpha=0.6, linewidth=0.3, color="#F3F4F6")

        else:
            # ── Vertical columns ──────────────────────────────────────────
            x_pos = np.arange(n)
            bar_width = max(0.3, min(0.65, 1.2 / n))

            default_color = CATEGORY_COLORS.get("IN", "#0D9488")
            bars = ax.bar(
                x_pos,
                values,
                width=bar_width,
                color=colors if colors is not None else default_color,
                edgecolor="none",
                linewidth=0,
                zorder=3,
            )

            ax.set_xticks(x_pos)
            ax.set_xticklabels(labels, fontsize=8)

            # Value labels above columns
            for bar, val in zip(bars, values):
                ax.text(
                    bar.get_x() + bar.get_width() / 2,
                    bar.get_height() + values.max() * 0.01,
                    f"{int(val)}" if val == int(val) else f"{val:.1f}",
                    ha="center",
                    va="bottom",
                    fontsize=7.5,
                    fontweight="bold",
                    color="#1A1A1A",
                )

            ax.set_ylim(0, values.max() * 1.12)
            ax.grid(axis="y", alpha=0.6, linewidth=0.3, color="#F3F4F6")

        # ── Polish ────────────────────────────────────────────────────────
        ax.tick_params(axis="both", which="both", length=0)
        ax.set_xlabel("")
        ax.set_ylabel("")

        return _chart_to_base64(fig)
