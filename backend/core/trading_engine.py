"""
Trading Engine - Main trading logic for Bybit Trading Bot
Orchestrates signal processing, risk management, and order execution
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
import pandas as pd
import math
from decimal import Decimal, ROUND_DOWN

from .signal_processor import SignalProcessor
from .risk_manager import RiskManager
from .strategy_manager import StrategyManager
from .trading_mode import TradingMode, get_mode_config
from ..integrations.bybit_client import BybitClient
from ..utils.config import settings, get_risk_config

# Настройка логгера
logger = logging.getLogger("backend.core.trading_engine")

class TradingEngine:
    """
    Main trading engine that coordinates all trading activities
    """
    
    def __init__(self, bybit_client: Optional[BybitClient] = None, signal_processor: Optional[SignalProcessor] = None, risk_manager: Optional[RiskManager] = None):
        self.signal_processor = signal_processor or SignalProcessor()
        self.risk_manager = risk_manager or RiskManager()
        self.strategy_manager = StrategyManager(self.signal_processor)
        self.bybit_client = bybit_client
        
        # Trading state
        self.is_running = False
        self.start_time = None
        self.active_positions = {}
        self.trading_pairs = settings.trading_pairs
        
        # Performance tracking
        self.total_trades = 0
        self.winning_trades = 0
        self.total_pnl = 0.0
        
        # Таблица точности лота для популярных пар
        self.LOT_PRECISION = {
            "BTCUSDT": 3,
            "ETHUSDT": 3,
            "SOLUSDT": 2,
            "DOGEUSDT": 0,
            "XRPUSDT": 0,
            "BNBUSDT": 2,
            # Добавьте другие пары по необходимости
        }
        
        # Таблица шага лота (lot size) для популярных пар
        self.LOT_SIZE = {
            "BTCUSDT": 0.001,
            "ETHUSDT": 0.001,
            "SOLUSDT": 0.01,
            "DOGEUSDT": 1,
            "XRPUSDT": 1,
            "BNBUSDT": 0.01,
            # Добавьте другие пары по необходимости
        }
        
    async def initialize(self):
        """Initialize the trading engine"""
        try:
            logger.info("🔧 Initializing Trading Engine...")
            
            # Initialize Bybit client
            self.bybit_client = BybitClient(
                api_key=settings.bybit_api_key,
                api_secret=settings.bybit_api_secret,
                testnet=settings.bybit_testnet
            )
            
            success = await self.bybit_client.initialize()
            if not success:
                raise Exception("Failed to initialize Bybit client")
            
            # Initialize risk manager
            await self.risk_manager.initialize()
            
            logger.info("✅ Trading Engine initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error initializing Trading Engine: {e}")
            return False
    
    async def start(self):
        """Start the trading engine"""
        if self.is_running:
            logger.warning("⚠️ Trading engine is already running")
            return
        
        self.is_running = True
        self.start_time = datetime.now()
        logger.info("🚀 Trading engine started")
        
        # Запускаем основной торговый цикл в фоне
        asyncio.create_task(self._main_trading_loop())
    
    def stop(self):
        """Stop the trading engine"""
        logger.info("🛑 Stopping trading engine...")
        self.is_running = False
        self.start_time = None
    
    async def _main_trading_loop(self):
        """Main trading loop that processes signals and executes trades"""
        current_mode = self.strategy_manager.get_current_mode()
        mode_config = self.strategy_manager.get_mode_parameters(current_mode)
        timeframe = mode_config.get('timeframes', ['5m'])[0] if mode_config and 'timeframes' in mode_config and mode_config['timeframes'] else "5m"
        trading_pairs = mode_config.get('trading_pairs', self.trading_pairs) if mode_config and 'trading_pairs' in mode_config else self.trading_pairs
        logger.info(f"📊 Trading loop started - Mode: {current_mode.value}, Timeframe: {timeframe}")
        logger.info(f"📊 Trading pairs: {trading_pairs}")
        while self.is_running:
            try:
                logger.info(f"🔄 [LOOP] Current trading pairs: {trading_pairs}")
                for symbol in trading_pairs:
                    bybit_symbol = symbol.replace("/", "")
                    await self._process_symbol(bybit_symbol, timeframe)
                wait_time = 15 if current_mode.value == "aggressive" else 30
                await asyncio.sleep(wait_time)
            except Exception as e:
                logger.error(f"❌ Error in trading loop iteration: {e}")
                await asyncio.sleep(60)
    
    async def _process_symbol(self, symbol: str, timeframe: str):
        """Process trading signals for a specific symbol"""
        try:
            # Get market data
            market_data = self.bybit_client.get_kline(
                symbol=symbol,
                interval=timeframe,
                limit=200
            )
            
            if market_data is None or len(market_data) < 50:
                logger.warning(f"Недостаточно данных для {symbol}")
                return
            
            # Process technical signals
            signals = self.signal_processor.get_signals(symbol, timeframe)
            signal_strength = self.signal_processor.get_signal_strength(signals)

            # Формируем человекочитаемый лог для веба
            web_log = self.format_signal_log_for_web(symbol, signals, signal_strength)
            from backend.main import manager
            import asyncio
            if len(manager.active_connections) > 0:
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        asyncio.create_task(manager.broadcast(f'{web_log}'))
                except Exception:
                    pass

            # Старый лог для backend
            logger.info(f"{symbol}: Buy: {signal_strength['BUY']}, Sell: {signal_strength['SELL']}, Hold: {signal_strength['HOLD']}")

            # Check if we should trade
            # ✅ ИСПРАВЛЕНИЕ: Адаптивное количество подтверждений для разных режимов
            current_mode = self.strategy_manager.get_current_mode()
            
            # Агрессивный режим требует меньше подтверждений для быстрой торговли
            if current_mode.value == "aggressive":
                min_confirmation = 3  # Для скальпинга нужно быстро реагировать
            elif current_mode.value == "medium":
                min_confirmation = 4  # Средний баланс между скоростью и надежностью
            else:  # conservative
                min_confirmation = 6  # Консервативно - больше подтверждений
            
            trading_decision = self.signal_processor.should_trade(
                signals, 
                min_confirmation=min_confirmation
            )
            
            if trading_decision:
                await self._execute_trade(symbol, trading_decision, market_data)
            
        except Exception as e:
            logger.error(f"Ошибка обработки {symbol}: {e}")

    def format_signal_log_for_web(self, symbol: str, signals: dict, signal_strength: dict) -> str:
        """
        Формирует строку для веб-логов: сначала расшифровка индикаторов, потом итоговая строка
        """
        buy = []
        sell = []
        hold = []
        for ind, sig in signals.items():
            if sig == "BUY":
                buy.append(ind)
            elif sig == "SELL":
                sell.append(ind)
            else:
                hold.append(ind)
        parts = []
        if buy:
            parts.append(f"Buy: {', '.join(buy)}")
        if sell:
            parts.append(f"Sell: {', '.join(sell)}")
        if hold:
            parts.append(f"Hold: {', '.join(hold)}")
        details = "; ".join(parts)
        summary = f"{symbol}: {signal_strength['BUY']} buy, {signal_strength['SELL']} sell, {signal_strength['HOLD']} hold"
        return f"{details}\n{summary}"
    
    def calc_tp_sl(self, entry_price, side, mode):
        logger.info(f"[TP/SL] entry_price={entry_price}, side={side}, mode={mode}")
        
        # Исправление: если режим moderate, заменяем на medium
        if mode == "moderate":
            logger.warning("[TP/SL] Режим 'moderate' заменён на 'medium'")
            mode = "medium"
        
        # ✅ ИСПРАВЛЕНИЕ: Более консервативные параметры TP/SL
        params = {
            'aggressive': {'sl': 0.02, 'tp': 0.03},    # 2% SL, 3% TP
            'medium':     {'sl': 0.015, 'tp': 0.025},  # 1.5% SL, 2.5% TP  
            'conservative': {'sl': 0.01, 'tp': 0.02}   # 1% SL, 2% TP
        }
        
        if mode not in params:
            logger.error(f"Неизвестный режим торговли: {mode}")
            return None, None
        
        sl_pct = params[mode]['sl']
        tp_pct = params[mode]['tp']
        
        # ✅ ИСПРАВЛЕНИЕ: Правильный расчет TP/SL с учетом направления
        if side.lower() in ['buy', 'long']:
            # Для покупки: SL ниже входной цены, TP выше
            stop_loss = entry_price * (1 - sl_pct)
            take_profit = entry_price * (1 + tp_pct)
        else:
            # Для продажи: SL выше входной цены, TP ниже
            stop_loss = entry_price * (1 + sl_pct)
            take_profit = entry_price * (1 - tp_pct)
        
        # ✅ ИСПРАВЛЕНИЕ: Проверяем разумность цен
        if side.lower() in ['buy', 'long']:
            if stop_loss >= entry_price:
                logger.error(f"❌ Неправильный SL для покупки: {stop_loss} >= {entry_price}")
                return None, None
            if take_profit <= entry_price:
                logger.error(f"❌ Неправильный TP для покупки: {take_profit} <= {entry_price}")
                return None, None
        else:
            if stop_loss <= entry_price:
                logger.error(f"❌ Неправильный SL для продажи: {stop_loss} <= {entry_price}")
                return None, None
            if take_profit >= entry_price:
                logger.error(f"❌ Неправильный TP для продажи: {take_profit} >= {entry_price}")
                return None, None
        
        logger.info(f"[TP/SL] Calculated: SL={stop_loss:.4f}, TP={take_profit:.4f}")
        return round(stop_loss, 4), round(take_profit, 4)
    
    def round_qty(self, symbol, qty):
        precision = self.LOT_PRECISION.get(symbol, 3)
        if precision == 0:
            return int(qty)
        return round(qty, precision)

    def adjust_qty(self, symbol, qty):
        import math
        lot_size = self.LOT_SIZE.get(symbol, 0.01)
        qty = abs(qty)
        qty_adjusted = math.ceil(qty / lot_size) * lot_size
        if qty_adjusted < lot_size:
            qty_adjusted = lot_size
        if lot_size >= 1:
            qty_adjusted = int(qty_adjusted)
        return qty_adjusted

    def format_qty_for_bybit(self, symbol: str, qty: float, price: float = None) -> str:
        """
        Форматирует qty для Bybit: кратен lot_size, не меньше lot_size, форматируется по LOT_PRECISION, убирает лишние нули/точку, всегда строка.
        
        Добавлена строгая валидация: qty округляется до нужной точности, проверяется кратность lot_size.
        """
        from decimal import Decimal, ROUND_DOWN
        lot_size = Decimal(str(self.LOT_SIZE.get(symbol, 0.01)))
        precision = self.LOT_PRECISION.get(symbol, 3)
        qty_orig = qty
        qty = Decimal(str(qty))
        logger.info(f"[format_qty_for_bybit] symbol={symbol}, qty_in={qty_orig}, lot_size={lot_size}, precision={precision}, price={price}")
        
        # qty не может быть меньше lot_size
        if qty < lot_size:
            logger.info(f"[format_qty_for_bybit] qty < lot_size: {qty} < {lot_size}, set to lot_size")
            qty = lot_size
        
        # qty обязательно кратен lot_size (до precision знаков)
        if lot_size > 0:
            qty = (qty // lot_size) * lot_size
        
        logger.info(f"[format_qty_for_bybit] qty after lot_size rounding: {qty}")
        
        # ✅ ИСПРАВЛЕНИЕ: Проверяем минимальную сумму ордера (5 USDT)
        if price is not None and price > 0:
            min_qty = (Decimal('5') / Decimal(str(price))).quantize(lot_size, rounding=ROUND_DOWN)
            logger.info(f"[format_qty_for_bybit] min_qty for 5 USDT: {min_qty}")
            if qty < min_qty:
                # Увеличиваем до минимального количества
                qty = ((min_qty // lot_size) + 1) * lot_size
                logger.info(f"[format_qty_for_bybit] qty increased to meet 5 USDT minimum: {qty}")
        
        # ✅ ИСПРАВЛЕНИЕ: Дополнительная проверка для ETHUSDT (минимум 0.1)
        if symbol == "ETHUSDT" and qty < Decimal('0.1'):
            qty = Decimal('0.1')
            logger.info(f"[format_qty_for_bybit] ETHUSDT minimum qty set to 0.1")
        
        # Проверка кратности lot_size
        remainder = (qty / lot_size) % 1
        logger.info(f"[format_qty_for_bybit] qty/lot_size={qty/lot_size}, remainder={remainder}")
        if remainder != 0:
            logger.warning(f"[format_qty_for_bybit] WARNING: qty={qty} не кратен lot_size={lot_size} (remainder={remainder}) — Bybit не примет!")
        
        # Форматируем результат
        qty_str = f"{qty:.{precision}f}".rstrip('0').rstrip('.')
        logger.info(f"[format_qty_for_bybit] qty_str result: {qty_str}, qty*price={qty*Decimal(str(price or 1)):.5f}")
        return qty_str

    def get_mode(self):
        """Возвращает текущий режим торговли (строка)"""
        if hasattr(self.risk_manager, 'mode'):
            return self.risk_manager.mode
        return 'medium'

    def set_mode(self, mode):
        """Устанавливает режим торговли"""
        if hasattr(self.risk_manager, 'mode'):
            self.risk_manager.mode = mode
        # Можно добавить сохранение в настройки, если нужно

    async def _execute_trade(self, symbol: str, decision: str, market_data: pd.DataFrame):
        """Execute a trade based on the signal"""
        try:
            await self.sync_positions_with_exchange()
            current_price = market_data['close'].iloc[-1]
            current_mode = self.strategy_manager.get_current_mode()
            mode_config = self.strategy_manager.get_mode_parameters(current_mode)
            if symbol in self.active_positions:
                logger.warning(f"⚠️ Already have position in {symbol}")
                return
            min_position_value = 100
            leverage = 1
            if 'leverage_range' in mode_config and isinstance(mode_config['leverage_range'], tuple):
                leverage = float(mode_config['leverage_range'][1])
            qty = min_position_value / (current_price * leverage)
            qty = max(qty, 0.001)
            min_qty = math.ceil(5 / float(current_price) * 1000) / 1000
            if qty * current_price < 5:
                logger.info(f"🔄 [min_qty] Increasing qty for {symbol}: {qty} → {min_qty} (to meet minimum order value >= 5 USDT)")
                qty = min_qty
            # Округляем qty по шагу лота
            qty_final = self.adjust_qty(symbol, qty)
            # Для логирования форматируем qty как строку с нужной точностью
            if self.LOT_SIZE.get(symbol, 0.01) >= 1:
                qty_str = str(int(qty_final))
            else:
                precision = 3 if self.LOT_SIZE.get(symbol, 0.01) == 0.001 else 2
                qty_str = f"{qty_final:.{precision}f}"
            logger.info(f"🔢 [lot_size] Итоговое qty для {symbol}: {qty_str} (lot_size={self.LOT_SIZE.get(symbol, 1)})")
            side = "Buy" if decision == "BUY" else "Sell"
            # Для market order передаем текущую цену, чтобы избежать ошибок типов
            order_price = current_price if "market" else None
            order_result = await self.place_order(
                symbol=symbol,
                side=side,
                amount=qty_final,
                order_type="market",
                price=current_price
            )
            if order_result and order_result.get('success'):
                order_id = order_result.get('order_id', None)
                self.active_positions[symbol] = {
                    "order_id": order_id,
                    "side": side,
                    "size": order_result.get('amount', qty_final),
                    "entry_price": current_price,
                    "stop_loss": None,
                    "take_profit": None,
                    "timestamp": datetime.now(),
                    "mode": current_mode.value
                }
                self.total_trades += 1
                logger.info(f"✅ Order placed successfully: {order_id}")
            else:
                error_msg = order_result.get('error', 'Unknown error') if order_result else 'No response'
                logger.error(f"❌ Failed to place order: {error_msg}")
            await self.sync_positions_with_exchange()
        except Exception as e:
            logger.error(f"❌ Error executing trade for {symbol}: {e}")
    
    def calc_tp_sl_from_mode(self, entry_price: float, side: str, mode_config) -> tuple:
        """Calculate TP/SL based on mode configuration"""
        try:
            # ✅ ИСПРАВЛЕНИЕ: mode_config - это словарь, не объект
            # Получаем диапазоны TP/SL из словаря
            tp_range = mode_config.get('tp_range', {'min': 0.5, 'max': 1.0})
            sl_range = mode_config.get('sl_range', {'min': 0.3, 'max': 0.7})
            
            # Используем минимальные значения из диапазона для агрессивного режима
            tp_pct = tp_range['min'] / 100  # Минимальный TP для быстрого закрытия
            sl_pct = sl_range['min'] / 100  # Минимальный SL для агрессивного режима
            
            if side.lower() in ['buy', 'long']:
                stop_loss = entry_price * (1 - sl_pct)
                take_profit = entry_price * (1 + tp_pct)
            else:
                stop_loss = entry_price * (1 + sl_pct)
                take_profit = entry_price * (1 - tp_pct)
                
            return round(stop_loss, 4), round(take_profit, 4)
            
        except Exception as e:
            logger.error(f"Error calculating TP/SL: {e}")
            return None, None
    
    async def place_order(self, symbol: str, side: str, amount: float, order_type: str = "market", price: float = None) -> Dict:
        """
        Публичный метод для выставления ордера через торговый движок
        
        Args:
            symbol: Торговая пара (например, BTCUSDT)
            side: Направление ("buy" или "sell")
            amount: Размер ордера
            order_type: Тип ордера ("market" или "limit")
            price: Цена для лимитного ордера
            
        Returns:
            Dict с результатом операции
        """
        logger.info(f"📝 Выставление ордера: {side.upper()} {amount} {symbol} ({order_type})")
        
        try:
            if not self.bybit_client:
                return {"success": False, "error": "Bybit client not initialized"}
            
            # Проверяем корректность параметров
            if side.lower() not in ['buy', 'sell']:
                return {"success": False, "error": f"Invalid side: {side}"}
            
            if amount <= 0:
                return {"success": False, "error": f"Invalid amount: {amount}"}
            
            # Логируем параметры ордера
            logger.info(f"🎯 Параметры ордера:")
            logger.info(f"   Символ: {symbol}")
            logger.info(f"   Направление: {side.upper()}")
            logger.info(f"   Количество: {amount}")
            logger.info(f"   Тип: {order_type}")
            if price:
                logger.info(f"   Цена: {price}")
            
            # Получаем текущую цену для расчёта TP/SL и проверки суммы
            current_price = price if price else self.bybit_client.get_current_price(symbol)
            if current_price is None:
                logger.error(f"❌ Не удалось получить цену для {symbol}, ордер не будет выставлен!")
                return {"success": False, "error": "Не удалось получить цену для расчёта суммы ордера"}
            # Получаем параметры режима для расчёта плеча
            mode = self.risk_manager.mode if hasattr(self.risk_manager, 'mode') else 'medium'
            try:
                mode_enum = TradingMode(mode)
            except Exception:
                mode_enum = TradingMode.MEDIUM
            mode_config = get_mode_config(mode_enum)
            leverage = 1
            if hasattr(mode_config, 'leverage_range') and isinstance(mode_config.leverage_range, tuple):
                leverage = float(mode_config.leverage_range[1])
            # Проверка минимальной суммы ордера (Bybit требует >= 5 USDT на заявку)
            min_qty = math.ceil(5 / float(current_price) * 1000) / 1000
            if amount < min_qty:
                logger.info(f"🔄 [min_qty] Increasing qty for {symbol}: {amount} → {min_qty} (to meet minimum order value >= 5 USDT)")
                amount = min_qty
            min_order_value = float(amount) * float(current_price)
            if min_order_value < 5:
                logger.warning(f"⚠️ Сумма ордера {min_order_value:.2f} USDT меньше минимальной 5 USDT (Bybit). Ордер не отправлен.")
                return {"success": False, "error": f"Сумма ордера {min_order_value:.2f} USDT меньше минимальной 5 USDT (Bybit)"}
            # Проверка минимальной суммы позиции с учетом плеча (стратегия)
            order_value = float(amount) * float(current_price) * leverage
            if order_value < 100:
                logger.warning(f"⚠️ Сумма позиции с учетом плеча {order_value:.2f} USDT меньше минимальной 100 USDT. Ордер не отправлен.")
                return {"success": False, "error": f"Сумма позиции с учетом плеча {order_value:.2f} USDT меньше минимальной 100 USDT"}
            # Проверка маржи (баланса)
            margin_required = float(amount) * float(current_price) / leverage
            balance = self.bybit_client.get_balance()
            if balance is not None and margin_required > float(balance):
                logger.warning(f"⚠️ Недостаточно средств: требуется маржа {margin_required:.2f} USDT, доступно {balance:.2f} USDT. Ордер не отправлен.")
                return {"success": False, "error": f"Недостаточно средств: требуется маржа {margin_required:.2f} USDT, доступно {balance:.2f} USDT"}
            mode = self.risk_manager.mode if hasattr(self.risk_manager, 'mode') else 'medium'
            stop_loss, take_profit = self.calc_tp_sl(current_price, side, mode)
            if stop_loss is None or take_profit is None:
                logger.error(f"❌ Не удалось рассчитать TP/SL для {symbol}, ордер не будет выставлен!")
                return {"success": False, "error": "Не удалось рассчитать TP/SL"}
            # --- Новый блок: попытки выставления ордера с увеличением qty при ошибке 110007 ---
            max_attempts = 3
            attempt = 0
            max_qty = 1000  # лимит для qty, чтобы не уйти в абсурд
            while attempt < max_attempts:
                logger.info(f"🎯 [Попытка {attempt+1}] Executing {side} order for {amount} {symbol} at {current_price}")
                qty_final = self.adjust_qty(symbol, amount)
                qty_str = self.format_qty_for_bybit(symbol, qty_final, price=current_price)
                lot_size = self.LOT_SIZE.get(symbol, 0.01)
                precision = self.LOT_PRECISION.get(symbol, 3)
                logger.info(f"🔢 [lot_size] Итоговое qty для {symbol}: {qty_str} (lot_size={lot_size}, precision={precision})")
                order_kwargs = dict(
                    symbol=symbol,
                    side=side.capitalize(),
                    order_type=order_type.capitalize(),
                    qty=qty_str,  # qty всегда строка с нужной точностью
                    stop_loss=float(stop_loss) if stop_loss is not None else None,
                    take_profit=float(take_profit) if take_profit is not None else None
                )
                if order_type.lower() == "limit" and price is not None:
                    order_kwargs["price"] = float(price)
                order_kwargs = {k: v for k, v in order_kwargs.items() if v is not None}
                logger.info(f"[place_order] Параметры для bybit_client.place_order: {order_kwargs}")
                logger.info(f"[place_order] type(qty_str)={type(qty_str)}, repr(qty_str)={repr(qty_str)}")
                logger.info(f"[place_order] Полный запрос: {order_kwargs}")
                order_result = await self.bybit_client.place_order(**order_kwargs)
                logger.info(f"[place_order] Ответ bybit_client.place_order: {order_result}")
                if order_result and order_result.get('retCode') == 0:
                    order_id = order_result.get('result', {}).get('orderId')
                    logger.info(f"✅ Ордер успешно выставлен! ID: {order_id}")
                    self.total_trades += 1
                    await self.sync_positions_with_exchange()
                    return {
                        "success": True,
                        "order_id": order_id,
                        "symbol": symbol,
                        "side": side,
                        "amount": amount,
                        "type": order_type,
                        "result": order_result
                    }
                else:
                    error_msg = order_result.get('retMsg', 'Unknown error') if order_result else 'No response'
                    logger.error(f"❌ Ошибка выставления ордера: {error_msg}")
                    # Если ошибка 110007 — увеличиваем qty и пробуем ещё раз
                    if order_result and ("110007" in str(order_result.get('retMsg', '')) or "ab not enough for new order" in str(order_result.get('retMsg', ''))):
                        new_amount = round(amount * 2, 3)
                        if new_amount > max_qty:
                            logger.error(f"❌ [110007] Достигнут лимит qty ({new_amount}), дальнейшие попытки невозможны.")
                            return {"success": False, "error": f"Достигнут лимит qty ({new_amount}), дальнейшие попытки невозможны.", "result": order_result}
                        logger.warning(f"🔄 [110007] Увеличиваем qty {amount} → {new_amount} и повторяем попытку...")
                        amount = new_amount
                        attempt += 1
                        continue
                    # Если другая ошибка — не повторяем
                    return {"success": False, "error": error_msg, "result": order_result}
            # Если не удалось после всех попыток
            logger.error(f"❌ Не удалось выставить ордер после увеличения qty. Последнее qty: {amount}")
            return {"success": False, "error": "Не удалось выставить ордер после увеличения qty", "result": None}
        except Exception as e:
            logger.error(f"❌ Исключение при выставлении ордера: {e}")
            return {"success": False, "error": str(e)}

    async def get_trading_status(self) -> Dict:
        """Get current trading status"""
        return {
            "is_running": self.is_running,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "win_rate": (self.winning_trades / self.total_trades * 100) if self.total_trades > 0 else 0,
            "total_pnl": self.total_pnl,
            "active_positions": len(self.active_positions),
            "trading_pairs": self.trading_pairs
        }
    
    async def get_active_positions(self) -> Dict:
        """Get active trading positions"""
        return self.active_positions
    
    async def close_position(self, symbol: str) -> bool:
        """Close a specific position"""
        if symbol not in self.active_positions:
            logger.warning(f"⚠️ No active position for {symbol}")
            return False
        
        try:
            position = self.active_positions[symbol]
            
            # Determine opposite side for closing
            close_side = "Sell" if position["side"] == "Buy" else "Buy"
            
            # Place closing order
            lot_size = self.LOT_SIZE.get(symbol, 0.01)
            qty_final = self.adjust_qty(symbol, position["size"])
            qty_str = self.format_qty_for_bybit(symbol, qty_final)
            logger.info(f"🔢 [lot_size] Закрытие позиции {symbol}: qty={qty_str} (lot_size={lot_size})")
            order_kwargs = dict(
                symbol=symbol,
                side=close_side,
                order_type="Market",
                qty=qty_str
            )
            order_result = await self.bybit_client.place_order(**order_kwargs)
            
            if order_result:
                # Remove from active positions
                del self.active_positions[symbol]
                logger.info(f"✅ Position closed for {symbol}")
                
                await self.sync_positions_with_exchange()  # Синхронизация после попытки
                
                return True
            
        except Exception as e:
            logger.error(f"❌ Error closing position for {symbol}: {e}")
        
        return False
    
    async def shutdown(self):
        """Shutdown the trading engine gracefully"""
        logger.info("🔄 Shutting down trading engine...")
        
        # Stop trading
        self.stop()
        
        # Close all positions
        for symbol in list(self.active_positions.keys()):
            await self.close_position(symbol)
        
        logger.info("✅ Trading engine shutdown complete")

    async def sync_positions_with_exchange(self):
        """Синхронизировать локальные позиции с реальными на бирже"""
        if not self.bybit_client:
            logger.warning("⚠️ Bybit client не инициализирован, синхронизация невозможна")
            return
        real_positions = self.bybit_client.get_positions() or []
        real_symbols = {p['symbol'] for p in real_positions if p['size'] > 0}
        # Удаляем локальные позиции, которых нет на бирже
        for symbol in list(self.active_positions.keys()):
            if symbol not in real_symbols:
                del self.active_positions[symbol]
        # Добавляем новые, если есть на бирже, а локально нет
        for pos in real_positions:
            if pos['symbol'] not in self.active_positions and pos['size'] > 0:
                self.active_positions[pos['symbol']] = pos