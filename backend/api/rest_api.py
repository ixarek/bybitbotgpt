"""
REST API endpoints for Bybit Trading Bot
Provides HTTP endpoints for bot control and data access
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, List, Optional
from pydantic import BaseModel
import asyncio
import logging
import os
import csv
from fastapi.responses import StreamingResponse
from ..utils.config import settings

logger = logging.getLogger(__name__)

# Request/Response models
class OrderRequest(BaseModel):
    symbol: str
    side: str  # "Buy" or "Sell"
    order_type: str  # "Market" or "Limit"
    quantity: float
    price: Optional[float] = None

class RiskModeRequest(BaseModel):
    risk_mode: str  # "risky", "moderate", "conservative"

class TradingControlRequest(BaseModel):
    action: str  # "start" or "stop"

class EnhancedFeaturesRequest(BaseModel):
    enabled: bool

class AutoCloseRequest(BaseModel):
    enabled: bool

class TrailingStopRequest(BaseModel):
    symbol: str
    side: str  # "BUY" or "SELL"
    entry_price: float
    stop_type: str = "trailing"  # "trailing", "atr_based", "percentage"

class PositionSizeRequest(BaseModel):
    symbol: str
    current_price: float
    account_balance: float = 1000.0

# Create router
router = APIRouter()

# Dependencies to get components (will be injected by main app)
async def get_trading_engine():
    from ..main import app
    return app.state.trading_engine

async def get_strategy_manager():
    from ..main import app
    return app.state.strategy_manager

async def get_market_analyzer():
    from ..main import app
    return app.state.market_analyzer

async def get_enhanced_signal_processor():
    from ..main import app
    return app.state.enhanced_signal_processor

async def get_enhanced_risk_manager():
    from ..main import app
    return app.state.enhanced_risk_manager

async def get_pair_watcher():
    from ..main import app
    return getattr(app.state, 'pair_reversal_watcher', None)

@router.get("/balance")
async def get_balance(trading_engine = Depends(get_trading_engine)):
    """Get account balance"""
    try:
        if not trading_engine.bybit_client:
            raise HTTPException(status_code=503, detail="Bybit client not initialized")
        
        balance = trading_engine.bybit_client.get_wallet_balance()
        if balance is None:
            # Fallback to mock data if API fails
            balance = {"USDT": {"available": 9789.88, "locked": 0.0, "total": 9789.88}}
        
        return balance
    except Exception as e:
        # Return mock data on error
        logger.error(f"Error getting balance: {e}")
        return {"USDT": {"available": 9789.88, "locked": 0.0, "total": 9789.88}}

@router.get("/positions")
async def get_positions(trading_engine = Depends(get_trading_engine)):
    """Get current positions"""
    try:
        if not trading_engine.bybit_client:
            raise HTTPException(status_code=503, detail="Bybit client not initialized")
        
        positions = trading_engine.bybit_client.get_positions()
        if positions is None:
            positions = []
        
        return {"positions": positions}
    except Exception as e:
        logger.error(f"Error getting positions: {e}")
        return {"positions": []}

@router.post("/order")
async def place_order(order: OrderRequest, trading_engine = Depends(get_trading_engine)):
    """Place a new order"""
    try:
        if not trading_engine.bybit_client:
            raise HTTPException(status_code=503, detail="Bybit client not initialized")
        
        result = trading_engine.bybit_client.place_order(
            symbol=order.symbol,
            side=order.side,
            order_type=order.order_type,
            quantity=order.quantity,
            price=order.price
        )
        
        if result is None:
            raise HTTPException(status_code=400, detail="Order placement failed")
        
        return result
    except Exception as e:
        logger.error(f"Error placing order: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/signals")
async def get_all_signals(trading_engine = Depends(get_trading_engine)):
    """Get trading signals for all symbols"""
    try:
        if not trading_engine.strategy_manager:
            raise HTTPException(status_code=503, detail="Strategy manager not initialized")
        
        # Получаем текущий режим и его конфигурацию
        current_mode = trading_engine.strategy_manager.get_current_mode()
        mode_config = trading_engine.strategy_manager.get_current_config()
        
        # Получаем таймфрейм для текущего режима
        timeframe = mode_config.timeframes[0] if mode_config.timeframes else "5m"
        
        # Конвертируем таймфрейм в формат API
        timeframe_map = {
            "1m": "1",
            "5m": "5", 
            "15m": "15",
            "30m": "30",
            "1h": "60",
            "4h": "240",
            "1d": "D"
        }
        api_timeframe = timeframe_map.get(timeframe, "5")
        
        logger.info(f"🎯 Получение сигналов для режима: {current_mode.value} ({mode_config.name})")
        logger.info(f"📊 Используемый таймфрейм: {timeframe} → API: {api_timeframe}")
        
        # Получаем детальные сигналы для всех торговых пар
        trading_pairs = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "DOGEUSDT", "XRPUSDT"]
        all_signals = {}
        
        for symbol in trading_pairs:
            try:
                # ✅ ИСПРАВЛЕНИЕ: Используем таймфрейм текущего режима
                detailed_signals = trading_engine.signal_processor.get_detailed_signals(symbol, api_timeframe)
                if detailed_signals:
                    all_signals[symbol] = detailed_signals
                    logger.info(f"✅ Generated detailed signals for {symbol} on {timeframe}: {len(detailed_signals)} indicators")
                else:
                    # Fallback к обычным сигналам с правильным таймфреймом
                    signals = trading_engine.signal_processor.get_signals(symbol, api_timeframe)
                    if signals:
                        all_signals[symbol] = signals
                        logger.info(f"✅ Generated fallback signals for {symbol} on {timeframe}: {len(signals)} indicators")
                    else:
                        all_signals[symbol] = {}
                        logger.warning(f"⚠️ No signals generated for {symbol} on {timeframe}")
            except Exception as e:
                logger.warning(f"Error getting signals for {symbol} on {timeframe}: {e}")
                all_signals[symbol] = {}
        
        return {
            "signals": all_signals,
            "enhanced_features_enabled": True,
            "current_mode": current_mode.value,
            "mode_name": mode_config.name,
            "timeframe": timeframe,
            "api_timeframe": api_timeframe
        }
    except Exception as e:
        logger.error(f"Error getting all signals: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/signals/{symbol}")
async def get_signals(symbol: str, trading_engine = Depends(get_trading_engine)):
    """Get trading signals for a symbol"""
    try:
        if not trading_engine.strategy_manager:
            raise HTTPException(status_code=503, detail="Strategy manager not initialized")
        
        signals = await trading_engine.strategy_manager.get_signals_for_mode(symbol)
        
        return signals
    except Exception as e:
        logger.error(f"Error getting signals for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/modes")
async def get_trading_modes(trading_engine = Depends(get_trading_engine)):
    """Get available trading modes"""
    try:
        if not trading_engine.strategy_manager:
            raise HTTPException(status_code=503, detail="Strategy manager not initialized")
        
        from ..core.trading_mode import TradingMode
        modes = []
        
        for mode in TradingMode:
            mode_params = trading_engine.strategy_manager.get_mode_parameters(mode)
            modes.append(mode_params)
        
        return {"modes": modes}
    except Exception as e:
        logger.error(f"Error getting trading modes: {e}")
        raise HTTPException(status_code=500, detail=str(e))

class TradingModeRequest(BaseModel):
    mode: str

@router.post("/mode")
async def switch_mode(request: TradingModeRequest, trading_engine = Depends(get_trading_engine)):
    """Switch trading mode"""
    try:
        if not trading_engine.strategy_manager:
            raise HTTPException(status_code=503, detail="Strategy manager not initialized")
        
        from ..core.trading_mode import TradingMode
        
        # Find the mode
        target_mode = None
        for tm in TradingMode:
            if tm.value == request.mode:
                target_mode = tm
                break
        
        if target_mode is None:
            raise HTTPException(status_code=400, detail=f"Invalid mode: {request.mode}")
        
        result = await trading_engine.strategy_manager.switch_mode(target_mode)
        
        return result
    except Exception as e:
        logger.error(f"Error switching mode: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/risk-mode")
async def set_risk_mode(request: RiskModeRequest, trading_engine = Depends(get_trading_engine)):
    """Set risk management mode"""
    try:
        if not trading_engine.risk_manager:
            raise HTTPException(status_code=503, detail="Risk manager not initialized")
        
        trading_engine.risk_manager.set_mode(request.risk_mode)
        
        return {"success": True, "risk_mode": request.risk_mode}
    except Exception as e:
        logger.error(f"Error setting risk mode: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/trading")
async def control_trading(request: TradingControlRequest, trading_engine = Depends(get_trading_engine)):
    """Start or stop trading"""
    try:
        if request.action == "start":
            await trading_engine.start_trading()
            return {"success": True, "action": "started"}
        elif request.action == "stop":
            await trading_engine.stop_trading()
            return {"success": True, "action": "stopped"}
        else:
            raise HTTPException(status_code=400, detail="Invalid action")
    except Exception as e:
        logger.error(f"Error controlling trading: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/status")
async def get_bot_status(trading_engine = Depends(get_trading_engine)):
    """Get bot status"""
    try:
        return {
            "is_running": trading_engine.is_running,
            "current_mode": trading_engine.strategy_manager.get_current_mode().value if trading_engine.strategy_manager else "unknown",
            "risk_mode": trading_engine.risk_manager.mode if trading_engine.risk_manager else "unknown",
            "enhanced_features": getattr(trading_engine.strategy_manager, 'use_enhanced_features', False)
        }
    except Exception as e:
        logger.error(f"Error getting bot status: {e}")
        return {"is_running": False, "error": str(e)}

@router.get("/stats")
async def get_statistics(trading_engine = Depends(get_trading_engine)):
    """Get trading statistics"""
    try:
        stats = {}
        
        if trading_engine.strategy_manager:
            stats["mode_stats"] = trading_engine.strategy_manager.get_mode_statistics()
        
        if trading_engine.risk_manager:
            stats["risk_stats"] = trading_engine.risk_manager.get_risk_status()
        
        return stats
    except Exception as e:
        logger.error(f"Error getting statistics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== НОВЫЕ ЭНДПОИНТЫ ДЛЯ УЛУЧШЕННЫХ ФУНКЦИЙ ====================

@router.get("/market-analysis/{symbol}")
async def get_market_analysis(symbol: str, timeframe: str = "5", trading_engine = Depends(get_trading_engine)):
    """Получить анализ рыночных условий для символа"""
    try:
        if not trading_engine.strategy_manager:
            raise HTTPException(status_code=503, detail="Strategy manager not initialized")
        
        if not getattr(trading_engine.strategy_manager, 'use_enhanced_features', False):
            raise HTTPException(status_code=503, detail="Enhanced features are disabled")
        
        # Получаем анализ рынка
        market_analysis = trading_engine.strategy_manager.market_analyzer.analyze_market(symbol, timeframe)
        
        # Добавляем краткое резюме
        summary = trading_engine.strategy_manager.get_market_summary(symbol)
        
        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "analysis": market_analysis,
            "summary": summary
        }
        
    except Exception as e:
        logger.error(f"Error getting market analysis for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/enhanced-signals/{symbol}")
async def get_enhanced_signals(symbol: str, trading_engine = Depends(get_trading_engine)):
    """Получить улучшенные сигналы с весовыми коэффициентами"""
    try:
        if not trading_engine.strategy_manager:
            raise HTTPException(status_code=503, detail="Strategy manager not initialized")
        
        if not getattr(trading_engine.strategy_manager, 'use_enhanced_features', False):
            raise HTTPException(status_code=503, detail="Enhanced features are disabled")
        
        # Получаем улучшенные сигналы
        enhanced_signals = trading_engine.strategy_manager.enhanced_signal_processor.get_enhanced_signals(symbol)
        
        # Добавляем объяснение
        explanation = trading_engine.strategy_manager.enhanced_signal_processor.get_signal_explanation(enhanced_signals)
        
        return {
            "symbol": symbol,
            "enhanced_signals": enhanced_signals,
            "explanation": explanation,
            "should_trade": trading_engine.strategy_manager.enhanced_signal_processor.should_trade_enhanced(enhanced_signals)
        }
        
    except Exception as e:
        logger.error(f"Error getting enhanced signals for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/position-size")
async def calculate_position_size(request: PositionSizeRequest, trading_engine = Depends(get_trading_engine)):
    """Рассчитать размер позиции с учетом рыночных условий"""
    try:
        if not trading_engine.strategy_manager:
            raise HTTPException(status_code=503, detail="Strategy manager not initialized")
        
        if not getattr(trading_engine.strategy_manager, 'use_enhanced_features', False):
            raise HTTPException(status_code=503, detail="Enhanced features are disabled")
        
        # Получаем сигналы для расчета
        signals = await trading_engine.strategy_manager.get_signals_for_mode(request.symbol)
        
        # Рассчитываем размер позиции
        position_info = await trading_engine.strategy_manager.get_enhanced_position_info(
            request.symbol, 
            signals, 
            request.current_price, 
            request.account_balance
        )
        
        return {
            "symbol": request.symbol,
            "current_price": request.current_price,
            "account_balance": request.account_balance,
            "position_info": position_info
        }
        
    except Exception as e:
        logger.error(f"Error calculating position size for {request.symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/trailing-stop")
async def create_trailing_stop(request: TrailingStopRequest, trading_engine = Depends(get_trading_engine)):
    """Создать трейлинг-стоп"""
    try:
        if not settings.trailing_stop_enabled:
            raise HTTPException(status_code=503, detail="Trailing stops are disabled")
        if not trading_engine.strategy_manager:
            raise HTTPException(status_code=503, detail="Strategy manager not initialized")
        
        if not getattr(trading_engine.strategy_manager, 'use_enhanced_features', False):
            raise HTTPException(status_code=503, detail="Enhanced features are disabled")
        
        # Получаем анализ рынка
        market_analysis = trading_engine.strategy_manager.market_analyzer.analyze_market(request.symbol)
        
        # Определяем тип стопа
        from ..core.enhanced_risk_manager import StopLossType
        stop_type_map = {
            "trailing": StopLossType.TRAILING,
            "atr_based": StopLossType.ATR_BASED,
            "percentage": StopLossType.PERCENTAGE
        }
        
        stop_type = stop_type_map.get(request.stop_type, StopLossType.TRAILING)
        
        # Создаем трейлинг-стоп
        trailing_stop = trading_engine.strategy_manager.enhanced_risk_manager.create_trailing_stop(
            request.symbol,
            request.side,
            request.entry_price,
            market_analysis,
            stop_type
        )
        
        return {
            "success": True,
            "trailing_stop": trailing_stop.get_info()
        }
        
    except Exception as e:
        logger.error(f"Error creating trailing stop: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/trailing-stops")
async def get_trailing_stops(trading_engine = Depends(get_trading_engine)):
    """Получить список активных трейлинг-стопов"""
    try:
        if not settings.trailing_stop_enabled:
            raise HTTPException(status_code=503, detail="Trailing stops are disabled")
        if not trading_engine.strategy_manager:
            raise HTTPException(status_code=503, detail="Strategy manager not initialized")
        
        if not getattr(trading_engine.strategy_manager, 'use_enhanced_features', False):
            raise HTTPException(status_code=503, detail="Enhanced features are disabled")
        
        active_stops = trading_engine.strategy_manager.enhanced_risk_manager.get_active_trailing_stops()
        
        return {
            "active_stops": active_stops,
            "count": len(active_stops)
        }
        
    except Exception as e:
        logger.error(f"Error getting trailing stops: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/trailing-stop/{symbol}/{side}")
async def remove_trailing_stop(symbol: str, side: str, trading_engine = Depends(get_trading_engine)):
    """Удалить трейлинг-стоп"""
    try:
        if not settings.trailing_stop_enabled:
            raise HTTPException(status_code=503, detail="Trailing stops are disabled")
        if not trading_engine.strategy_manager:
            raise HTTPException(status_code=503, detail="Strategy manager not initialized")
        
        if not getattr(trading_engine.strategy_manager, 'use_enhanced_features', False):
            raise HTTPException(status_code=503, detail="Enhanced features are disabled")
        
        success = trading_engine.strategy_manager.enhanced_risk_manager.remove_trailing_stop(symbol, side)
        
        if success:
            return {"success": True, "message": f"Trailing stop removed for {symbol} {side}"}
        else:
            raise HTTPException(status_code=404, detail="Trailing stop not found")
        
    except Exception as e:
        logger.error(f"Error removing trailing stop: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/enhanced-features")
async def toggle_enhanced_features(request: EnhancedFeaturesRequest, trading_engine = Depends(get_trading_engine)):
    """Включить/отключить улучшенные функции"""
    try:
        if not trading_engine.strategy_manager:
            raise HTTPException(status_code=503, detail="Strategy manager not initialized")
        
        result = trading_engine.strategy_manager.toggle_enhanced_features(request.enabled)
        
        return result
        
    except Exception as e:
        logger.error(f"Error toggling enhanced features: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/auto-close")
async def get_auto_close_status(pair_watcher = Depends(get_pair_watcher)):
    """Получить статус автозакрытия позиций."""
    if pair_watcher is None:
        raise HTTPException(status_code=503, detail="Pair reversal watcher not initialized")
    return {"enabled": pair_watcher.enabled}

@router.post("/auto-close")
async def toggle_auto_close(request: AutoCloseRequest, pair_watcher = Depends(get_pair_watcher)):
    """Включить или отключить автозакрытие позиций."""
    if pair_watcher is None:
        raise HTTPException(status_code=503, detail="Pair reversal watcher not initialized")
    result = pair_watcher.set_enabled(request.enabled)
    return result

@router.get("/enhanced-stats")
async def get_enhanced_statistics(trading_engine = Depends(get_trading_engine)):
    """Получить расширенную статистику"""
    try:
        if not trading_engine.strategy_manager:
            raise HTTPException(status_code=503, detail="Strategy manager not initialized")
        
        stats = trading_engine.strategy_manager.get_mode_statistics()
        
        # Добавляем дополнительную информацию об улучшенных функциях
        if getattr(trading_engine.strategy_manager, 'use_enhanced_features', False):
            stats["enhanced_features_info"] = {
                "market_analyzer": "active",
                "enhanced_signal_processor": "active",
                "enhanced_risk_manager": "active",
                "trailing_stops_count": len(trading_engine.strategy_manager.enhanced_risk_manager.get_active_trailing_stops())
            }
        
        return stats
        
    except Exception as e:
        logger.error(f"Error getting enhanced statistics: {e}")
        raise HTTPException(status_code=500, detail=str(e)) 

@router.get("/api/signals/btcusdt/1m")
async def get_btcusdt_signals_1m(trading_engine = Depends(get_trading_engine)):
    """
    Получить detailed_signals для BTCUSDT по минутному таймфрейму (1m) + BB
    """
    if not trading_engine:
        raise HTTPException(status_code=500, detail="Trading engine not initialized")
    try:
        symbol = "BTCUSDT"
        timeframe = "1"  # 1m
        detailed_signals = trading_engine.signal_processor.get_detailed_signals(symbol, timeframe)
        # Добавляем BB
        df = trading_engine.bybit_client.get_kline(symbol, timeframe, limit=200)
        if df is not None and not df.empty:
            from backend.core.pair_reversal_watcher import PairReversalWatcher
            upper_bb, lower_bb = PairReversalWatcher.calc_bollinger_bands(df['close'])
            detailed_signals['BB_upper'] = {"value": f"{upper_bb.iloc[-1]:.2f}", "signal": "BB_upper"}
            detailed_signals['BB_lower'] = {"value": f"{lower_bb.iloc[-1]:.2f}", "signal": "BB_lower"}
        return {"symbol": symbol, "timeframe": "1m", "signals": detailed_signals}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) 

@router.get("/api/trade-history")
async def get_trade_history(symbol: str = "", limit: int = 50, trading_engine = Depends(get_trading_engine)):
    """
    Получить историю исполненных сделок (trade history, fills) через Bybit API
    """
    try:
        if not trading_engine.bybit_client:
            raise HTTPException(status_code=503, detail="Bybit client not initialized")
        trades = trading_engine.bybit_client.get_trade_history(symbol=symbol, limit=limit)
        return {"symbol": symbol, "trades": trades or []}
    except Exception as e:
        logger.error(f"Error getting trade history: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/closed-pnl")
async def get_closed_pnl(symbol: str = "", limit: int = 50, trading_engine = Depends(get_trading_engine)):
    """
    Получить историю закрытых позиций (PNL history) через Bybit API
    """
    try:
        if not trading_engine.bybit_client:
            raise HTTPException(status_code=503, detail="Bybit client not initialized")
        closed = trading_engine.bybit_client.get_closed_pnl(symbol=symbol, limit=limit)
        return {"symbol": symbol, "closed": closed or []}
    except Exception as e:
        logger.error(f"Error getting closed pnl: {e}")
        raise HTTPException(status_code=500, detail=str(e)) 

from backend.core.trade_analyzer import TradeAnalyzer

@router.get("/api/trade-analysis")
async def get_trade_analysis(symbol: str = "", limit: int = 50, trading_engine = Depends(get_trading_engine)):
    """
    Получить summary-анализ истории закрытых позиций через TradeAnalyzer
    """
    try:
        if not trading_engine.bybit_client:
            raise HTTPException(status_code=503, detail="Bybit client not initialized")
        closed = trading_engine.bybit_client.get_closed_pnl(symbol=symbol, limit=limit)
        analyzer = TradeAnalyzer(closed=closed)
        summary = analyzer.summary()
        return {"symbol": symbol, "summary": summary}
    except Exception as e:
        logger.error(f"Error in trade analysis: {e}")
        raise HTTPException(status_code=500, detail=str(e)) 

from backend.core.auto_param_adjuster import adjust_params

@router.post("/api/auto-adjust-params")
async def auto_adjust_params(symbol: str = "", limit: int = 50, trading_engine = Depends(get_trading_engine)):
    """
    Автоматически скорректировать параметры торговли на основе анализа истории сделок
    """
    try:
        if not trading_engine.bybit_client:
            raise HTTPException(status_code=503, detail="Bybit client not initialized")
        closed = trading_engine.bybit_client.get_closed_pnl(symbol=symbol, limit=limit)
        from backend.core.trade_analyzer import TradeAnalyzer
        analyzer = TradeAnalyzer(closed=closed)
        summary = analyzer.summary()
        # Получаем текущие параметры (пример: из strategy_manager)
        current_params = getattr(trading_engine.strategy_manager, 'current_params', {
            'position_size': 1.0,
            'take_profit': 0.03,
            'stop_loss': 0.01
        })
        new_params, log = adjust_params(summary, current_params)
        # (Опционально) применить новые параметры к strategy_manager
        # trading_engine.strategy_manager.current_params = new_params
        return {
            "symbol": symbol,
            "old_params": current_params,
            "new_params": new_params,
            "log": log,
            "summary": summary
        }
    except Exception as e:
        logger.error(f"Error in auto adjust params: {e}")
        raise HTTPException(status_code=500, detail=str(e)) 

import os

@router.get("/api/param-adjust-log")
async def get_param_adjust_log(limit: int = 20):
    """
    Получить последние записи истории изменений параметров
    """
    log_file = os.path.join("logs", "param_adjustments.log")
    if not os.path.exists(log_file):
        return {"log": []}
    with open(log_file, "r", encoding="utf-8") as f:
        lines = f.readlines()
    # Разбиваем по разделителю ---
    entries = "".join(lines).split("---\n")
    entries = [e.strip() for e in entries if e.strip()]
    return {"log": entries[-limit:]} 

@router.get("/api/export-closed-pnl")
async def export_closed_pnl(symbol: str = "", limit: int = 1000, trading_engine = Depends(get_trading_engine)):
    """
    Экспорт истории закрытых сделок в CSV для ML/AI анализа
    """
    try:
        if not trading_engine.bybit_client:
            raise HTTPException(status_code=503, detail="Bybit client not initialized")
        closed = trading_engine.bybit_client.get_closed_pnl(symbol=symbol, limit=limit) or []
        if not closed:
            raise HTTPException(status_code=404, detail="No closed trades found")
        # Определяем поля для экспорта
        fields = list({k for trade in closed for k in trade.keys()})
        def iter_csv():
            yield ','.join(fields) + '\n'
            for trade in closed:
                row = [str(trade.get(f, '')) for f in fields]
                yield ','.join(row) + '\n'
        filename = f"closed_pnl_{symbol or 'all'}.csv"
        return StreamingResponse(iter_csv(), media_type="text/csv", headers={"Content-Disposition": f"attachment; filename={filename}"})
    except Exception as e:
        logger.error(f"Error exporting closed pnl: {e}")
        raise HTTPException(status_code=500, detail=str(e)) 