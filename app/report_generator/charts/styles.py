"""
Editorial chart style — "The Economist" inspired, light theme.

Thread-safe: uses matplotlib's Agg backend (non-interactive) at import time.
Style is applied via ``plt.rc_context()`` for isolation between chart calls.

Usage::

    from .styles import chart_context, _chart_to_base64

    with chart_context(overrides=None):
        fig, ax = plt.subplots(figsize=(4, 2))
        ax.plot(...)
        return _chart_to_base64(fig, dpi=150)

Public API
----------
- chart_context(overrides=None) → context manager that applies editorial rcParams
- _chart_to_base64(fig, dpi=150) → {"base64": str, "format": "png", "width": int, "height": int}
"""

from __future__ import annotations

import base64
import io
from contextlib import contextmanager
from typing import Any

import matplotlib
# ── Non-interactive backend — MUST be set before any pyplot import ──────────
matplotlib.use("Agg")

import matplotlib.pyplot as plt

# ── Category → Colour mapping (shared across all charts) ───────────────────

CATEGORY_COLORS: dict[str, str] = {
    "IN": "#0D9488",    # Teal
    "TC": "#F97316",    # Orange/coral
    "Rx": "#7C3AED",    # Purple
    "RA": "#EC4899",    # Pink
    "Dx": "#6B7280",    # Gray
}

CATEGORY_LABELS: dict[str, str] = {
    "IN": "IN",
    "TC": "TC",
    "Rx": "Rx",
    "RA": "RA",
    "Dx": "Dx",
}

# ── Editorial rcParams defaults ────────────────────────────────────────────

_EDITORIAL_RCPARAMS: dict[str, Any] = {
    # Figure — high DPI for crisp output in email
    "figure.facecolor": "#FFFFFF",
    "figure.dpi": 200,
    "savefig.dpi": 200,
    "savefig.bbox": "tight",
    "savefig.pad_inches": 0.15,
    # Axes
    "axes.facecolor": "#FFFFFF",
    "axes.edgecolor": "#E5E7EB",
    "axes.linewidth": 0.0,
    "axes.labelcolor": "#6B7280",
    "axes.titlecolor": "#111827",
    "axes.titleweight": "bold",
    "axes.titlelocation": "left",
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.spines.left": False,
    "axes.spines.bottom": False,
    "axes.grid": False,
    # Ticks
    "xtick.color": "#D1D5DB",
    "ytick.color": "#D1D5DB",
    "xtick.labelsize": 9,
    "ytick.labelsize": 9,
    # Grid — very subtle, light gray
    "grid.color": "#F3F4F6",
    "grid.alpha": 0.6,
    "grid.linewidth": 0.5,
    # Font — clean sans-serif (Latinometrics style)
    # Uses DejaVu Sans as reliable fallback on Docker slim images
    "font.family": "sans-serif",
    "font.sans-serif": [
        "Inter",
        "DejaVu Sans",
        "system-ui",
        "sans-serif",
    ],
    "font.size": 11,
    # Legend
    "legend.fontsize": 9,
    "legend.frameon": False,
    "legend.loc": "best",
    "legend.handlelength": 1.0,
    "legend.handletextpad": 0.5,
    "legend.labelspacing": 0.3,
    "legend.borderpad": 0.3,
    # Lines — bolder for clarity at high DPI
    "lines.linewidth": 2.0,
    "lines.markersize": 6,
    "lines.markeredgewidth": 0.0,
    # Save
    "savefig.facecolor": "#FFFFFF",
    "savefig.edgecolor": "none",
}


# ── Label helper (shared across all charts) ──────────────────────────────


def add_data_labels(
    ax: matplotlib.axes.Axes,
    fmt: str = "{:.0f}",
    fontsize: int = 8,
    color: str = "#1A1A1A",
    offset: float = 4,
) -> None:
    """Add value labels on top of bars / data points.

    Works with:
    - ``BarContainer`` (bar / column charts) via ``ax.bar_label``.
    - ``Line2D`` artists (trend / sparkline charts) via per-point annotations.

    Parameters
    ----------
    ax : matplotlib.axes.Axes
        The axes to label.
    fmt : str
        Format string for values (default ``"{:.0f}"``).
    fontsize : int
        Label font size.
    color : str
        Label colour.
    offset : float
        Padding in points above bars or data points.
    """
    # ── Bar / column containers ─────────────────────────────────────────
    for container in ax.containers:
        try:
            ax.bar_label(container, fmt=fmt, fontsize=fontsize, color=color, padding=offset)
        except (TypeError, AttributeError):
            pass

    # ── Line2D data points ──────────────────────────────────────────────
    for line in ax.lines:
        xdata, ydata = line.get_xdata(), line.get_ydata()
        line_color = line.get_color()
        for xi, yi in zip(xdata, ydata):
            ax.annotate(
                fmt.format(yi),
                xy=(xi, yi),
                xytext=(0, offset),
                textcoords="offset points",
                ha="center",
                va="bottom",
                fontsize=fontsize,
                color=line_color,
                fontweight="bold",
            )


@contextmanager
def chart_context(overrides: dict[str, Any] | None = None):
    """Context manager that applies editorial rcParams (plus optional overrides).

    The context is entered *inside* ``plt.rc_context`` so that the previous
    rcParams are restored on exit — even if an exception is raised inside the
    ``with`` block.

    Parameters
    ----------
    overrides : dict | None
        Additional rcParams to merge on top of the editorial defaults.
    """
    params = dict(_EDITORIAL_RCPARAMS)
    if overrides:
        params.update(overrides)
    with plt.rc_context(params):
        yield


def _chart_to_base64(
    fig: matplotlib.figure.Figure,
    dpi: int = 200,
) -> dict:
    """Render a matplotlib figure to a base64 PNG dict (no disk writes).

    Parameters
    ----------
    fig : matplotlib.figure.Figure
        The figure to render.
    dpi : int
        Output DPI (overrides ``savefig.dpi`` from the context).

    Returns
    -------
    dict
        ``{"base64": str, "format": "png", "width": int, "height": int}``
    """
    buf = io.BytesIO()
    fig.savefig(
        buf,
        format="png",
        dpi=dpi,
        bbox_inches="tight",
        pad_inches=0.1,
        facecolor=fig.get_facecolor(),
        edgecolor="none",
    )
    plt.close(fig)
    buf.seek(0)

    w_px, h_px = fig.get_size_inches()
    w_px = int(round(w_px * dpi))
    h_px = int(round(h_px * dpi))

    return {
        "base64": base64.b64encode(buf.getvalue()).decode("utf-8"),
        "format": "png",
        "width": w_px,
        "height": h_px,
    }
