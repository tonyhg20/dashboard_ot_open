"""
Executive Report v2 — Playwright-based PNG report generation.

Public API
----------
- ``ReportV2Generator`` — Orchestrator: SQL → KPI → chart data → Jinja2 → Playwright PNG

v2 replaces matplotlib-based HTML email with Monarch dark theme, inline SVG charts,
and Playwright full-page PNG capture.  v1 (``ReportGenerator``) kept as fallback.
"""

from __future__ import annotations

from .generator import ReportV2Generator

__all__ = [
    "ReportV2Generator",
]
