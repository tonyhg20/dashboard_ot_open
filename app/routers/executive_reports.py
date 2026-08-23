"""
FastAPI router for the executive report feature.

Available endpoints
-------------------
- ``POST /api/reportes/executive/generate``  — Preview (returns HTML)
- ``POST /api/reportes/executive/download``   — Download .eml (Outlook-ready)
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any

from fastapi import APIRouter, Body, HTTPException
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel

from app.db import DB_CONFIG
from app.report_generator import ReportGenerator
from app.report_generator.email import EMLGenerator
from app.report_generator.v2 import ReportV2Generator
from app.report_generator.v2.generator import DEFAULT_HUBS

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/reportes/executive", tags=["executive-reports"])

# ── Request models ──────────────────────────────────────────────────────────


class ReportRequest(BaseModel):
    """Shared body for /generate and /download."""

    hub_ids: list[str]
    period: str = "weekly"
    dia: str | None = None  # YYYY-MM-DD, optional


# ── Helpers ────────────────────────────────────────────────────────────────


def _generate_report_id(hub_ids: list[str], dia: datetime.date | None, period: str) -> str:
    """Generate a unique report identifier."""
    date_str = dia.strftime("%Y%m%d") if dia else datetime.now().strftime("%Y%m%d")
    hubs = "_".join(sorted(hub_ids))
    return f"rep_{date_str}_{hubs}_{period}"


def _count_charts(charts: dict[str, Any]) -> int:
    """Count how many charts have a truthy value."""
    return sum(1 for v in charts.values() if v)


def _validate_empty_data(result) -> None:
    """If the report has no meaningful data, reject with 422."""
    metrics = result.metrics
    total = metrics.get("total_os", 0)
    charts = getattr(result, "charts", {})
    has_charts = _count_charts(charts) > 0

    if total == 0 and not has_charts:
        category_sum = sum(
            metrics.get(k, 0) for k in ("in_count", "tc_count", "rx_count", "dx_count", "ra_count")
        )
        if category_sum == 0:
            raise HTTPException(
                status_code=422,
                detail="No data available for the requested period and hubs",
            )


def _parse_dia(dia: str | None) -> datetime.date | None:
    """Parse *dia* as ``YYYY-MM-DD`` or return ``None``."""
    if dia is None:
        return None
    try:
        return datetime.strptime(dia, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid dia format {dia!r} — expected YYYY-MM-DD",
        )


def _validate_hub_ids(hub_ids: list[str]) -> None:
    if not hub_ids:
        raise HTTPException(status_code=422, detail="hub_ids must have at least 1 entry")
    if len(hub_ids) > 10:
        raise HTTPException(status_code=422, detail="hub_ids must have at most 10 entries")


def _build_generator() -> ReportGenerator:
    """Shortcut — create a ``ReportGenerator`` with the project's DB config."""
    return ReportGenerator(db_config=DB_CONFIG)


# ── Shared logic ────────────────────────────────────────────────────────────


def _generate(req: ReportRequest):
    """Generate report, validate data, return (result, report_id, chart_count)."""
    _validate_hub_ids(req.hub_ids)
    dia_date = _parse_dia(req.dia)

    try:
        gen = _build_generator()
        result = gen.generate_report(
            hub_ids=req.hub_ids,
            period=req.period,
            dia=dia_date,
        )
    except Exception as exc:
        log.exception("Report generation failed")
        raise HTTPException(status_code=500, detail=str(exc))

    _validate_empty_data(result)

    report_id = _generate_report_id(req.hub_ids, dia_date, req.period)
    chart_count = _count_charts(getattr(result, "charts", {}))
    return result, report_id, chart_count


# ── Endpoints ──────────────────────────────────────────────────────────────


@router.post("/generate")
async def generate_report(req: ReportRequest):
    """Generate the report HTML and return it inline (no download).

    Useful for previewing / testing before downloading.
    """
    result, report_id, chart_count = _generate(req)

    return {
        "status": "ok",
        "report_id": report_id,
        "html": result.html,
        "email_subject": result.subject,
        "chart_count": chart_count,
        "metrics": result.metrics,
        "generated_at": result.generated_at,
    }


@router.post("/download")
async def download_report(req: ReportRequest):
    """Generate the report and return it as a .eml file for Outlook.

    When opened, Outlook creates a *new* message with the report pre-loaded
    as the HTML body — no SMTP configuration needed.
    """
    result, report_id, chart_count = _generate(req)

    eml_bytes = EMLGenerator.generate_eml(
        html_content=result.html,
        subject=result.subject,
    )

    filename = f"{report_id}.eml"

    return Response(
        content=eml_bytes,
        media_type="message/rfc822",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(eml_bytes)),
        },
    )


# ── V2 Endpoint ────────────────────────────────────────────────────────────


@router.get("/generate-v2")
async def generate_v2():
    """Generate a Monarch-dark executive report landing page (v2).

    GET endpoint — open directly in browser for manual capture.
    """
    gen = ReportV2Generator()
    html = gen.generate_report(hub_ids=DEFAULT_HUBS, period="last_7_days")

    return HTMLResponse(content=html, status_code=200)
