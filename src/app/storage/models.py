from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class AnalysisRunModel(Base):
    __tablename__ = "analysis_runs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    reason: Mapped[str] = mapped_column(String(32), nullable=False)
    assets: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    request_payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    quality: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    regime: Mapped[str] = mapped_column(String(32), nullable=False, default="transition")
    degraded: Mapped[bool] = mapped_column(nullable=False, default=False)
    memo_path: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    memo_body: Mapped[str] = mapped_column(Text, nullable=False, default="")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    snapshots: Mapped[list[MarketSnapshotModel]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )
    signals: Mapped[list[DerivedSignalModel]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )
    trade_setups: Mapped[list[TradeSetupModel]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )


class MarketSnapshotModel(Base):
    __tablename__ = "market_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("analysis_runs.id", ondelete="CASCADE"), index=True
    )
    symbol: Mapped[str] = mapped_column(String(16), nullable=False)
    venue: Mapped[str] = mapped_column(String(32), nullable=False)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)

    run: Mapped[AnalysisRunModel] = relationship(back_populates="snapshots")


class DerivedSignalModel(Base):
    __tablename__ = "derived_signals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("analysis_runs.id", ondelete="CASCADE"), index=True
    )
    symbol: Mapped[str] = mapped_column(String(16), nullable=False)
    orderbook_score: Mapped[float] = mapped_column(Float, nullable=False)
    positioning_score: Mapped[float] = mapped_column(Float, nullable=False)
    options_score: Mapped[float] = mapped_column(Float, nullable=False)
    basis_score: Mapped[float] = mapped_column(Float, nullable=False)
    valuation_gap_z: Mapped[float] = mapped_column(Float, nullable=False)
    regime: Mapped[str] = mapped_column(String(16), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    components: Mapped[dict] = mapped_column(JSON, nullable=False)

    run: Mapped[AnalysisRunModel] = relationship(back_populates="signals")


class TradeSetupModel(Base):
    __tablename__ = "trade_setups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("analysis_runs.id", ondelete="CASCADE"), index=True
    )
    symbol: Mapped[str] = mapped_column(String(16), nullable=False)
    direction: Mapped[str] = mapped_column(String(8), nullable=False)
    reward_risk: Mapped[float] = mapped_column(Float, nullable=False)
    size_notional: Mapped[float] = mapped_column(Float, nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)

    run: Mapped[AnalysisRunModel] = relationship(back_populates="trade_setups")
