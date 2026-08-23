"""
Tiny sparkline chart for KPI cards — no axes, no labels, no grid.

Used for:
    - Total OS Volume sparkline
    - TC Rate sparkline with Δ% indicator

All configuration is internal — the caller just passes values.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from .styles import CATEGORY_COLORS, _chart_to_base64, chart_context


def create_sparkline(
    values: list[float | int],
    *,
    color: str | None = None,
    figsize: tuple[float, float] | None = None,
    style: dict[str, Any] | None = None,
) -> dict:
    """Generate a tiny sparkline (no axes, just a line + fill + final dot).

    Parameters
    ----------
    values : list[float | int]
        Chronological data points.  Empty or single-point lists return a
        minimal placeholder.
    color : str | None
        Line colour.  Defaults to teal ``#0D9488`` (IN).
    figsize : tuple[float, float] | None
        Figure size in inches.  Default is ``(1.33, 0.27)`` → 200 × 40 px at
        150 dpi.  **Must be wide enough to avoid visual clipping.**
    style : dict | None
        Optional ``rcParams`` overrides merged on top of the editorial style.

    Returns
    -------
    dict
        ``{"base64": …, "format": "png", "width": …, "height": …}``
    """
    if figsize is None:
        figsize = (1.33, 0.27)  # ~200 × 40 px at 150 dpi

    if color is None:
        color = CATEGORY_COLORS["IN"]

    with chart_context(overrides=style):
        import matplotlib.pyplot as plt  # noqa: PLC0415 — safe inside rc_context

        fig, ax = plt.subplots(figsize=figsize)

        # ── Strip all axes furniture ──────────────────────────────────────
        ax.set_axis_off()
        # Also remove the figure-level spine container
        for spine in ax.spines.values():
            spine.set_visible(False)
        ax.tick_params(left=False, bottom=False, labelleft=False, labelbottom=False)

        n = len(values)
        if n < 2:
            # Placeholder — horizontal line at y=0
            ax.plot([0, 1], [0, 0], color=color, linewidth=2)
        else:
            x = np.arange(n)
            y = np.asarray(values, dtype=float)

            ax.plot(x, y, color=color, linewidth=2, solid_capstyle="round")

            # Subtle fill below the line
            ax.fill_between(x, y, alpha=0.1, color=color, linewidth=0)

            # Last-value dot
            ax.scatter(
                [x[-1]],
                [y[-1]],
                s=12,  # marker area in points²
                c=color,
                edgecolors="none",
                zorder=5,
            )

        # Tight bounds so the line touches the figure edges
        ax.set_xlim(0, max(n - 1, 1))
        # Leave 5 % vertical padding
        if n >= 2:
            y_min, y_max = y.min(), y.max()
            y_range = max(y_max - y_min, 1)
            margin = y_range * 0.05
            ax.set_ylim(y_min - margin, y_max + margin)

        render = _chart_to_base64(fig)
        # Sparkline dimensions may differ from figsize pixel math — trust
        # what _chart_to_base64 computes.

    return render
