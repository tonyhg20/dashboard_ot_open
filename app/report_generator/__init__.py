"""
Executive Report — packages for report generation.

Public API
----------
- ``ReportGenerator`` — Orchestrator: SQL → charts → Jinja2 → HTML
- ``ReportResult`` — Dataclass holding the rendered HTML + metadata
"""

from .generator import ReportGenerator, ReportResult

__all__ = [
    "ReportGenerator",
    "ReportResult",
]
