"""
Executive Report − Chart generators.

All chart generators return a dict:
    {
        "base64": str,       # base64-encoded PNG (no data: URI prefix)
        "format": "png",
        "width": int,        # pixels
        "height": int,       # pixels
    }

Every generator accepts:
    figsize : tuple[float, float] | None  — matplotlib inches (default per chart)
    style   : dict | None                  — rcParams overrides on top of editorial defaults
"""

from .sparkline import create_sparkline
from .trend_chart import create_trend_chart
from .bar_chart import create_bar_chart
from .bullet_chart import create_bullet_chart
from .donut import create_donut
from .small_multiples import create_small_multiples

__all__ = [
    "create_sparkline",
    "create_trend_chart",
    "create_bar_chart",
    "create_bullet_chart",
    "create_donut",
    "create_small_multiples",
]
