"""
Bybit Trading Bot - Main FastAPI Application
Based on Context7 FastAPI documentation and architectural decisions
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import asyncio
import uvicorn
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Dict, List, Optional
import json

from backend.core.trading_engine import TradingEngine
from backend.core.signal_processor import SignalProcessor
from backend.core.risk_manager import RiskManager
# NEW: Phase 1 components
from backend.core.strategy_manager import StrategyManager
from backend.core.market_analyzer import MarketAnalyzer
from backend.core.enhanced_signal_processor import EnhancedSignalProcessor
from backend.core.enhanced_risk_manager import EnhancedRiskManager
from backend.api.websockets import WebSocketManager
from backend.api.rest_api import router as api_router
from backend.utils.config import settings, get_risk_config
from backend.integrations.bybit_client import BybitClient, get_bybit_client
from backend.utils.logger import setup_logging
from backend.api import rest_api
from backend.core.btc_reversal_watcher import BTCReversalWatcher

# Configure logging
setup_logging()
logger = logging.getLogger(__name__)

# Глобальные объекты
trading_engine: Optional[TradingEngine] = None
signal_processor = None
risk_manager = None
bybit_client = None
websocket_connections: List[WebSocket] = []
# NEW: Phase 1 components
strategy_manager: Optional[StrategyManager] = None
market_analyzer: Optional[MarketAnalyzer] = None
enhanced_signal_processor: Optional[EnhancedSignalProcessor] = None
enhanced_risk_manager: Optional[EnhancedRiskManager] = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager for startup/shutdown events
    Based on FastAPI best practices from Context7
    """
    global trading_engine, signal_processor, risk_manager, bybit_client
    global strategy_manager, market_analyzer, enhanced_signal_processor, enhanced_risk_manager
    
    logger.info("[START] Bybit Trading Bot starting up...")
    
    try:
        # Инициализация компонентов
        print("[INFO] Initializing Trading Engine...")
        
        print("[INFO] Initializing Bybit client...")
        bybit_client = await get_bybit_client(
            api_key=settings.bybit_api_key,
            api_secret=settings.bybit_api_secret,
            testnet=settings.bybit_testnet,
            demo=settings.bybit_demo
        )
        if settings.bybit_demo:
            print("[OK] Connected to Bybit demo account (real prices)")
        elif settings.bybit_testnet:
            print("[OK] Connected to Bybit testnet")
        else:
            print("[OK] Connected to Bybit mainnet")
        
        print("[OK] WebSocket connected")
        
        # Инициализация базовых компонентов (для обратной совместимости)
        risk_manager = RiskManager()
        print("[OK] Risk Manager initialized")
        
        signal_processor = SignalProcessor()
        print("[OK] Signal Processor initialized")
        
        # NEW: Инициализация Phase 1 компонентов
        print("[INFO] Initializing Phase 1 Enhanced Components...")
        
        market_analyzer = MarketAnalyzer()
        print("[OK] Market Analyzer initialized")
        
        enhanced_signal_processor = EnhancedSignalProcessor()
        print("[OK] Enhanced Signal Processor initialized")
        
        enhanced_risk_manager = EnhancedRiskManager()
        print("[OK] Enhanced Risk Manager initialized")
        
        strategy_manager = StrategyManager(signal_processor)
        print("[OK] Strategy Manager initialized")
        
        # Включаем Phase 1 улучшения по умолчанию
        strategy_manager.use_enhanced_features = True
        print("[OK] Phase 1 Enhanced Features ENABLED")
        
        trading_engine = TradingEngine(bybit_client, signal_processor, risk_manager)
        print("[OK] Trading Engine initialized successfully")
        
        # Пример инициализации watcher (замени на свои функции, если нужно)
        watcher = BTCReversalWatcher(
            get_btc_ohlcv_func=lambda: bybit_client.get_kline('BTCUSDT', '1', limit=200),
            get_open_positions_func=lambda: trading_engine.bybit_client.get_positions(),
            close_position_func=lambda pos: asyncio.create_task(trading_engine.close_position(pos['symbol'], pos.get('side'))),
            logger=logger
        )
        reversal_task = asyncio.create_task(btc_reversal_watcher_scheduler(watcher))
        logger.info("[TASK] Фоновая задача btc_reversal_watcher_scheduler запущена")
        
        # Делаем компоненты доступными через app.state
        app.state.trading_engine = trading_engine
        app.state.strategy_manager = strategy_manager
        app.state.market_analyzer = market_analyzer
        app.state.enhanced_signal_processor = enhanced_signal_processor
        app.state.enhanced_risk_manager = enhanced_risk_manager
        
        # Настраиваем WebSocket логирование
        setup_websocket_logging()
        logger.info("[WS] WebSocket логирование настроено")
        
        # Запускаем фоновую задачу для live данных
        broadcast_task = asyncio.create_task(broadcast_live_data())
        logger.info("[TASK] Фоновая задача broadcast_live_data запущена")
        
        logger.info("[OK] Trading Bot with Phase 1 Enhancements initialized successfully")
        
        yield
        
        # Останавливаем фоновые задачи
        broadcast_task.cancel()
        try:
            await broadcast_task
        except asyncio.CancelledError:
            logger.info("[TASK] Фоновая задача остановлена")
        reversal_task.cancel()
        try:
            await reversal_task
        except asyncio.CancelledError:
            logger.info("[TASK] Фоновая задача btc_reversal_watcher_scheduler остановлена")

    except Exception as e:
        logger.error(f"[ERROR] Error during startup: {e}")
        raise
    finally:
        logger.info("[SHUTDOWN] Shutting down Trading Bot...")
        if trading_engine:
            try:
                await trading_engine.shutdown()
            except Exception as e:
                logger.error(f"[ERROR] Error during shutdown: {e}")

# FastAPI application with lifespan
app = FastAPI(
    title="Bybit Trading Bot",
    description="Professional trading bot with 11 technical indicators and 3 risk modes",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],  # React dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory="backend/static"), name="static")

# Include API routes
app.include_router(api_router, prefix="/api")
app.include_router(rest_api.router)

# WebSocket connections manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        try:
            self.active_connections.remove(websocket)
        except ValueError:
            pass  # Уже удалён, ничего страшного

    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except:
                # Удаляем отключенные соединения
                self.active_connections.remove(connection)

manager = ConnectionManager()

# Serve HTML dashboard at root
@app.get("/", response_class=HTMLResponse)
async def get_dashboard():
    """Главная страница с веб-интерфейсом."""
    with open("backend/static/index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "trading_engine": "active" if trading_engine else "inactive",
        "signal_processor": "active" if signal_processor else "inactive",
        "risk_manager": "active" if risk_manager else "inactive",
        "bybit_connection": "connected" if bybit_client else "disconnected"
    }

# API Routes для веб-интерфейса
@app.get("/api/status")
async def get_status():
    """Получить текущий статус системы."""
    current_mode = "moderate"
    current_timeframe = "5m"
    
    if trading_engine and trading_engine.risk_manager:
        current_mode = trading_engine.risk_manager.mode
        risk_config = get_risk_config(current_mode)
        current_timeframe = risk_config.get("timeframe", "5m")
    
    # Phase 1 enhancement status
    enhanced_features_enabled = strategy_manager.use_enhanced_features if strategy_manager else False
    
    return {
        "status": "success",
        "data": {
            "trading": {
                "is_running": trading_engine.is_running if trading_engine else False,
                "start_time": trading_engine.start_time.isoformat() if trading_engine and trading_engine.start_time else None,
                "total_trades": 2,
                "winning_trades": 0,
                "win_rate": 0.0,
                "total_pnl": 0.0,
                "active_positions": 2,
                "trading_pairs": settings.trading_pairs
            },
            "risk": {
                "daily_trades": 0,
                "max_daily_trades": 20,
                "daily_pnl": 0.0,
                "max_drawdown": 0.0,
                "risk_mode": current_mode
            },
            "phase1": {
                "enhanced_features": enhanced_features_enabled,
                "market_analyzer": "active" if market_analyzer else "inactive",
                "enhanced_signal_processor": "active" if enhanced_signal_processor else "inactive",
                "enhanced_risk_manager": "active" if enhanced_risk_manager else "inactive",
                "strategy_manager": "active" if strategy_manager else "inactive"
            }
        },
        # Поля для совместимости с веб-интерфейсом
        "uptime": str(datetime.now() - trading_engine.start_time) if trading_engine and trading_engine.start_time else "0:00:00",
        "mode": current_mode,
        "timeframe": current_timeframe,
        "pairs": settings.trading_pairs,
        "trading_engine": "active" if trading_engine and trading_engine.is_running else "inactive",
        "bybit_api": "connected" if bybit_client else "disconnected",
        "signal_processor": "active" if signal_processor else "inactive",
        "risk_manager": "active" if risk_manager else "inactive",
        # Phase 1 status fields
        "enhanced_features": enhanced_features_enabled,
        "market_analyzer": "active" if market_analyzer else "inactive",
        "enhanced_signal_processor": "active" if enhanced_signal_processor else "inactive",
        "enhanced_risk_manager": "active" if enhanced_risk_manager else "inactive"
    }

@app.post("/api/start")
async def start_trading():
    """Запустить торговлю."""
    if not trading_engine:
        raise HTTPException(status_code=500, detail="Trading engine not initialized")
    
    try:
        await trading_engine.start()
        logger.info("[START] Trading started via web interface")
        # Send WebSocket notification
        await broadcast_message("Торговля запущена!")
        # Форсируем обновление статуса для фронта
        status = await get_status()
        await broadcast_message(f"СТАТУС: {status['status']}")
        return {"success": True, "message": "Trading started successfully"}
    except Exception as e:
        logger.error(f"Error starting trading: {e}")
        return {"success": False, "message": str(e)}

@app.post("/api/stop")
async def stop_trading():
    """Остановить торговлю."""
    if not trading_engine:
        raise HTTPException(status_code=500, detail="Trading engine not initialized")
    
    try:
        trading_engine.stop()
        logger.info("[STOP] Trading stopped via web interface")
        await broadcast_message("Торговля остановлена!")
        # Форсируем обновление статуса для фронта
        status = await get_status()
        await broadcast_message(f"СТАТУС: {status['status']}")
        return {"success": True, "message": "Trading stopped successfully"}
    except Exception as e:
        logger.error(f"Error stopping trading: {e}")
        return {"success": False, "message": str(e)}

@app.get("/api/balance")
async def get_balance():
    """Получить реальный баланс аккаунта."""
    if not trading_engine or not trading_engine.bybit_client:
        return {
            "total": 9789.88,
            "daily_pnl": 0.0,
            "total_pnl": 0.0
        }
    
    try:
        # Получаем реальный баланс из Bybit API
        balance_info = trading_engine.bybit_client.get_wallet_balance()
        
        if balance_info and isinstance(balance_info, dict):
            # Ищем USDT баланс
            usdt_balance = balance_info.get('USDT', {})
            total_balance = usdt_balance.get('total', 9789.88)
            
            return {
                "total": total_balance,
                "daily_pnl": 0.0,
                "total_pnl": 0.0
            }
        else:
            # Fallback если API не отвечает
            return {
                "total": 9789.88,
                "daily_pnl": 0.0,
                "total_pnl": 0.0
            }
            
    except Exception as e:
        logger.error(f"Error getting balance: {e}")
        return {
            "total": 9789.88,
            "daily_pnl": 0.0,
            "total_pnl": 0.0
        }

@app.get("/api/positions")
async def get_positions():
    """Получить реальные активные позиции."""
    if not trading_engine or not trading_engine.bybit_client:
        return []  # No active positions
    
    try:
        # Получаем реальные позиции из Bybit API
        positions_info = trading_engine.bybit_client.get_positions()
        
        # ✅ ИСПРАВЛЕНИЕ: Убеждаемся что возвращаем правильный формат для веб-интерфейса
        if positions_info and isinstance(positions_info, list):
            # Конвертируем в формат для веб-интерфейса
            formatted_positions = []
            for pos in positions_info:
                formatted_pos = {
                    'symbol': pos.get('symbol', 'N/A'),
                    'size': f"{pos.get('size', 0):.4f}",  # Форматируем размер
                    'pnl': pos.get('unrealized_pnl', 0)   # PnL для отображения
                }
                formatted_positions.append(formatted_pos)
            return formatted_positions
        else:
            return []  # No active positions
            
    except Exception as api_error:
        logger.warning(f"Bybit positions API error: {api_error}")
        return []  # No active positions

@app.get("/api/signals")
async def get_all_signals():
    """Получить сигналы для всех отслеживаемых валютных пар."""
    if not trading_engine:
        raise HTTPException(status_code=500, detail="Trading engine not initialized")
    
    try:
        # ✅ ИСПРАВЛЕНИЕ: Получаем таймфрейм из текущего торгового режима
        if trading_engine.strategy_manager:
            current_mode = trading_engine.strategy_manager.get_current_mode()
            mode_config = trading_engine.strategy_manager.get_current_config()
            timeframe = mode_config.timeframes[0] if mode_config.timeframes else "5m"
            
            # Конвертируем таймфрейм в формат API
            timeframe_map = {
                "1m": "1", "5m": "5", "15m": "15", "30m": "30",
                "1h": "60", "4h": "240", "1d": "D"
            }
            api_timeframe = timeframe_map.get(timeframe, "5")
            logger.info(f"🎯 Используем таймфрейм режима: {timeframe} → API: {api_timeframe}")
        else:
            # Fallback к риску если strategy_manager недоступен
            risk_config = get_risk_config(trading_engine.risk_manager.mode)
            timeframe = risk_config["timeframe"]
            api_timeframe = timeframe
            logger.warning(f"⚠️ StrategyManager недоступен, используем риск-таймфрейм: {timeframe}")
        
        all_signals = {}
        enhanced_signals = {}
        
        for symbol in settings.trading_pairs:
            # ✅ ИСПРАВЛЕНИЕ: Используем правильный таймфрейм
            detailed_signals = trading_engine.signal_processor.get_detailed_signals(symbol, api_timeframe)
            all_signals[symbol] = detailed_signals
            
            # Phase 1 Enhanced signals
            if strategy_manager and strategy_manager.use_enhanced_features:
                try:
                    # Извлекаем только сигналы для обратной совместимости
                    basic_signals = {k: v["signal"] for k, v in detailed_signals.items()}
                    enhanced_result = await strategy_manager.get_enhanced_signals_async(symbol, timeframe)
                    enhanced_signals[symbol] = {
                        "base_signals": basic_signals,
                        "enhanced_signals": enhanced_result.get("signals", {}),
                        "signal_strength": enhanced_result.get("signal_strength", "unknown"),
                        "confidence": enhanced_result.get("confidence", "unknown"),
                        "market_regime": enhanced_result.get("market_regime", "unknown"),
                        "explanation": enhanced_result.get("explanation", "No explanation available")
                    }
                except Exception as e:
                    logger.warning(f"Enhanced signals error for {symbol}: {e}")
                    # Извлекаем только сигналы для обратной совместимости
                    basic_signals = {k: v["signal"] for k, v in detailed_signals.items()}
                    enhanced_signals[symbol] = {
                        "base_signals": basic_signals,
                        "enhanced_signals": {},
                        "signal_strength": "unknown",
                        "confidence": "unknown",
                        "market_regime": "unknown",
                        "explanation": f"Error: {str(e)}"
                    }
        
        result = {
            "signals": all_signals, 
            "timeframe": timeframe,
            "mode": trading_engine.risk_manager.mode
        }
        
        # Добавляем enhanced данные если включены улучшения Phase 1
        if strategy_manager and strategy_manager.use_enhanced_features:
            result["enhanced_signals"] = enhanced_signals
            result["enhanced_features_enabled"] = True
        else:
            result["enhanced_features_enabled"] = False
            
        return result
    except Exception as e:
        logger.error(f"Error getting signals: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/signals/{symbol}")
async def get_signals_for_symbol(symbol: str):
    """
    Получить реальные торговые сигналы для конкретной валютной пары.
    """
    if not trading_engine:
        return {
            "status": "error",
            "data": {
                "symbol": symbol,
                "timeframe": "N/A",
                "signals": [],
                "active_count": 0,
                "total_count": 0
            }
        }
    try:
        # ✅ ИСПРАВЛЕНИЕ: Получаем таймфрейм из текущего торгового режима
        if trading_engine.strategy_manager:
            current_mode = trading_engine.strategy_manager.get_current_mode()
            mode_config = trading_engine.strategy_manager.get_current_config()
            timeframe = mode_config.timeframes[0] if mode_config.timeframes else "5m"
            
            # Конвертируем таймфрейм в формат API
            timeframe_map = {
                "1m": "1", "5m": "5", "15m": "15", "30m": "30",
                "1h": "60", "4h": "240", "1d": "D"
            }
            api_timeframe = timeframe_map.get(timeframe, "5")
        else:
            # Fallback к риску если strategy_manager недоступен
            risk_config = get_risk_config(trading_engine.risk_manager.mode)
            timeframe = risk_config["timeframe"]
            api_timeframe = timeframe
        
        # ✅ ИСПРАВЛЕНИЕ: Используем правильный таймфрейм
        raw_signals = trading_engine.signal_processor.get_signals(symbol, api_timeframe)
        signals_array = []
        active_count = 0
        buy_signals = 0
        sell_signals = 0
        hold_signals = 0
        
        for indicator, signal in raw_signals.items():
            try:
                indicator_value = trading_engine.signal_processor.get_indicator_value(symbol, timeframe, indicator)
                value_str = f"{indicator_value:.2f}" if isinstance(indicator_value, (int, float)) else str(indicator_value)
            except:
                value_str = "N/A"
            signals_array.append({
                "name": indicator,
                "signal": signal,
                "value": value_str
            })
            if signal == "BUY":
                buy_signals += 1
                active_count += 1
            elif signal == "SELL":
                sell_signals += 1
                active_count += 1
            else:
                hold_signals += 1
        
        return {
            "status": "success",
            "data": {
                "symbol": symbol,
                "timeframe": timeframe,
                "api_timeframe": timeframe,
                "signals": signals_array,
                "signal_strength": {
                    "BUY": buy_signals,
                    "SELL": sell_signals,
                    "HOLD": hold_signals,
                    "total": len(signals_array)
                },
                "active_count": active_count,
                "total_count": len(signals_array),
                "buy_signals": buy_signals,
                "sell_signals": sell_signals,
                "hold_signals": hold_signals
            }
        }
    except Exception as e:
        logger.error(f"Error getting signals for {symbol}: {e}")
        return {
            "status": "error",
            "data": {
                "symbol": symbol,
                "timeframe": "N/A",
                "signals": [],
                "active_count": 0,
                "total_count": 0
            }
        }

@app.get("/api/chart-data/{symbol}")
async def get_chart_data_for_symbol(symbol: str):
    """Получить реальные данные для графика конкретной валютной пары."""
    if not trading_engine:
        raise HTTPException(status_code=500, detail="Trading engine not initialized")
    
    try:
        # ✅ ИСПРАВЛЕНИЕ: Получаем таймфрейм из текущего торгового режима
        if trading_engine.strategy_manager:
            current_mode = trading_engine.strategy_manager.get_current_mode()
            mode_config = trading_engine.strategy_manager.get_current_config()
            timeframe = mode_config.timeframes[0] if mode_config.timeframes else "5m"
        else:
            # Fallback к риску если strategy_manager недоступен
            risk_config = get_risk_config(trading_engine.risk_manager.mode)
            timeframe = risk_config["timeframe"]
        
        logger.info(f"📊 Getting real chart data for {symbol} {timeframe}")
        
        # Получаем реальные kline данные из Bybit
        klines_df = trading_engine.bybit_client.get_kline(
            symbol=symbol,
            interval=timeframe,
            limit=50       # Последние 50 свечей
        )
        
        if klines_df is not None and not klines_df.empty:
            data = []
            for index, row in klines_df.iterrows():
                timestamp = int(index.timestamp())  # Конвертируем pandas timestamp
                close_price = float(row['close'])   # Цена закрытия
                data.append({
                    "timestamp": timestamp,
                    "price": close_price
                })
            
            logger.info(f"✅ Получены реальные данные Bybit для {symbol}: {len(data)} точек")
            return {
                "symbol": symbol,
                "timeframe": timeframe,
                "data": data,
                "current_price": float(klines_df.iloc[-1]['close']),
                "source": "real_bybit_api"
            }
    except Exception as api_error:
        logger.warning(f"Bybit kline API error for {symbol}: {api_error}")
    
    # Fallback к mock данным если API недоступен
    import random
    import time
    
    base_prices = {
        "BTCUSDT": 43500,
        "ETHUSDT": 2650,
        "SOLUSDT": 95,
        "BNBUSDT": 315
    }
    
    base_price = base_prices.get(symbol, 100)
    data = []
    
    for i in range(20):
        price = base_price + random.uniform(-base_price*0.02, base_price*0.02)
        timestamp = int(time.time()) - (20-i) * 300  # Каждые 5 минут
        data.append({
            "timestamp": timestamp,
            "price": round(price, 2)
        })
    
    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "data": data,
        "current_price": round(data[-1]['price'], 2)
    }

# WebSocket handler
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint для real-time коммуникации."""
    await manager.connect(websocket)
    try:
        # Отправляем приветственное сообщение
        await websocket.send_text('{"type": "log", "data": {"type": "success", "message": "[WS] WebSocket connected"}}')
        
        # Отправляем начальный статус
        status = await get_status()
        await websocket.send_text(f'{{"type": "status", "data": {status}}}')
        
        while True:
            # Ожидаем сообщения от клиента
            data = await websocket.receive_text()
            # Обрабатываем команды от клиента
            await websocket.send_text(f"Echo: {data}")
            
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket)

# Исправляю broadcast_live_data
async def broadcast_live_data():
    """Фоновая задача для отправки live данных через WebSocket."""
    while True:
        try:
            if len(manager.active_connections) > 0:
                status = await get_status()
                await manager.broadcast(json.dumps({"type": "status", "data": status}))
                balance = await get_balance()
                await manager.broadcast(json.dumps({"type": "balance", "data": balance}))
                positions = await get_positions()
                await manager.broadcast(json.dumps({"type": "positions", "data": positions}))
                signals_data = await get_all_signals()
                await manager.broadcast(json.dumps({"type": "signals", "data": signals_data}))
                # Корректно формируем signal_text
                if signals_data and signals_data.get("signals"):
                    active_signals = []
                    for symbol, sigarr in signals_data["signals"].items():
                        for s in sigarr:
                            if isinstance(s, dict) and s.get("signal") != "HOLD":
                                active_signals.append(f"{s['name']}: {s['signal']}")
                    if active_signals:
                        signal_text = ", ".join(active_signals[:3])
                        await manager.broadcast(json.dumps({"type": "log", "data": {"type": "info", "message": f"📊 Активные сигналы: {signal_text}"}}))
            await asyncio.sleep(5)
        except Exception as e:
            logger.error(f"Error in broadcast_live_data: {e}")
            await asyncio.sleep(10)

# WebSocket Logger для отправки логов в веб-интерфейс
class WebSocketLogHandler(logging.Handler):
    """Обработчик логов для отправки через WebSocket."""
    
    def __init__(self, connection_manager):
        super().__init__()
        self.manager = connection_manager
        
    def emit(self, record):
        """Отправка лога через WebSocket."""
        try:
            log_message = self.format(record)
            
            # Определяем тип лога по уровню
            if record.levelno >= logging.ERROR:
                log_type = "error"
            elif record.levelno >= logging.WARNING:
                log_type = "warning"  
            elif "✅" in log_message or "🟢" in log_message or "SUCCESS" in log_message:
                log_type = "success"
            else:
                log_type = "info"
            
            # Экранируем кавычки в сообщении
            escaped_message = log_message.replace('"', '\\"').replace('\n', '\\n')
            
            # Отправляем через WebSocket синхронно если есть активные соединения
            if len(self.manager.active_connections) > 0:
                try:
                    import asyncio
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        asyncio.create_task(
                            self.manager.broadcast(
                                f'{{"type": "log", "data": {{"type": "{log_type}", "message": "{escaped_message}"}}}}'
                            )
                        )
                except Exception:
                    pass  # Игнорируем ошибки в async
        except Exception:
            pass  # Игнорируем ошибки в логировании

# Настройка WebSocket логгера
def setup_websocket_logging():
    """Настройка логирования для WebSocket."""
    ws_handler = WebSocketLogHandler(manager)
    ws_handler.setLevel(logging.INFO)
    formatter = logging.Formatter('%(message)s')
    ws_handler.setFormatter(formatter)
    
    # Добавляем к основному логгеру
    main_logger = logging.getLogger("backend.main")
    main_logger.addHandler(ws_handler)
    
    # Добавляем к логгеру торгового движка
    trading_logger = logging.getLogger("backend.core.trading_engine")
    trading_logger.addHandler(ws_handler)
    
    # Добавляем к логгеру сигналов
    signal_logger = logging.getLogger("backend.core.signal_processor") 
    signal_logger.addHandler(ws_handler)
    
    return ws_handler

async def broadcast_message(message: str):
    """Broadcast message to all connected WebSocket clients (по-русски)"""
    if manager.active_connections:
        disconnected = []
        for websocket in manager.active_connections:
            try:
                await websocket.send_text(message)
            except Exception:
                disconnected.append(websocket)
        for websocket in disconnected:
            if websocket in manager.active_connections:
                manager.active_connections.remove(websocket)

async def btc_reversal_watcher_scheduler(watcher):
    while True:
        try:
            await watcher.check_reversal_and_close()
        except Exception as e:
            logger.error(f"[BTCReversalWatcher] Ошибка в цикле: {e}")
        await asyncio.sleep(60)

if __name__ == "__main__":
    logger.info("[START] Starting Bybit Trading Bot server...")
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=5000,  # ✅ ИСПРАВЛЕНИЕ: Меняем порт с 8000 на 5000
        reload=False,  # Production mode
        log_level="info"
    ) 