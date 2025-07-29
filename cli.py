import argparse
import asyncio
import logging

from backend.utils.logger import setup_logging
from backend.utils.config import settings
from backend.integrations.bybit_client import get_bybit_client
from backend.core.trading_engine import TradingEngine
from backend.core.signal_processor import SignalProcessor
from backend.core.risk_manager import RiskManager
import uvicorn


async def run_console() -> None:
    """Run trading engine directly from the console."""
    setup_logging()
    logger = logging.getLogger("cli")
    logger.info("Starting trading engine in console mode...")

    bybit_client = await get_bybit_client(
        api_key=settings.bybit_api_key,
        api_secret=settings.bybit_api_secret,
        testnet=settings.bybit_testnet,
        demo=settings.bybit_demo,
    )

    engine = TradingEngine(bybit_client, SignalProcessor(), RiskManager())
    await engine.start()
    logger.info("Trading started. Press Ctrl+C to stop.")
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        logger.info("Stopping trading...")
        engine.stop()


def run_web() -> None:
    """Run the FastAPI web server."""
    uvicorn.run(
        "backend.main:app",
        host=settings.host,
        port=5000,
        reload=False,
        log_level="info",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Bybit Trading Bot CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("web", help="Run web interface")
    subparsers.add_parser("console", help="Run trading engine in console")

    args = parser.parse_args()

    if args.command == "web":
        run_web()
    else:
        asyncio.run(run_console())


if __name__ == "__main__":
    main()
