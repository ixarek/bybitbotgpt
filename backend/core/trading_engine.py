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
from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP
import requests

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
        # Теперь ключ — (symbol, side): ("BTCUSDT", "Buy") или ("BTCUSDT", "Sell")
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
                testnet=settings.bybit_testnet,
                demo=settings.bybit_demo
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
        
        # ✅ ИСПРАВЛЕНИЕ: Всегда используем торговые пары из режима, а не из settings
        trading_pairs = mode_config.get('trading_pairs', self.trading_pairs) if mode_config else self.trading_pairs
        
        logger.info(f"📊 Trading loop started - Mode: {current_mode.value}, Timeframe: {timeframe}")
        logger.info(f"📊 Trading pairs from mode config: {trading_pairs}")
        logger.info(f"📊 Settings trading pairs (fallback): {self.trading_pairs}")
        
        while self.is_running:
            try:
                # ✅ ИСПРАВЛЕНИЕ: Сначала корректируем размеры существующих позиций
                logger.info("🔧 [LOOP] Корректируем размеры существующих позиций...")
                await self.sync_positions_with_exchange()
                
                # Затем обрабатываем новые торговые сигналы
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
            # Получаем detailed_signals для ATR силы
            if hasattr(self.signal_processor, 'get_detailed_signals'):
                detailed_signals = self.signal_processor.get_detailed_signals(symbol, timeframe)
                atr_info = detailed_signals.get('ATR', {})
                if 'strength' in atr_info:
                    logger.info(f"[ATR] {symbol} {timeframe}: {atr_info.get('value')} ({atr_info.get('strength')})")

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
    
    def round_position_to_nearest_100(self, symbol: str, qty: float, current_price: float, leverage: float) -> float:
        """
        Округляет размер позиции до диапазона 100$ ± 20$ (80-120$) с учетом плеча
        
        Args:
            symbol: Торговая пара
            qty: Количество актива
            current_price: Текущая цена
            leverage: Плечо
            
        Returns:
            float: Округленное количество актива
        """
        # Рассчитываем текущую стоимость позиции с учетом плеча
        position_value = qty * current_price * leverage
        
        # Округляем до ближайших 100$ с допуском ±20$
        target_value = 100
        min_value = 80  # 100 - 20
        max_value = 120  # 100 + 20
        
        if position_value < min_value:
            # Если меньше 80$, увеличиваем до 100$
            rounded_value = target_value
        elif position_value > max_value:
            # Если больше 120$, уменьшаем до 100$
            rounded_value = target_value
        else:
            # Если в диапазоне 80-120$, оставляем как есть
            rounded_value = position_value
        
        # Рассчитываем новое количество актива
        new_qty = rounded_value / (current_price * leverage)
        
        # Округляем по параметрам биржи
        adjusted_qty = self.adjust_qty(symbol, float(new_qty))
        
        # Проверяем, что итоговая стоимость не меньше 80$
        final_value = adjusted_qty * current_price * leverage
        if final_value < min_value:
            # Если меньше 80$, увеличиваем до минимальных 100$
            min_qty_for_100 = target_value / (current_price * leverage)
            adjusted_qty = self.adjust_qty(symbol, min_qty_for_100)
        
        logger.info(f"🔢 [round_position_to_nearest_100] {symbol}:")
        logger.info(f"   Исходное qty: {qty:.6f}")
        logger.info(f"   Исходная стоимость: {position_value:.2f} USDT")
        logger.info(f"   Диапазон: {min_value}-{max_value} USDT")
        logger.info(f"   Целевая стоимость: {rounded_value:.2f} USDT")
        logger.info(f"   Новое qty: {adjusted_qty:.6f}")
        logger.info(f"   Итоговая стоимость: {adjusted_qty * current_price * leverage:.2f} USDT")
        
        return adjusted_qty

    def calc_tp_sl(self, entry_price, side, mode, market_data=None, symbol=None, timeframe=None):
        logger.info(f"[TP/SL] entry_price={entry_price}, side={side}, mode={mode}")
        
        # Исправление: если режим moderate, заменяем на medium
        if mode == "moderate":
            logger.warning("[TP/SL] Режим 'moderate' заменён на 'medium'")
            mode = "medium"
        
        # ATR-основанный SL для агрессивного режима
        if mode == "aggressive" and market_data is not None:
            try:
                atr_period = 14
                if 'high' in market_data and 'low' in market_data and 'close' in market_data:
                    high = market_data['high']
                    low = market_data['low']
                    close = market_data['close']
                    import numpy as np
                    high_low = high - low
                    high_close = np.abs(high - close.shift())
                    low_close = np.abs(low - close.shift())
                    true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
                    atr = true_range.rolling(window=atr_period).mean().iloc[-1]
                    atr_mult = 1.5
                    if side.lower() in ['buy', 'long']:
                        stop_loss = entry_price - atr * atr_mult
                        take_profit = entry_price * 1.03
                    else:
                        stop_loss = entry_price + atr * atr_mult
                        take_profit = entry_price * 0.97
                    logger.info(f"[TP/SL][ATR] SL={stop_loss:.4f}, TP={take_profit:.4f}, ATR={atr:.4f}")
                    return round(stop_loss, 4), round(take_profit, 4)
            except Exception as e:
                logger.error(f"[TP/SL][ATR] Ошибка расчёта ATR: {e}")
        # ATR-основанный SL/TP для консервативного режима
        if mode == "conservative" and market_data is not None:
            try:
                atr_period = 14
                if 'high' in market_data and 'low' in market_data and 'close' in market_data:
                    high = market_data['high']
                    low = market_data['low']
                    close = market_data['close']
                    import numpy as np
                    high_low = high - low
                    high_close = np.abs(high - close.shift())
                    low_close = np.abs(low - close.shift())
                    true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
                    atr = true_range.rolling(window=atr_period).mean().iloc[-1]
                    # Диапазоны SL/TP
                    min_sl, max_sl = 0.01, 0.03
                    min_tp, max_tp = 0.02, 0.05
                    # ATR нормируем относительно цены (процент волатильности)
                    atr_pct = atr / entry_price
                    # Чем выше ATR, тем ближе к max_sl/max_tp
                    # ATR < 1% — min, ATR >= 3% — max, между — линейная интерполяция
                    atr_min, atr_max = 0.01, 0.03
                    k = min(1.0, max(0.0, (atr_pct - atr_min) / (atr_max - atr_min)))
                    sl_pct = min_sl + (max_sl - min_sl) * k
                    tp_pct = min_tp + (max_tp - min_tp) * k
                    if side.lower() in ['buy', 'long']:
                        stop_loss = entry_price * (1 - sl_pct)
                        take_profit = entry_price * (1 + tp_pct)
                    else:
                        stop_loss = entry_price * (1 + sl_pct)
                        take_profit = entry_price * (1 - tp_pct)
                    logger.info(f"[TP/SL][ATR_CONS] SL={stop_loss:.4f}, TP={take_profit:.4f}, ATR={atr:.4f}, k={k:.2f}")
                    return round(stop_loss, 4), round(take_profit, 4)
            except Exception as e:
                logger.error(f"[TP/SL][ATR_CONS] Ошибка расчёта ATR: {e}")
        # Старый способ для остальных режимов
        params = {
            'aggressive': {'sl': 0.01, 'tp': 0.03},
            'medium':     {'sl': 0.02, 'tp': 0.04},
            'conservative': {'sl': 0.03, 'tp': 0.05}
        }
        if mode not in params:
            logger.error(f"Неизвестный режим торговли: {mode}")
            return None, None
        sl_pct = params[mode]['sl']
        tp_pct = params[mode]['tp']
        if side.lower() in ['buy', 'long']:
            stop_loss = entry_price * (1 - sl_pct)
            take_profit = entry_price * (1 + tp_pct)
        else:
            stop_loss = entry_price * (1 + sl_pct)
            take_profit = entry_price * (1 - tp_pct)
        # Проверяем разумность цен
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
        from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP
        import requests
        
        qty = abs(qty)
        
        # ✅ ИСПРАВЛЕНИЕ: Получаем актуальные параметры с биржи
        try:
            base_url = self.get_api_base_url() if hasattr(self, 'bybit_client') and self.bybit_client else "https://api-testnet.bybit.com"
            api_url = f"{base_url}/v5/market/instruments-info"
            params = {"category": "linear", "symbol": symbol}
            response = requests.get(api_url, params=params, timeout=5)
            if response.status_code == 200:
                data = response.json()
                if data.get('retCode') == 0 and data.get('result', {}).get('list'):
                    instrument = data['result']['list'][0]
                    lot_size_filter = instrument.get('lotSizeFilter', {})
                    
                    min_order_qty = float(lot_size_filter.get('minOrderQty', '0.1'))
                    qty_step = float(lot_size_filter.get('qtyStep', '0.1'))
                    
                    logger.info(f"[adjust_qty] Получены параметры с биржи: minOrderQty={min_order_qty}, qtyStep={qty_step}")
                else:
                    # Fallback к статическим значениям
                    min_order_qty = 0.1
                    qty_step = 0.1
                    logger.warning(f"[adjust_qty] Не удалось получить параметры с биржи, используем fallback")
            else:
                # Fallback к статическим значениям
                min_order_qty = 0.1
                qty_step = 0.1
                logger.warning(f"[adjust_qty] Ошибка запроса к бирже, используем fallback")
        except Exception as e:
            # Fallback к статическим значениям
            min_order_qty = 0.1
            qty_step = 0.1
            logger.warning(f"[adjust_qty] Исключение при получении параметров: {e}, используем fallback")
        
        # Используем Decimal для точных вычислений
        qty_decimal = Decimal(str(qty))
        qty_step_decimal = Decimal(str(qty_step))
        min_order_qty_decimal = Decimal(str(min_order_qty))
        
        # Округляем до ближайшего кратного qtyStep
        qty_adjusted = (qty_decimal / qty_step_decimal).quantize(Decimal('1'), rounding=ROUND_HALF_UP) * qty_step_decimal
        
        # Минимальное количество не может быть меньше minOrderQty
        if qty_adjusted < min_order_qty_decimal:
            qty_adjusted = min_order_qty_decimal
        
        # Конвертируем обратно в float
        qty_result = float(qty_adjusted)
        
        # Для целых лотов возвращаем int
        if qty_step >= 1:
            qty_result = int(qty_result)
        
        logger.info(f"🔢 [adjust_qty] {symbol}: {qty:.6f} → {qty_result} (qtyStep={qty_step}, minOrderQty={min_order_qty})")
        return qty_result

    def format_qty_for_bybit(self, symbol: str, qty: float, price: float = None) -> str:
        """
        Форматирует qty для Bybit: кратен qtyStep, не меньше minOrderQty, форматируется по LOT_PRECISION, убирает лишние нули/точку, всегда строка.
        
        Добавлена строгая валидация: qty округляется до нужной точности, проверяется кратность qtyStep.
        """
        from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP
        import requests
        
        qty_orig = qty
        qty = Decimal(str(qty))
        logger.info(f"[format_qty_for_bybit] symbol={symbol}, qty_in={qty_orig}, price={price}")
        
        # ✅ ИСПРАВЛЕНИЕ: Получаем актуальные параметры с биржи
        try:
            base_url = self.get_api_base_url() if hasattr(self, 'bybit_client') and self.bybit_client else "https://api-testnet.bybit.com"
            api_url = f"{base_url}/v5/market/instruments-info"
            params = {"category": "linear", "symbol": symbol}
            response = requests.get(api_url, params=params, timeout=5)
            if response.status_code == 200:
                data = response.json()
                if data.get('retCode') == 0 and data.get('result', {}).get('list'):
                    instrument = data['result']['list'][0]
                    lot_size_filter = instrument.get('lotSizeFilter', {})
                    
                    min_order_qty = Decimal(str(lot_size_filter.get('minOrderQty', '0.1')))
                    qty_step = Decimal(str(lot_size_filter.get('qtyStep', '0.1')))
                    min_notional_value = Decimal(str(lot_size_filter.get('minNotionalValue', '5')))
                    
                    logger.info(f"[format_qty_for_bybit] Получены параметры с биржи: minOrderQty={min_order_qty}, qtyStep={qty_step}, minNotionalValue={min_notional_value}")
                else:
                    # Fallback к статическим значениям
                    min_order_qty = Decimal('0.1')
                    qty_step = Decimal('0.1')
                    min_notional_value = Decimal('5')
                    logger.warning(f"[format_qty_for_bybit] Не удалось получить параметры с биржи, используем fallback")
            else:
                # Fallback к статическим значениям
                min_order_qty = Decimal('0.1')
                qty_step = Decimal('0.1')
                min_notional_value = Decimal('5')
                logger.warning(f"[format_qty_for_bybit] Ошибка запроса к бирже, используем fallback")
        except Exception as e:
            # Fallback к статическим значениям
            min_order_qty = Decimal('0.1')
            qty_step = Decimal('0.1')
            min_notional_value = Decimal('5')
            logger.warning(f"[format_qty_for_bybit] Исключение при получении параметров: {e}, используем fallback")
        
        # qty не может быть меньше minOrderQty
        if qty < min_order_qty:
            logger.info(f"[format_qty_for_bybit] qty < minOrderQty: {qty} < {min_order_qty}, set to minOrderQty")
            qty = min_order_qty
        
        # ✅ ИСПРАВЛЕНИЕ: qty обязательно кратен qtyStep
        if qty_step > 0:
            # Округляем до ближайшего кратного qtyStep
            qty = (qty / qty_step).quantize(Decimal('1'), rounding=ROUND_HALF_UP) * qty_step
        
        logger.info(f"[format_qty_for_bybit] qty after qtyStep rounding: {qty}")
        
        # ✅ ИСПРАВЛЕНИЕ: Проверяем минимальную сумму ордера (minNotionalValue USDT)
        if price is not None and price > 0:
            price_decimal = Decimal(str(price))
            # Рассчитываем минимальное количество для достижения minNotionalValue
            min_qty_raw = min_notional_value / price_decimal
            # Округляем до кратного qty_step в большую сторону
            min_qty_for_value = ((min_qty_raw / qty_step).quantize(Decimal('1'), rounding=ROUND_HALF_UP)) * qty_step
            logger.info(f"[format_qty_for_bybit] min_qty for {min_notional_value} USDT: {min_qty_for_value}")
            if qty < min_qty_for_value:
                # Увеличиваем до минимального количества
                qty = min_qty_for_value
                logger.info(f"[format_qty_for_bybit] qty increased to meet {min_notional_value} USDT minimum: {qty}")
        
        # Проверка кратности qtyStep
        remainder = (qty / qty_step) % 1
        logger.info(f"[format_qty_for_bybit] qty/qtyStep={qty/qty_step}, remainder={remainder}")
        if remainder != 0:
            logger.warning(f"[format_qty_for_bybit] WARNING: qty={qty} не кратен qtyStep={qty_step} (remainder={remainder}) — Bybit не примет!")
            # Принудительно округляем
            qty = (qty / qty_step).quantize(Decimal('1'), rounding=ROUND_HALF_UP) * qty_step
            logger.info(f"[format_qty_for_bybit] Принудительно округлено до: {qty}")
        
        # Форматируем результат - убираем лишние нули только после десятичной точки
        qty_str = f"{qty}"
        if '.' in qty_str:
            qty_str = qty_str.rstrip('0').rstrip('.')
        if qty_str == '':
            qty_str = '0'
        
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
            side = "Buy" if decision == "BUY" else "Sell"
            if (symbol, side) in self.active_positions:
                logger.warning(f"⚠️ Already have {side} position in {symbol}")
                return
            
            # ✅ ИСПРАВЛЕНИЕ: Рассчитываем размер позиции 80-120$ С учетом плеча
            target_position_value = 100  # Целевая стоимость позиции в USDT (с учетом плеча)
            
            # Получаем плечо из конфигурации режима
            leverage = 10  # По умолчанию 10x
            try:
                if hasattr(mode_config, 'leverage_range') and isinstance(mode_config.leverage_range, tuple):
                    leverage = float(mode_config.leverage_range[1])
                    logger.info(f"[_execute_trade] Используем плечо из режима: {leverage}x")
                elif isinstance(mode_config, dict) and 'leverage_range' in mode_config:
                    leverage_range = mode_config['leverage_range']
                    if isinstance(leverage_range, (list, tuple)) and len(leverage_range) > 1:
                        leverage = float(leverage_range[1])
                    else:
                        leverage = float(leverage_range)
                    logger.info(f"[_execute_trade] Используем плечо из режима: {leverage}x")
                else:
                    logger.warning(f"[_execute_trade] Не удалось получить плечо из mode_config, используем по умолчанию: {leverage}x")
            except Exception as e:
                logger.warning(f"[_execute_trade] Ошибка получения плеча: {e}, используем по умолчанию: {leverage}x")
            
            # Получаем minNotionalValue для правильного расчета
            min_notional_value = 5  # По умолчанию
            try:
                base_url = self.get_api_base_url() if hasattr(self, 'bybit_client') and self.bybit_client else "https://api-testnet.bybit.com"
                api_url = f"{base_url}/v5/market/instruments-info"
                params = {"category": "linear", "symbol": symbol}
                response = requests.get(api_url, params=params, timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    if data.get('retCode') == 0 and data.get('result', {}).get('list'):
                        instrument = data['result']['list'][0]
                        lot_size_filter = instrument.get('lotSizeFilter', {})
                        min_notional_value = float(lot_size_filter.get('minNotionalValue', '5'))
                        logger.info(f"[_execute_trade] Получен minNotionalValue с биржи: {min_notional_value}")
            except Exception as e:
                logger.warning(f"[_execute_trade] Исключение при получении параметров: {e}")
            
            # Рассчитываем qty для целевой стоимости С учетом плеча
            # Цель: 1000$ позиция с плечом 10x = 100$ маржи
            # Но мы хотим 1000$ позицию, поэтому умножаем на leverage
            required_value = max(target_position_value * leverage, min_notional_value)
            qty = required_value / current_price
            
            # Округляем qty по параметрам биржи
            qty = self.adjust_qty(symbol, qty)
            
            # Проверяем что расчетная стоимость соответствует требованиям (С учетом плеча)
            calculated_value = qty * current_price
            logger.info(f"🔢 [_execute_trade] Рассчитанный размер: {qty:.6f} {symbol} = {calculated_value:.2f} USDT (с плечом {leverage}x)")
            
            # Проверяем что стоимость в диапазоне 800-1200$ (1000$ ± 200$)
            min_value = 800
            max_value = 1200
            if calculated_value < min_value or calculated_value > max_value:
                logger.warning(f"⚠️ Стоимость позиции {calculated_value:.2f} USDT вне диапазона {min_value}-{max_value}$. Ордер не отправлен.")
                return
            
            await self.place_order(
                symbol=symbol,
                side=side,
                amount=qty,
                order_type="market",
                price=current_price,
                market_data=market_data,
                mode=current_mode.value,
                timeframe=mode_config.get('timeframes', ['5m'])[0] if mode_config and 'timeframes' in mode_config and mode_config['timeframes'] else "5m"
            )
            if current_mode.value == "conservative":
                # Создаём ступенчатый стоп через EnhancedRiskManager
                if hasattr(self.risk_manager, 'create_trailing_stop'):
                    self.risk_manager.create_trailing_stop(
                        symbol=symbol,
                        side=side,
                        entry_price=current_price,
                        stop_type=getattr(self.risk_manager, 'StopLossType', None).STEPWISE if hasattr(self.risk_manager, 'StopLossType') else None
                    )
        except Exception as e:
            import traceback
            logger.error(f"❌ Error executing trade for {symbol}: {e}")
            logger.error(f"❌ Full traceback: {traceback.format_exc()}")
    
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
    
    async def place_order(self, symbol: str, side: str, amount: float, order_type: str = "market", price: float = None, market_data=None, mode=None, timeframe=None) -> Dict:
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
            if mode is None:
                mode = self.risk_manager.mode if hasattr(self.risk_manager, 'mode') else 'medium'
            try:
                mode_enum = TradingMode(mode)
            except Exception:
                mode_enum = TradingMode.MEDIUM
            mode_config = get_mode_config(mode_enum)
            leverage = 1
            if hasattr(mode_config, 'leverage_range') and isinstance(mode_config.leverage_range, tuple):
                leverage = float(mode_config.leverage_range[1])
            
            # ✅ ИСПРАВЛЕНИЕ: Получаем актуальные параметры с биржи для проверки минимальной суммы
            min_notional_value = 5  # По умолчанию
            try:
                base_url = self.get_api_base_url() if hasattr(self, 'bybit_client') and self.bybit_client else "https://api-testnet.bybit.com"
                api_url = f"{base_url}/v5/market/instruments-info"
                params = {"category": "linear", "symbol": symbol}
                response = requests.get(api_url, params=params, timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    if data.get('retCode') == 0 and data.get('result', {}).get('list'):
                        instrument = data['result']['list'][0]
                        lot_size_filter = instrument.get('lotSizeFilter', {})
                        min_notional_value = float(lot_size_filter.get('minNotionalValue', '5'))
                        logger.info(f"[place_order] Получен minNotionalValue с биржи: {min_notional_value}")
                    else:
                        logger.warning(f"[place_order] Не удалось получить параметры с биржи, используем fallback")
                else:
                    logger.warning(f"[place_order] Ошибка запроса к бирже, используем fallback")
            except Exception as e:
                logger.warning(f"[place_order] Исключение при получении параметров: {e}, используем fallback")
            
            # Проверка минимальной суммы ордера (Bybit требует >= minNotionalValue USDT на заявку)
            min_qty = math.ceil(min_notional_value / float(current_price) * 1000) / 1000
            if amount < min_qty:
                logger.info(f"🔄 [min_qty] Increasing qty for {symbol}: {amount} → {min_qty} (to meet minimum order value >= {min_notional_value} USDT)")
                amount = min_qty
            min_order_value = float(amount) * float(current_price)
            if min_order_value < min_notional_value:
                logger.warning(f"⚠️ Сумма ордера {min_order_value:.2f} USDT меньше минимальной {min_notional_value} USDT (Bybit). Ордер не отправлен.")
                return {"success": False, "error": f"Сумма ордера {min_order_value:.2f} USDT меньше минимальной {min_notional_value} USDT (Bybit)"}
            # ✅ ИСПРАВЛЕНИЕ: Для новых ордеров размер уже правильно рассчитан в _execute_trade
            # Проверяем только минимальную сумму ордера для Bybit
            order_value = float(amount) * float(current_price)
            
            logger.info(f"📊 [place_order] Размер ордера: {amount:.6f} {symbol} (стоимость: {order_value:.2f} USDT)")
            # Проверка маржи (баланса)
            margin_required = float(amount) * float(current_price) / leverage
            balance = self.bybit_client.get_balance()
            if balance is not None and margin_required > float(balance):
                logger.warning(f"⚠️ Недостаточно средств: требуется маржа {margin_required:.2f} USDT, доступно {balance:.2f} USDT. Ордер не отправлен.")
                return {"success": False, "error": f"Недостаточно средств: требуется маржа {margin_required:.2f} USDT, доступно {balance:.2f} USDT"}
            stop_loss, take_profit = self.calc_tp_sl(current_price, side, mode, market_data=market_data, symbol=symbol, timeframe=timeframe)
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
                logger.info(f"🔢 [lot_size] Итоговое qty для {symbol}: {qty_str}")
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
    
    async def close_position(self, symbol: str, side: str = None) -> bool:
        """Close a specific position. Если side не указан — закрыть обе стороны"""
        closed = False
        if side:
            key = (symbol, side)
            if key not in self.active_positions:
                logger.warning(f"⚠️ No active {side} position for {symbol}")
                return False
            try:
                position = self.active_positions[key]
                close_side = "Sell" if position["side"] == "Buy" else "Buy"
                qty_final = self.adjust_qty(symbol, position["size"])
                qty_str = self.format_qty_for_bybit(symbol, qty_final)
                logger.info(f"🔢 [lot_size] Закрытие позиции {symbol} {side}: qty={qty_str}")
                order_kwargs = dict(
                    symbol=symbol,
                    side=close_side,
                    order_type="Market",
                    qty=qty_str
                )
                order_result = await self.bybit_client.place_order(**order_kwargs)
                if order_result:
                    del self.active_positions[key]
                    logger.info(f"✅ Position closed for {symbol} {side}")
                    await self.sync_positions_with_exchange()
                    closed = True
            except Exception as e:
                logger.error(f"❌ Error closing position for {symbol} {side}: {e}")
        else:
            # Закрыть обе стороны
            for s in ["Buy", "Sell"]:
                key = (symbol, s)
                if key in self.active_positions:
                    try:
                        position = self.active_positions[key]
                        close_side = "Sell" if position["side"] == "Buy" else "Buy"
                        qty_final = self.adjust_qty(symbol, position["size"])
                        qty_str = self.format_qty_for_bybit(symbol, qty_final)
                        logger.info(f"🔢 [lot_size] Закрытие позиции {symbol} {s}: qty={qty_str}")
                        order_kwargs = dict(
                            symbol=symbol,
                            side=close_side,
                            order_type="Market",
                            qty=qty_str
                        )
                        order_result = await self.bybit_client.place_order(**order_kwargs)
                        if order_result:
                            del self.active_positions[key]
                            logger.info(f"✅ Position closed for {symbol} {s}")
                            closed = True
                    except Exception as e:
                        logger.error(f"❌ Error closing position for {symbol} {s}: {e}")
            if closed:
                await self.sync_positions_with_exchange()
        return closed
    
    async def shutdown(self):
        """Shutdown the trading engine gracefully"""
        logger.info("🔄 Shutting down trading engine...")
        
        # Stop trading
        self.stop()
        
        # Close all positions
        for key in list(self.active_positions.keys()):
            await self.close_position(key[0], key[1])
        
        logger.info("✅ Trading engine shutdown complete")

    async def sync_positions_with_exchange(self):
        """Синхронизировать локальные позиции с реальными на бирже"""
        if not self.bybit_client:
            logger.warning("⚠️ Bybit client не инициализирован, синхронизация невозможна")
            return
        real_positions = self.bybit_client.get_positions() or []
        real_keys = {(p['symbol'], p.get('side', 'Buy')) for p in real_positions if p['size'] > 0}
        # Удаляем локальные позиции, которых нет на бирже
        for key in list(self.active_positions.keys()):
            if key not in real_keys:
                del self.active_positions[key]
        # Добавляем новые, если есть на бирже, а локально нет
        for pos in real_positions:
            key = (pos['symbol'], pos.get('side', 'Buy'))
            if key not in self.active_positions and pos['size'] > 0:
                self.active_positions[key] = pos
                
        # ✅ НОВОЕ: Корректируем размеры существующих позиций
        await self.correct_position_sizes()

    async def correct_position_sizes(self):
        """Корректирует размеры всех активных позиций до диапазона 80-120 USDT"""
        if not self.bybit_client:
            return
            
        try:
            real_positions = self.bybit_client.get_positions() or []
            # ✅ ИСПРАВЛЕНИЕ: Для корректировки позиций всегда используем leverage=1
            # так как позиции на бирже уже имеют встроенное плечо
            leverage = 1
            
            for position in real_positions:
                symbol = position['symbol']
                current_size = float(position['size'])
                
                if current_size <= 0:
                    continue
                    
                # Получаем текущую цену
                current_price = self.bybit_client.get_current_price(symbol)
                if not current_price:
                    continue
                    
                # Рассчитываем текущую стоимость позиции С учетом плеча
                position_value = current_size * current_price * leverage
                side = position.get('side', 'Buy')
                
                logger.info(f"🔍 [correct_position_sizes] Проверяем {symbol}: "
                          f"размер={current_size}, цена={current_price}, "
                          f"стоимость={position_value:.2f} USDT")
                
                # Проверяем нужна ли корректировка (диапазон 800-1200$ для позиций ~1000$)
                min_value = 800
                max_value = 1200
                
                if min_value <= position_value <= max_value:
                    logger.info(f"✅ {symbol}: Размер позиции в норме ({position_value:.2f} USDT)")
                    continue
                    
                if position_value < min_value:
                    # Позиция слишком мала - увеличиваем до 1000 USDT
                    target_value = 1000
                    target_size = target_value / (current_price * leverage)
                    additional_size = target_size - current_size
                    
                    if additional_size > 0:
                        logger.info(f"📈 {symbol}: Увеличиваем позицию с {position_value:.2f} до 1000 USDT "
                                  f"(+{additional_size:.6f})")
                        
                        # Округляем до параметров биржи
                        additional_size = self.adjust_qty(symbol, additional_size)
                        
                        # Выставляем дополнительный ордер
                        result = await self.place_order(
                            symbol=symbol,
                            side=side,
                            amount=additional_size,
                            order_type="market"
                        )
                        
                        if result.get('success'):
                            logger.info(f"✅ {symbol}: Позиция увеличена на {additional_size:.6f}")
                        else:
                            logger.error(f"❌ {symbol}: Ошибка увеличения позиции: {result.get('error')}")
                            
                elif position_value > max_value:
                    # Позиция слишком велика - уменьшаем до 1000 USDT
                    target_value = 1000
                    target_size = target_value / (current_price * leverage)
                    reduce_size = current_size - target_size
                    
                    if reduce_size > 0:
                        logger.info(f"📉 {symbol}: Уменьшаем позицию с {position_value:.2f} до 1000 USDT "
                                  f"(-{reduce_size:.6f})")
                        
                        # Округляем до параметров биржи
                        reduce_size = self.adjust_qty(symbol, reduce_size)
                        
                        # Определяем противоположную сторону для частичного закрытия
                        close_side = "Sell" if side == "Buy" else "Buy"
                        
                        # Выставляем ордер на частичное закрытие
                        result = await self.place_order(
                            symbol=symbol,
                            side=close_side,
                            amount=reduce_size,
                            order_type="market"
                        )
                        
                        if result.get('success'):
                            logger.info(f"✅ {symbol}: Позиция уменьшена на {reduce_size:.6f}")
                        else:
                            logger.error(f"❌ {symbol}: Ошибка уменьшения позиции: {result.get('error')}")
                            
        except Exception as e:
            logger.error(f"❌ Ошибка корректировки размеров позиций: {e}")

    def get_api_base_url(self) -> str:
        """Возвращает правильный базовый URL для API в зависимости от режима"""
        if hasattr(self.bybit_client, 'demo') and self.bybit_client.demo:
            return "https://api-demo.bybit.com"
        elif hasattr(self.bybit_client, 'testnet') and self.bybit_client.testnet:
            return "https://api-testnet.bybit.com"
        else:
            return "https://api.bybit.com"