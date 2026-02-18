# market-intel-lab

Local-first crypto market analysis and trade memo engine.

## What it does

- Ingests spot and perp data from configured venues using `ccxt`.
- Pulls options context from Deribit (native API) for skew and put/call pressure.
- Computes market-structure, positioning, valuation, and regime signals.
- Applies hard risk controls and position sizing.
- Produces daily markdown memo output for `BTC, ETH, SOL, BNB, XRP`.
- Exposes a browser dashboard at `/` with embedded Codex-style run Q&A chat.
- Exposes local API endpoints for analysis automation and streaming chat.

## Core risk defaults

- Horizon: Swing (`2-20 days`)
- Per-trade risk budget: `1.0%` of portfolio equity
- Max gross exposure: `2.5x`
- Drawdown kill-switch: `10%`
- Stop method: structure invalidation + `1.2x ATR` buffer

## Quickstart (local machine)

1. Copy environment template:

```bash
cp .env.example .env
```

2. Start services:

```bash
docker compose up --build
```

3. Open the dashboard:

`http://localhost:8000`

4. Run an on-demand analysis (optional API path):

```bash
curl -X POST http://localhost:8000/analysis/run \
  -H "Content-Type: application/json" \
  -d '{"portfolio_equity": 100000}'
```

5. Check latest status:

```bash
curl http://localhost:8000/status/latest
```

## API

- `POST /analysis/run`
- `GET /analysis/{run_id}`
- `GET /analysis/runs`
- `GET /health`
- `GET /status/latest`
- `GET /chat/status`
- `POST /chat/stream` (SSE)

## Chat

- Set `OPENAI_API_KEY` in `.env` to enable the embedded chat panel.
- Chat is analysis-scoped and grounded to selected run context.
- Chat history is stored in browser local storage per run.

## Development

Install dependencies:

```bash
python3 -m pip install -e '.[dev]'
```

Run tests:

```bash
python3 -m pytest
```

Run lint/type checks:

```bash
python3 -m ruff check src tests
python3 -m mypy src
```

## Notes

- Advisory-only scope in v1 (no live order execution).
- If critical market feeds are stale, the engine marks run output as degraded and suppresses actionable trade calls.
