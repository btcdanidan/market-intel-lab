from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = Field(default="market-intel-lab", alias="APP_NAME")
    app_env: str = Field(default="local", alias="APP_ENV")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    port: int = Field(default=8000, alias="PORT")

    database_url: str = Field(
        default="postgresql+psycopg://market:market@localhost:5432/market_intel",
        alias="DATABASE_URL",
    )
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")

    schedule_cron: str = Field(default="0 8 * * *", alias="SCHEDULE_CRON")
    schedule_timezone: str = Field(default="UTC", alias="SCHEDULE_TIMEZONE")

    reports_dir: str = Field(default="reports", alias="REPORTS_DIR")

    asset_universe_raw: str = Field(default="BTC,ETH,SOL,BNB,XRP", alias="ASSET_UNIVERSE")
    exchanges_raw: str = Field(default="binance,coinbase", alias="EXCHANGES")
    primary_options_venue: str = Field(default="deribit", alias="PRIMARY_OPTIONS_VENUE")

    portfolio_equity: float = Field(default=100_000, alias="PORTFOLIO_EQUITY")
    per_trade_risk_pct: float = Field(default=1.0, alias="PER_TRADE_RISK_PCT")
    max_gross_exposure: float = Field(default=2.5, alias="MAX_GROSS_EXPOSURE")
    drawdown_kill_switch_pct: float = Field(default=10.0, alias="DRAWDOWN_KILL_SWITCH_PCT")
    stop_atr_multiplier: float = Field(default=1.2, alias="STOP_ATR_MULTIPLIER")

    binance_api_key: str | None = Field(default=None, alias="BINANCE_API_KEY")
    binance_api_secret: str | None = Field(default=None, alias="BINANCE_API_SECRET")
    coinbase_api_key: str | None = Field(default=None, alias="COINBASE_API_KEY")
    coinbase_api_secret: str | None = Field(default=None, alias="COINBASE_API_SECRET")
    deribit_client_id: str | None = Field(default=None, alias="DERIBIT_CLIENT_ID")
    deribit_client_secret: str | None = Field(default=None, alias="DERIBIT_CLIENT_SECRET")

    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    openai_chat_model: str = Field(default="gpt-4.1-mini", alias="OPENAI_CHAT_MODEL")
    openai_chat_temperature: float = Field(default=0.2, alias="OPENAI_CHAT_TEMPERATURE")
    openai_chat_max_output_tokens: int = Field(default=700, alias="OPENAI_CHAT_MAX_OUTPUT_TOKENS")
    chat_max_turns: int = Field(default=12, alias="CHAT_MAX_TURNS")

    data_stale_minutes: int = Field(default=15, alias="DATA_STALE_MINUTES")

    @property
    def asset_universe(self) -> list[str]:
        return [item.strip().upper() for item in self.asset_universe_raw.split(",") if item.strip()]

    @property
    def exchanges(self) -> list[str]:
        return [item.strip().lower() for item in self.exchanges_raw.split(",") if item.strip()]

    @property
    def reports_path(self) -> Path:
        return Path(self.reports_dir)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
