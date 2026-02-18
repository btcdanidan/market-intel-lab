from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

RunStatus = Literal["running", "completed", "failed"]
RegimeState = Literal["risk-on", "risk-off", "transition"]
Direction = Literal["Long", "Short"]


class AnalysisRequest(BaseModel):
    assets: list[str] | None = None
    window_hours: int = 24
    portfolio_equity: float | None = None
    per_trade_risk_pct: float | None = None
    reason: str = "manual"


class MarketSnapshot(BaseModel):
    venue: str
    symbol: str
    ts: datetime
    spot_price: float | None = None
    perp_price: float | None = None
    funding_rate: float | None = None
    perp_open_interest: float | None = None
    bid: float | None = None
    ask: float | None = None
    bid_size: float | None = None
    ask_size: float | None = None
    options_put_oi: float | None = None
    options_call_oi: float | None = None
    options_skew_25d: float | None = None
    implied_vol: float | None = None
    data_quality: list[str] = Field(default_factory=list)
    raw: dict[str, Any] = Field(default_factory=dict)


class DerivedSignals(BaseModel):
    symbol: str
    orderbook_score: float
    positioning_score: float
    options_score: float
    basis_score: float
    valuation_gap_z: float
    regime: RegimeState
    confidence: float
    components: dict[str, float] = Field(default_factory=dict)


class TradeSetup(BaseModel):
    symbol: str
    direction: Direction
    horizon_days: int
    thesis: str
    catalysts: list[str]
    entry_zone: str
    stop: float
    targets: list[float]
    reward_risk: float
    invalidation_trigger: str
    what_changes_my_mind: str
    size_notional: float
    confidence: Literal["Low", "Med", "High"]


class RiskState(BaseModel):
    gross_exposure: float
    dd_pct: float
    kill_switch: bool
    per_trade_risk_budget: float
    remaining_budget: float
    notes: list[str] = Field(default_factory=list)


class ScenarioCase(BaseModel):
    name: Literal["base", "bullish", "bearish"]
    probability: int
    description: str
    expected_path: str


class DailyMemo(BaseModel):
    run_id: str
    generated_at: datetime
    regime: RegimeState
    market_brief: dict[str, Any]
    trade_memos: list[TradeSetup]
    scenarios: list[ScenarioCase]
    bullish_counterargument: str
    bearish_counterargument: str
    facts: list[str]
    assumptions: list[str]
    inferences: list[str]
    data_gaps: list[str]
    risk_state: RiskState


class AnalysisResult(BaseModel):
    run_id: str
    status: RunStatus
    regime: RegimeState
    degraded: bool
    memo_path: str
    memo_body: str
    snapshots: list[MarketSnapshot]
    signals: list[DerivedSignals]
    trade_setups: list[TradeSetup]
    risk_state: RiskState
    facts: list[str]
    assumptions: list[str]
    inferences: list[str]
    data_gaps: list[str]


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1)


class ChatStreamRequest(BaseModel):
    run_id: str = Field(min_length=1)
    question: str = Field(min_length=1)
    messages: list[ChatMessage] = Field(default_factory=list)


class ChatStreamDone(BaseModel):
    answer: str
    citations: list[str]
    run_id: str
    model: str
    citation_note: str | None = None
