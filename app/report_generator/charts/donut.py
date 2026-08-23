"""
Clean donut chart — category distribution with direct segment labels.

Intended for:
    - RA volume (RA vs rest)
    - Category breakdown (IN / TC / Rx / RA / Dx)

No legend — every segment is labelled directly with category + percentage.
White centre, no 3D, no explosion.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from .styles import CATEGORY_COLORS, _chart_to_base64, chart_context


def create_donut(
    df: pd.DataFrame,
    *,
    category_col: str = "category",
    value_col: str = "value",
    colors: dict[str, str] | None = None,
    hole_ratio: float = 0.55,
    figsize: tuple[float, float] | None = None,
    style: dict[str, Any] | None = None,
) -> dict:
    """Generate a clean donut chart with inline labels.

    Parameters
    ----------
    df : pd.DataFrame
        Must contain ``category_col`` (str) and ``value_col`` (numeric).
    category_col : str
        Name of the category column (default ``"category"``).
    value_col : str
        Name of the value column (default ``"value"``).
    colors : dict[str, str] | None
        Optional per-category colour map, merged on top of
        ``CATEGORY_COLORS``.  Unrecognised categories fall back to
        ``#999999``.
    hole_ratio : float
        Fraction of the donut radius that is hollow (default ``0.55``).
    figsize : tuple[float, float] | None
        Inches.  Default ``(2.0, 2.0)`` → 300 × 300 px at 150 dpi.
    style : dict | None
        Optional ``rcParams`` overrides.

    Returns
    -------
    dict
        ``{"base64": …, "format": "png", "width": …, "height": …}``
    """
    if figsize is None:
        figsize = (2.0, 2.0)

    required = {category_col, value_col}
    if not required.issubset(df.columns):
        msg = f"donut requires columns {required}, got {list(df.columns)}"
        raise ValueError(msg)

    # ── Sort by value descending ──────────────────────────────────────────
    data = df.sort_values(value_col, ascending=False)
    cats: list[str] = data[category_col].tolist()
    vals: np.ndarray = data[value_col].values.astype(float)

    total = float(vals.sum())
    if total == 0:
        # Edge case: all zeros — fall back to equal slices
        vals = np.ones_like(vals)
        total = float(vals.sum())

    # ── Resolve colours ──────────────────────────────────────────────────
    palette = dict(CATEGORY_COLORS)
    if colors:
        palette.update(colors)

    bar_colors = [palette.get(c, "#999999") for c in cats]

    with chart_context(overrides=style):
        import matplotlib.pyplot as plt  # noqa: PLC0415

        fig, ax = plt.subplots(figsize=figsize)

        wedges, texts = ax.pie(
            vals,
            labels=None,  # we draw our own labels below
            colors=bar_colors,
            startangle=90,
            counterclock=False,
            wedgeprops={
                "linewidth": 0,
                "edgecolor": "none",
                "width": hole_ratio,
            },
        )

        # ── Direct segment labels (category + percentage) ─────────────────
        for wedge, cat, val in zip(wedges, cats, vals):
            angle = (wedge.theta1 + wedge.theta2) / 2
            r = 0.5 + hole_ratio / 2  # middle of the annular ring
            x = r * np.cos(np.deg2rad(angle))
            y = r * np.sin(np.deg2rad(angle))

            pct = val / total * 100
            label = (
                f"{cat}\n{pct:.1f}%"
                if pct >= 4.0
                else ""  # skip tiny slices to avoid crowding
            )
            if label:
                ax.text(
                    x, y,
                    label,
                    ha="center",
                    va="center",
                    fontsize=7,
                    fontweight="bold" if pct >= 10 else "normal",
                    color="#1A1A1A",
                )

        # ── Equal aspect + no axes ────────────────────────────────────────
        ax.set_aspect("equal")
        ax.set_axis_off()

        return _chart_to_base64(fig)
