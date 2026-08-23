"""
Small multiples — hub comparison chart using grouped horizontal bars.

Input expects a **long-form** DataFrame::

    hub     metric  value
    ZAP     IN      312
    ZAP     TC       98
    ZAP     Rx       45
    VIL     IN      245
    VIL     TC      112
    VIL     Rx       38
    …

Each hub gets a mini row of bars, one per metric, sharing a common axis
so the reader can compare magnitudes across hubs at a glance.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from .styles import CATEGORY_COLORS, CATEGORY_LABELS, _chart_to_base64, chart_context


def create_small_multiples(
    df: pd.DataFrame,
    *,
    figsize: tuple[float, float] | None = None,
    style: dict[str, Any] | None = None,
) -> dict:
    """Generate a small-multiples grouped bar chart for hub comparison.

    Parameters
    ----------
    df : pd.DataFrame
        Long-form data with columns ``["hub", "metric", "value"]``.
        ``hub`` and ``metric`` are strings; ``value`` is numeric.
    figsize : tuple[float, float] | None
        Inches.  Default ``(4.0, 1.6)`` → 600 × 240 px at 150 dpi.
    style : dict | None
        Optional ``rcParams`` overrides.

    Returns
    -------
    dict
        ``{"base64": …, "format": "png", "width": …, "height": …}``
    """
    if figsize is None:
        figsize = (4.0, 1.6)

    required = {"hub", "metric", "value"}
    if not required.issubset(df.columns):
        msg = f"small_multiples requires columns {required}, got {list(df.columns)}"
        raise ValueError(msg)

    # ── Pivot: hub × metric ───────────────────────────────────────────────
    pivot = df.pivot_table(
        index="hub",
        columns="metric",
        values="value",
        aggfunc="sum",
    ).fillna(0).sort_index()

    hubs: list[str] = pivot.index.tolist()
    metrics: list[str] = pivot.columns.tolist()
    n_hubs = len(hubs)
    n_metrics = len(metrics)

    if n_hubs == 0 or n_metrics == 0:
        msg = "small_multiples requires at least one hub and one metric"
        raise ValueError(msg)

    # ── Colours per metric ────────────────────────────────────────────────
    bar_colors = [CATEGORY_COLORS.get(m, "#999999") for m in metrics]
    bar_labels = [CATEGORY_LABELS.get(m, m) for m in metrics]

    # Global max for shared axis
    global_max = pivot.values.max()

    with chart_context(overrides=style):
        import matplotlib.pyplot as plt  # noqa: PLC0415

        fig, axes = plt.subplots(
            nrows=1,
            ncols=n_hubs,
            figsize=figsize,
            sharey=True,
            gridspec_kw={"wspace": 0.08},
        )

        # Ensure axes is iterable even for a single hub
        if n_hubs == 1:
            axes = [axes]

        for idx, hub in enumerate(hubs):
            ax = axes[idx]
            values = pivot.loc[hub, metrics].values.astype(float)
            x_pos = np.arange(n_metrics)
            bar_width = 0.45

            bars = ax.bar(
                x_pos,
                values,
                width=bar_width,
                color=bar_colors,
                edgecolor="none",
                linewidth=0,
                zorder=3,
            )

            # ── Value labels on bars ──────────────────────────────────────
            for bar, val in zip(bars, values):
                if val > 0:
                    ax.text(
                        bar.get_x() + bar.get_width() / 2,
                        bar.get_height() + global_max * 0.02,
                        f"{int(val)}" if val == int(val) else f"{val:.1f}",
                        ha="center",
                        va="bottom",
                        fontsize=6.5,
                        fontweight="bold",
                        color="#1A1A1A",
                    )

            # ── Axes polish ──────────────────────────────────────────────
            ax.set_xticks(x_pos)
            ax.set_xticklabels(bar_labels, fontsize=6.5)
            ax.set_title(hub, fontsize=8, fontweight="bold", pad=4)
            ax.tick_params(axis="both", length=0, pad=2)
            ax.set_ylim(0, global_max * 1.18)
            ax.grid(axis="y", alpha=0.6, linewidth=0.3, color="#F3F4F6")

            # Only show y-ticks on the leftmost axis
            if idx > 0:
                ax.tick_params(labelleft=False)
                ax.set_ylabel("")

        # ── Single y-label on the left ────────────────────────────────────
        axes[0].set_ylabel("Órdenes", fontsize=8, color="#6B7280")

        return _chart_to_base64(fig)
