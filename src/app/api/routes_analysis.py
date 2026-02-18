from __future__ import annotations

from typing import Annotated, Any, cast

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from app.core.service import AnalysisService
from app.core.types import AnalysisRequest

router = APIRouter()


class AnalysisRunRequest(BaseModel):
    assets: list[str] | None = None
    window_hours: int = Field(default=24, ge=1, le=168)
    portfolio_equity: float | None = Field(default=None, gt=0)
    per_trade_risk_pct: float | None = Field(default=None, ge=0.1, le=5.0)


class AnalysisRunResponse(BaseModel):
    run_id: str
    status: str
    regime: str
    degraded: bool
    memo_path: str


def get_service(request: Request) -> AnalysisService:
    return cast(AnalysisService, request.app.state.analysis_service)


@router.post("/analysis/run", response_model=AnalysisRunResponse)
def run_analysis(
    payload: AnalysisRunRequest,
    service: Annotated[AnalysisService, Depends(get_service)],
) -> AnalysisRunResponse:
    result = service.run_analysis(
        AnalysisRequest(
            assets=payload.assets,
            window_hours=payload.window_hours,
            portfolio_equity=payload.portfolio_equity,
            per_trade_risk_pct=payload.per_trade_risk_pct,
            reason="manual",
        )
    )
    return AnalysisRunResponse(
        run_id=result.run_id,
        status=result.status,
        regime=result.regime,
        degraded=result.degraded,
        memo_path=result.memo_path,
    )


@router.get("/analysis/runs")
def list_runs(
    service: Annotated[AnalysisService, Depends(get_service)],
    limit: int = Query(default=20, ge=1, le=200),
) -> dict[str, Any]:
    return {"runs": service.list_runs(limit=limit)}


@router.get("/analysis/{run_id}")
def get_analysis(
    run_id: str,
    service: Annotated[AnalysisService, Depends(get_service)],
) -> dict[str, Any]:
    run = service.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


@router.get("/status/latest")
def get_latest_status(
    service: Annotated[AnalysisService, Depends(get_service)],
) -> dict[str, Any]:
    run = service.get_latest_run()
    if run is None:
        return {
            "status": "empty",
            "message": "No runs found",
        }
    return run
