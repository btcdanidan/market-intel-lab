from __future__ import annotations

import logging
from datetime import UTC, datetime

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from redis import Redis

from app.config.settings import Settings
from app.core.service import AnalysisService
from app.core.types import AnalysisRequest

logger = logging.getLogger(__name__)


class AnalysisScheduler:
    def __init__(self, settings: Settings, service: AnalysisService, redis_client: Redis):
        self.settings = settings
        self.service = service
        self.redis = redis_client
        self.scheduler = BackgroundScheduler(timezone=self.settings.schedule_timezone)

    def start(self) -> None:
        trigger = CronTrigger.from_crontab(
            self.settings.schedule_cron, timezone=self.settings.schedule_timezone
        )
        self.scheduler.add_job(
            self._scheduled_run,
            trigger=trigger,
            id="daily_analysis",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )
        self.scheduler.start()
        logger.info("Scheduler started with cron '%s'", self.settings.schedule_cron)

    def shutdown(self) -> None:
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
            logger.info("Scheduler stopped")

    def _scheduled_run(self) -> None:
        lock_key = "market-intel-lab:analysis-lock"
        lock_value = datetime.now(UTC).isoformat()
        acquired = self.redis.set(lock_key, lock_value, ex=60 * 30, nx=True)
        if not acquired:
            logger.warning("Scheduled run skipped because lock is already held")
            return

        try:
            self.service.run_analysis(AnalysisRequest(reason="scheduled"))
            logger.info("Scheduled analysis completed")
        except Exception:  # noqa: BLE001
            logger.exception("Scheduled analysis failed")
        finally:
            self.redis.delete(lock_key)
