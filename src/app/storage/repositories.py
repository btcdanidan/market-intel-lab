from __future__ import annotations

from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from datetime import UTC, datetime

from sqlalchemy import create_engine, desc, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.types import DerivedSignals, MarketSnapshot, RiskState, TradeSetup
from app.storage.models import (
    AnalysisRunModel,
    Base,
    DerivedSignalModel,
    MarketSnapshotModel,
    TradeSetupModel,
)


class AnalysisRepository:
    def __init__(self, database_url: str):
        connect_args: dict[str, object] = {}
        if database_url.startswith("sqlite"):
            connect_args["check_same_thread"] = False
        self.engine = create_engine(database_url, future=True, connect_args=connect_args)
        self.session_factory = sessionmaker(
            bind=self.engine, expire_on_commit=False, class_=Session
        )

    def init_db(self) -> None:
        Base.metadata.create_all(self.engine)

    @contextmanager
    def _session(self) -> Iterator[Session]:
        session = self.session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def create_run(self, run_id: str, reason: str, assets: list[str], payload: dict) -> None:
        run = AnalysisRunModel(
            id=run_id,
            status="running",
            reason=reason,
            assets=assets,
            request_payload=payload,
            quality={},
            regime="transition",
            degraded=False,
        )
        with self._session() as session:
            session.add(run)

    def store_snapshots(self, run_id: str, snapshots: Sequence[MarketSnapshot]) -> None:
        rows = [
            MarketSnapshotModel(
                run_id=run_id,
                symbol=snapshot.symbol,
                venue=snapshot.venue,
                ts=snapshot.ts,
                payload=snapshot.model_dump(mode="json"),
            )
            for snapshot in snapshots
        ]
        with self._session() as session:
            session.add_all(rows)

    def store_signals(self, run_id: str, signals: Sequence[DerivedSignals]) -> None:
        rows = [
            DerivedSignalModel(
                run_id=run_id,
                symbol=signal.symbol,
                orderbook_score=signal.orderbook_score,
                positioning_score=signal.positioning_score,
                options_score=signal.options_score,
                basis_score=signal.basis_score,
                valuation_gap_z=signal.valuation_gap_z,
                regime=signal.regime,
                confidence=signal.confidence,
                components=signal.components,
            )
            for signal in signals
        ]
        with self._session() as session:
            session.add_all(rows)

    def store_trade_setups(self, run_id: str, setups: Sequence[TradeSetup]) -> None:
        rows = [
            TradeSetupModel(
                run_id=run_id,
                symbol=setup.symbol,
                direction=setup.direction,
                reward_risk=setup.reward_risk,
                size_notional=setup.size_notional,
                payload=setup.model_dump(mode="json"),
            )
            for setup in setups
        ]
        with self._session() as session:
            session.add_all(rows)

    def mark_run_completed(
        self,
        run_id: str,
        regime: str,
        degraded: bool,
        quality: dict,
        memo_path: str,
        memo_body: str,
    ) -> None:
        with self._session() as session:
            run = session.get(AnalysisRunModel, run_id)
            if run is None:
                return
            run.status = "completed"
            run.regime = regime
            run.degraded = degraded
            run.quality = quality
            run.memo_path = memo_path
            run.memo_body = memo_body
            run.completed_at = datetime.now(UTC)

    def mark_run_failed(self, run_id: str, error_message: str) -> None:
        with self._session() as session:
            run = session.get(AnalysisRunModel, run_id)
            if run is None:
                return
            run.status = "failed"
            run.error_message = error_message
            run.completed_at = datetime.now(UTC)

    def get_run(self, run_id: str) -> dict | None:
        with self._session() as session:
            run = session.get(AnalysisRunModel, run_id)
            if run is None:
                return None
            return self._run_dict(run)

    def get_latest_run(self) -> dict | None:
        with self._session() as session:
            stmt = select(AnalysisRunModel).order_by(desc(AnalysisRunModel.created_at)).limit(1)
            run = session.scalar(stmt)
            if run is None:
                return None
            return self._run_dict(run)

    def list_runs(self, limit: int = 20) -> list[dict]:
        with self._session() as session:
            stmt = select(AnalysisRunModel).order_by(desc(AnalysisRunModel.created_at)).limit(limit)
            runs = session.scalars(stmt).all()
            return [self._run_summary(run) for run in runs]

    @staticmethod
    def _run_dict(run: AnalysisRunModel) -> dict:
        return {
            "id": run.id,
            "status": run.status,
            "reason": run.reason,
            "assets": run.assets,
            "quality": run.quality,
            "regime": run.regime,
            "degraded": run.degraded,
            "memo_path": run.memo_path,
            "memo_body": run.memo_body,
            "error_message": run.error_message,
            "created_at": run.created_at.isoformat() if run.created_at else None,
            "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        }

    @staticmethod
    def _run_summary(run: AnalysisRunModel) -> dict:
        return {
            "id": run.id,
            "status": run.status,
            "regime": run.regime,
            "degraded": run.degraded,
            "created_at": run.created_at.isoformat() if run.created_at else None,
            "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        }


def summarize_risk_state(risk_state: RiskState) -> dict:
    return risk_state.model_dump(mode="json")
