from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from app.report.render import to_html, to_pdf
from app.schemas import ThreatModel

router = APIRouter(tags=["report"])


@router.post("/report/html")
def report_html(tm: ThreatModel) -> Response:
    return Response(content=to_html(tm), media_type="text/html; charset=utf-8")


@router.post("/report/pdf")
def report_pdf(tm: ThreatModel) -> Response:
    try:
        pdf = to_pdf(tm)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Falha ao gerar PDF: {e}") from e
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="relatorio-stride.pdf"'},
    )
