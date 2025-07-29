# BybitBotGPT Code Overview

This document provides an overview of the repository structure, the main modules and scripts, and how the pieces fit together. Use it as a reference when working on the code base.

## Top level layout

```
bybitbotgpt/
├── backend/              # FastAPI application
├── memory-bank/          # Documentation (tasks, progress, contexts)
├── logs/                 # Log files
├── *.md                  # Additional documentation in Russian
├── *.bat / *.py          # Helper scripts and tests
```

### Key files

- `README.md` – high level instructions for running the trading bot, configuration examples and API overview.
- `PHASE1_USER_GUIDE.md` – user guide describing Phase 1 “enhanced” features: market analysis, improved signals and trailing stops.
- `project_structure_and_errors_report.md` – an automatically generated report summarising file layout and possible issues.
- `config.example` / `config.env` – environment variables for Bybit API keys, trading pairs and web server settings.

Most other `.md` files contain Russian notes about trading strategies and optimisation approaches.

## Backend application

The backend is implemented with FastAPI inside the `backend/` folder.

```
backend/
├── api/              # HTTP and WebSocket endpoints
├── core/             # Trading logic and strategy modules
├── integrations/     # Wrappers for external services (Bybit)
├── static/           # HTML, JS and CSS for the dashboard
├── utils/            # Configuration, logging and error handling helpers
└── main.py           # Application entry point
```

### API layer

`backend/api/rest_api.py` defines many REST endpoints. They expose functionality such as balance/positions retrieval, order placement and controlling trading modes. It also provides advanced endpoints introduced in Phase 1: market analysis, enhanced signals, position sizing, trailing stops and export utilities.

`backend/api/websockets.py` implements `WebSocketManager`, a helper used to maintain client connections and broadcast real‑time updates (signals, market data, logs).

### Core modules

`backend/core/trading_engine.py` is the central class orchestrating trading. It coordinates the `SignalProcessor`, `RiskManager`, `StrategyManager` and communicates with `BybitClient`. The trading loop fetches market data, generates signals and decides whether to place orders. The engine tracks active positions, handles position sizing, TP/SL calculation and includes extra logic for trailing stops and position correction.

`backend/core/signal_processor.py` calculates technical indicators (RSI, MACD, Bollinger Bands, etc.) and produces trading signals. It can also return detailed values for UI display.

`backend/core/risk_manager.py` defines basic risk controls like daily trade limits and confidence thresholds.

`backend/core/strategy_manager.py`, `market_analyzer.py`, `enhanced_signal_processor.py`, `enhanced_risk_manager.py` and other files implement Phase 1 features such as advanced market analysis and adaptive risk management.

Other helper modules include `trade_analyzer.py` for statistics, `pair_reversal_watcher.py` for monitoring price reversals and `auto_param_adjuster.py` for automatically tuning parameters.

### Integrations

`backend/integrations/bybit_client.py` wraps Bybit API calls (REST and WebSocket). It provides methods for getting klines, placing orders, fetching account balance and positions.

### Utilities

- `backend/utils/config.py` loads environment variables using `pydantic` and exposes the `settings` object with all configuration values. It also defines `get_risk_config`.
- `backend/utils/logger.py` configures the logging system. Log files are stored in `logs/`, and log messages can be sent to WebSocket clients.
- `backend/utils/error_handler.py` (not shown above) contains decorators for capturing exceptions.

### Static files

The dashboard UI lives in `backend/static/`. The main page is `index.html` which loads Bootstrap and custom JS (`app.js`). The frontend connects to the FastAPI WebSocket at `/ws` for live updates and uses REST endpoints for manual actions (start/stop trading, mode changes, fetching signals). CSS files in this folder control the look of the interface.

### Application startup

`backend/main.py` creates the FastAPI app with a lifespan handler. During startup it sets up logging, initialises Bybit client and the core managers, schedules background tasks (broadcasting live data, parameter adjustment, pair reversal monitoring) and mounts the REST router and static files. It exposes endpoints like `/api/start`, `/api/stop`, `/api/balance`, `/api/positions` and WebSocket `/ws`.

To run the server locally:

```bash
python -m backend.main
```
(or run `start_web.bat` on Windows). The web UI then becomes available at `http://localhost:8000/` (or whichever port is configured).

## Documentation folders

`memory-bank/` stores markdown documents for project planning:
- `tasks.md` – active tasks and fixes performed on the interface.
- `progress.md` – progress log.
- `productContext.md`, `techContext.md` etc. – additional context notes.

`cursor-memory-bank/` is currently empty but reserved for generated diagrams or other documentation.

## Scripts and tests

Several Python scripts (`demo_test.py`, `demo_test_simple.py`, `test_demo_connection.py`, `test_demo_direct.py`, `test_real_demo.py`, etc.) are provided to test API connectivity and basic trading logic in demo mode. `.bat` files serve as shortcuts for Windows to install dependencies or start the bot.

## Logs

The `logs/` folder contains rotating log files produced by the logger. The main file names look like `trading_bot_YYYYMMDD.log`, plus `errors.log` for captured exceptions and `trading.log` for trade actions.

## Summary

This repository implements a Bybit trading bot with a FastAPI backend and a lightweight web dashboard. The core components handle signal generation, risk management and strategy logic, while API modules expose REST/WebSocket endpoints for controlling the bot and delivering real‑time data to the UI. Extensive documentation in the root and `memory-bank` directories describes the trading strategies and project tasks.
