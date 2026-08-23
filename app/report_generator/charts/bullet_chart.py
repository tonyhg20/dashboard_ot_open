"""
Bullet graph — a compact, dashboard-friendly KPI gauge.

Shows:
1. Qualitative background bands (poor → satisfactory → good → excellent).
2. Actual value as a thick horizontal bar.
3. Target / benchmark as a thin vertical marker line.
4. Annotated actual and target values.

Inspired by Stephen Few's bullet graph design.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from .styles import _chart_to_base64, chart_context

# ── Default qualitative ranges (IN/TC ratio bands) ────────────────────────

_DEFAULT_RANGES: list[tuple[float, float, str]] = [
    (0.0, 1.5, "#E8E8E8"),   # poor — lightest gray
    (1.5, 2.5, "#DCDCDC"),   # satisfactory
    (2.5, 3.5, "#D0D0D0"),   # good
    (3.5, 5.0, "#C4C4C4"),   # excellent — darkest gray
]


def create_bullet_chart(
    actual: float,
    target: float,
    *,
    ranges: list[tuple[float, float, str]] | None = None,
    bar_color: str = "#2E5984",
    target_color: str = "#1A1A1A",
    figsize: tuple[float, float] | None = None,
    style: dict[str, Any] | None = None,
) -> dict:
    """Generate a horizontal bullet graph.

    Parameters
    ----------
    actual : float
        The current measured value.
    target : float
        The benchmark / goal value.
    ranges : list[tuple[float, float, str]] | None
        Qualitative background bands as ``(lo, hi, hex_color)``.
        Defaults to IN/TC ratio bands: poor → excellent in grays.
    bar_color : str
        Colour of the actual-value bar.
    target_color : str
        Colour of the target marker line.
    figsize : tuple[float, float] | None
        Inches.  Default ``(4.0, 0.3)`` → 600 × 45 px at 150 dpi.
    style : dict | None
        Optional ``rcParams`` overrides.

    Returns
    -------
    dict
        ``{"base64": …, "format": "png", "width": …, "height": …}``
    """
    if figsize is None:
        figsize = (4.0, 0.35)

    if ranges is None:
        ranges = _DEFAULT_RANGES

    with chart_context(overrides=style):
        import matplotlib.pyplot as plt  # noqa: PLC0415

        fig, ax = plt.subplots(figsize=figsize)

        max_range = max(hi for _, hi, _ in ranges)
        plot_max = max(max_range, actual * 1.15, target * 1.15)

        # ── Qualitative background bands ─────────────────────────────────
        for lo, hi, color in ranges:
            ax.axvspan(lo, hi, color=color, linewidth=0, zorder=1)

        # ── Actual value bar ──────────────────────────────────────────────
        bar_height = 0.5
        ax.barh(
            0,
            actual,
            height=bar_height,
            color=bar_color,
            edgecolor="none",
            zorder=3,
        )

        # ── Target marker ─────────────────────────────────────────────────
        ax.axvline(
            target,
            ymin=0.15,
            ymax=0.85,
            color=target_color,
            linewidth=1.8,
            zorder=4,
            solid_capstyle="round",
        )

        # ── Value labels ──────────────────────────────────────────────────
        # Actual value label
        ax.text(
            actual,
            0,
            f"{actual:.1f}" if actual != int(actual) else str(int(actual)),
            ha="left" if actual < plot_max * 0.85 else "right",
            va="center",
            fontsize=8,
            fontweight="bold",
            color="#1A1A1A",
            zorder=5,
        )

        # ── Axes stripping ────────────────────────────────────────────────
        ax.set_ylim(-0.6, 0.6)
        ax.set_xlim(0, plot_max)
        ax.set_yticks([])
        ax.set_xticks([])
        for spine_key in ("left", "right", "top", "bottom"):
            ax.spines[spine_key].set_visible(False)
        ax.tick_params(left=False, bottom=False, labelleft=False, labelbottom=False)

        return _chart_to_base64(fig)
