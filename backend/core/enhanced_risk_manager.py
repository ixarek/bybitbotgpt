"""
Enhanced Risk Manager for Bybit Trading Bot
Улучшенное управление рисками с трейлинг-стопами и адаптивным позиционированием
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from enum import Enum
import pandas as pd
import numpy as np

from .risk_manager import RiskManager
from .market_analyzer import MarketAnalyzer, MarketRegime
from ..utils.config import settings, get_risk_config

logger = logging.getLogger(__name__)


class StopLossType(Enum):
    """Типы стоп-лоссов"""
    FIXED = "fixed"
    TRAILING = "trailing"
    ATR_BASED = "atr_based"
    PERCENTAGE = "percentage"
    VOLATILITY_ADJUSTED = "volatility_adjusted"


class PositionRisk(Enum):
    """Уровни риска позиции"""
    VERY_LOW = "very_low"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"


class TrailingStopOrder:
    """Класс для управления трейлинг-стопом"""
    
    def __init__(self, symbol: str, side: str, entry_price: float, 
                 initial_stop: float, trailing_distance: float, 
                 stop_type: StopLossType = StopLossType.TRAILING):
        self.symbol = symbol
        self.side = side  # "BUY" or "SELL"
        self.entry_price = entry_price
        self.initial_stop = initial_stop
        self.current_stop = initial_stop
        self.trailing_distance = trailing_distance
        self.stop_type = stop_type
        self.best_price = entry_price
        self.created_at = datetime.now()
        self.last_update = datetime.now()
        self.is_active = True
        
    def update_trailing_stop(self, current_price: float, atr: Optional[float] = None) -> bool:
        """Обновление трейлинг-стопа"""
        try:
            if not self.is_active:
                return False
            
            updated = False
            
            if self.side == "BUY":  # Лонг позиция
                if current_price > self.best_price:
                    self.best_price = current_price
                    
                    if self.stop_type == StopLossType.TRAILING:
                        new_stop = current_price - self.trailing_distance
                    elif self.stop_type == StopLossType.ATR_BASED and atr:
                        new_stop = current_price - (atr * 2)
                    elif self.stop_type == StopLossType.PERCENTAGE:
                        new_stop = current_price * (1 - self.trailing_distance)
                    else:
                        new_stop = current_price - self.trailing_distance
                    
                    if new_stop > self.current_stop:
                        self.current_stop = new_stop
                        updated = True
            
            else:  # Шорт позиция
                if current_price < self.best_price:
                    self.best_price = current_price
                    
                    if self.stop_type == StopLossType.TRAILING:
                        new_stop = current_price + self.trailing_distance
                    elif self.stop_type == StopLossType.ATR_BASED and atr:
                        new_stop = current_price + (atr * 2)
                    elif self.stop_type == StopLossType.PERCENTAGE:
                        new_stop = current_price * (1 + self.trailing_distance)
                    else:
                        new_stop = current_price + self.trailing_distance
                    
                    if new_stop < self.current_stop:
                        self.current_stop = new_stop
                        updated = True
            
            if updated:
                self.last_update = datetime.now()
                logger.info(f"🔄 Trailing stop updated for {self.symbol}: {self.current_stop:.4f}")
            
            return updated
            
        except Exception as e:
            logger.error(f"Error updating trailing stop: {e}")
            return False
    
    def should_trigger(self, current_price: float) -> bool:
        """Проверка срабатывания стопа"""
        if not self.is_active:
            return False
        
        if self.side == "BUY":
            return current_price <= self.current_stop
        else:
            return current_price >= self.current_stop
    
    def get_info(self) -> Dict[str, Any]:
        """Получение информации о стопе"""
        return {
            "symbol": self.symbol,
            "side": self.side,
            "entry_price": self.entry_price,
            "current_stop": self.current_stop,
            "best_price": self.best_price,
            "trailing_distance": self.trailing_distance,
            "stop_type": self.stop_type.value,
            "profit_loss": self.calculate_profit_loss(),
            "age_minutes": (datetime.now() - self.created_at).total_seconds() / 60,
            "is_active": self.is_active
        }
    
    def calculate_profit_loss(self) -> float:
        """Расчет текущей прибыли/убытка"""
        if self.side == "BUY":
            return (self.best_price - self.entry_price) / self.entry_price
        else:
            return (self.entry_price - self.best_price) / self.entry_price


class EnhancedRiskManager(RiskManager):
    """
    Улучшенный менеджер рисков с трейлинг-стопами
    и адаптивным управлением позициями
    """
    
    def __init__(self):
        super().__init__()
        self.market_analyzer = MarketAnalyzer()
        self.trailing_stops: Dict[str, TrailingStopOrder] = {}
        self.position_history: List[Dict] = []
        self.max_history_size = 100
        
        # Настройки трейлинг-стопов
        self.trailing_config = {
            "default_distance": 0.02,  # 2%
            "min_distance": 0.005,     # 0.5%
            "max_distance": 0.05,      # 5%
            "atr_multiplier": 2.0,
            "update_frequency": 30     # секунд
        }
        
        # Настройки адаптивного позиционирования
        self.position_config = {
            "base_risk_per_trade": 0.02,    # 2% от депозита
            "max_risk_per_trade": 0.05,     # 5% от депозита
            "volatility_adjustment": True,
            "correlation_adjustment": True,
            "trend_adjustment": True
        }
        
        # Отслеживание корреляций
        self.correlation_matrix = {}
        self.last_correlation_update = datetime.now()
        
        logger.info("🛡️ Enhanced Risk Manager initialized with trailing stops")
    
    async def calculate_enhanced_position_size(
        self, 
        symbol: str, 
        signals: Dict[str, Any], 
        current_price: float,
        account_balance: float = 1000.0
    ) -> Dict[str, Any]:
        """
        Расчет размера позиции с учетом рыночных условий
        и адаптивного управления рисками
        """
        try:
            # Получаем анализ рынка
            market_analysis = self.market_analyzer.analyze_market(symbol)
            
            # Базовый размер позиции
            base_risk = self.position_config["base_risk_per_trade"]
            base_position_value = account_balance * base_risk
            
            # Корректировки на основе рыночных условий
            risk_multiplier = self._calculate_risk_multiplier(market_analysis, signals)
            
            # Корректировка на волатильность
            volatility_multiplier = self._calculate_volatility_multiplier(market_analysis)
            
            # Корректировка на тренд
            trend_multiplier = self._calculate_trend_multiplier(market_analysis)
            
            # Корректировка на корреляцию
            correlation_multiplier = await self._calculate_correlation_multiplier(symbol)
            
            # Итоговый размер позиции
            final_multiplier = (risk_multiplier * 
                              volatility_multiplier * 
                              trend_multiplier * 
                              correlation_multiplier)
            
            # Ограничиваем размер позиции
            max_risk = self.position_config["max_risk_per_trade"]
            final_multiplier = min(final_multiplier, max_risk / base_risk)
            
            adjusted_position_value = base_position_value * final_multiplier
            quantity = adjusted_position_value / current_price
            
            # Определяем уровень риска
            risk_level = self._determine_risk_level(final_multiplier)
            
            return {
                "quantity": quantity,
                "position_value": adjusted_position_value,
                "risk_multiplier": final_multiplier,
                "risk_level": risk_level.value,
                "base_risk": base_risk,
                "adjustments": {
                    "market_conditions": risk_multiplier,
                    "volatility": volatility_multiplier,
                    "trend": trend_multiplier,
                    "correlation": correlation_multiplier
                },
                "market_analysis": market_analysis
            }
            
        except Exception as e:
            logger.error(f"Error in enhanced position sizing: {e}")
            return await self.calculate_position_size(symbol, signals, current_price)
    
    def create_trailing_stop(
        self, 
        symbol: str, 
        side: str, 
        entry_price: float,
        market_analysis: Optional[Dict] = None,
        stop_type: StopLossType = StopLossType.TRAILING
    ) -> TrailingStopOrder:
        """Создание трейлинг-стопа"""
        try:
            # Получаем анализ рынка если не предоставлен
            if market_analysis is None:
                market_analysis = self.market_analyzer.analyze_market(symbol)
            
            # Рассчитываем дистанцию трейлинга
            trailing_distance = self._calculate_trailing_distance(market_analysis, stop_type)
            
            # Рассчитываем начальный стоп
            if side == "BUY":
                initial_stop = entry_price - trailing_distance
            else:
                initial_stop = entry_price + trailing_distance
            
            # Создаем трейлинг-стоп
            trailing_stop = TrailingStopOrder(
                symbol=symbol,
                side=side,
                entry_price=entry_price,
                initial_stop=initial_stop,
                trailing_distance=trailing_distance,
                stop_type=stop_type
            )
            
            # Сохраняем в активные стопы
            self.trailing_stops[f"{symbol}_{side}"] = trailing_stop
            
            logger.info(f"✅ Trailing stop created for {symbol} {side}: {initial_stop:.4f}")
            return trailing_stop
            
        except Exception as e:
            logger.error(f"Error creating trailing stop: {e}")
            # Возвращаем простой стоп
            distance = self.trailing_config["default_distance"]
            if side == "BUY":
                initial_stop = entry_price * (1 - distance)
            else:
                initial_stop = entry_price * (1 + distance)
            
            return TrailingStopOrder(symbol, side, entry_price, initial_stop, distance)
    
    async def update_trailing_stops(self, market_data: Dict[str, float]) -> List[str]:
        """Обновление всех трейлинг-стопов"""
        triggered_stops = []
        
        try:
            for stop_key, trailing_stop in self.trailing_stops.items():
                if not trailing_stop.is_active:
                    continue
                
                symbol = trailing_stop.symbol
                current_price = market_data.get(symbol)
                
                if current_price is None:
                    continue
                
                # Получаем ATR для ATR-based стопов
                atr = None
                if trailing_stop.stop_type == StopLossType.ATR_BASED:
                    try:
                        from backend.integrations.bybit_client import bybit_client
                        if bybit_client:
                            df = bybit_client.get_kline(symbol, "5", limit=50)
                            if df is not None and len(df) > 14:
                                atr = self._calculate_atr(df['high'], df['low'], df['close'])
                    except Exception as e:
                        logger.warning(f"Could not get ATR for {symbol}: {e}")
                
                # Обновляем трейлинг-стоп
                trailing_stop.update_trailing_stop(current_price, atr)
                
                # Проверяем срабатывание
                if trailing_stop.should_trigger(current_price):
                    triggered_stops.append(stop_key)
                    trailing_stop.is_active = False
                    logger.warning(f"🚨 Trailing stop triggered for {symbol}: {current_price:.4f}")
            
            return triggered_stops
            
        except Exception as e:
            logger.error(f"Error updating trailing stops: {e}")
            return []
    
    def _calculate_risk_multiplier(self, market_analysis: Dict, signals: Dict[str, Any]) -> float:
        """Расчет мультипликатора риска на основе рыночных условий"""
        try:
            base_multiplier = 1.0
            
            # Корректировка на основе рыночного счета
            market_score = market_analysis.get("market_score", 50)
            if market_score > 70:
                base_multiplier *= 1.2  # Увеличиваем при хороших условиях
            elif market_score < 30:
                base_multiplier *= 0.7  # Уменьшаем при плохих условиях
            
            # Корректировка на основе силы сигнала
            if isinstance(signals, dict):
                signal_strength = signals.get("signal_strength", 0.0)
                if signal_strength > 0.7:
                    base_multiplier *= 1.1
                elif signal_strength < 0.4:
                    base_multiplier *= 0.8
            
            # Корректировка на основе режима рынка
            regime = market_analysis.get("regime", "sideways")
            if regime in ["trending_up", "trending_down"]:
                base_multiplier *= 1.1  # Увеличиваем в трендовых рынках
            elif regime == "high_volatility":
                base_multiplier *= 0.8  # Уменьшаем при высокой волатильности
            
            return min(max(base_multiplier, 0.3), 2.0)
            
        except Exception as e:
            logger.error(f"Error calculating risk multiplier: {e}")
            return 1.0
    
    def _calculate_volatility_multiplier(self, market_analysis: Dict) -> float:
        """Расчет мультипликатора на основе волатильности"""
        try:
            volatility = market_analysis.get("volatility", {})
            vol_level = volatility.get("level", "medium")
            
            multipliers = {
                "very_low": 1.2,
                "low": 1.1,
                "medium": 1.0,
                "high": 0.8,
                "very_high": 0.6
            }
            
            return multipliers.get(vol_level, 1.0)
            
        except Exception as e:
            logger.error(f"Error calculating volatility multiplier: {e}")
            return 1.0
    
    def _calculate_trend_multiplier(self, market_analysis: Dict) -> float:
        """Расчет мультипликатора на основе тренда"""
        try:
            trend = market_analysis.get("trend", {})
            trend_strength = trend.get("strength", "none")
            
            multipliers = {
                "strong": 1.2,
                "medium": 1.1,
                "weak": 1.0,
                "none": 0.9
            }
            
            return multipliers.get(trend_strength, 1.0)
            
        except Exception as e:
            logger.error(f"Error calculating trend multiplier: {e}")
            return 1.0
    
    async def _calculate_correlation_multiplier(self, symbol: str) -> float:
        """Расчет мультипликатора на основе корреляции с другими позициями"""
        try:
            # Простая реализация - если у нас уже есть позиции в коррелированных активах,
            # уменьшаем размер новой позиции
            
            # Группы коррелированных активов
            correlation_groups = {
                "major_crypto": ["BTCUSDT", "ETHUSDT"],
                "altcoins": ["SOLUSDT", "ADAUSDT", "BNBUSDT"],
                "meme_coins": ["DOGEUSDT"]
            }
            
            # Находим группу текущего символа
            current_group = None
            for group, symbols in correlation_groups.items():
                if symbol in symbols:
                    current_group = group
                    break
            
            if current_group is None:
                return 1.0
            
            # Считаем количество активных позиций в той же группе
            active_positions_in_group = 0
            for stop_key in self.trailing_stops:
                if self.trailing_stops[stop_key].is_active:
                    stop_symbol = self.trailing_stops[stop_key].symbol
                    if stop_symbol in correlation_groups.get(current_group, []):
                        active_positions_in_group += 1
            
            # Уменьшаем размер позиции при наличии коррелированных позиций
            if active_positions_in_group > 0:
                return max(0.5, 1.0 - (active_positions_in_group * 0.2))
            
            return 1.0
            
        except Exception as e:
            logger.error(f"Error calculating correlation multiplier: {e}")
            return 1.0
    
    def _calculate_trailing_distance(self, market_analysis: Dict, stop_type: StopLossType) -> float:
        """Расчет дистанции трейлинга"""
        try:
            if stop_type == StopLossType.PERCENTAGE:
                # Базовая дистанция
                base_distance = self.trailing_config["default_distance"]
                
                # Корректировка на волатильность
                volatility = market_analysis.get("volatility", {})
                vol_pct = volatility.get("percentage", 2.0)
                
                # Увеличиваем дистанцию при высокой волатильности
                if vol_pct > 5.0:
                    distance = base_distance * 1.5
                elif vol_pct > 3.0:
                    distance = base_distance * 1.2
                elif vol_pct < 1.0:
                    distance = base_distance * 0.8
                else:
                    distance = base_distance
                
                # Ограничиваем дистанцию
                min_dist = self.trailing_config["min_distance"]
                max_dist = self.trailing_config["max_distance"]
                
                return min(max(distance, min_dist), max_dist)
            
            elif stop_type == StopLossType.ATR_BASED:
                # Для ATR-based стопов используем мультипликатор
                return self.trailing_config["atr_multiplier"]
            
            else:
                return self.trailing_config["default_distance"]
                
        except Exception as e:
            logger.error(f"Error calculating trailing distance: {e}")
            return self.trailing_config["default_distance"]
    
    def _determine_risk_level(self, multiplier: float) -> PositionRisk:
        """Определение уровня риска позиции"""
        if multiplier >= 1.5:
            return PositionRisk.VERY_HIGH
        elif multiplier >= 1.2:
            return PositionRisk.HIGH
        elif multiplier >= 0.8:
            return PositionRisk.MEDIUM
        elif multiplier >= 0.5:
            return PositionRisk.LOW
        else:
            return PositionRisk.VERY_LOW
    
    def _calculate_atr(self, high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> float:
        """Расчет ATR"""
        try:
            high_low = high - low
            high_close = np.abs(high - close.shift())
            low_close = np.abs(low - close.shift())
            true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
            atr = true_range.rolling(window=period).mean()
            return atr.iloc[-1] if len(atr) > 0 else 0.0
        except Exception as e:
            logger.error(f"Error calculating ATR: {e}")
            return 0.0
    
    def get_risk_summary(self) -> Dict[str, Any]:
        """Получение сводки по рискам"""
        try:
            active_stops = sum(1 for stop in self.trailing_stops.values() if stop.is_active)
            
            # Статистика по стопам
            stop_stats = {
                "active_stops": active_stops,
                "total_stops": len(self.trailing_stops),
                "stop_types": {}
            }
            
            for stop in self.trailing_stops.values():
                stop_type = stop.stop_type.value
                if stop_type not in stop_stats["stop_types"]:
                    stop_stats["stop_types"][stop_type] = 0
                stop_stats["stop_types"][stop_type] += 1
            
            # Общая информация о рисках
            risk_info = {
                "daily_trades": self.daily_trade_count,
                "max_daily_trades": self.max_daily_trades,
                "daily_pnl": self.daily_pnl,
                "max_drawdown": self.max_drawdown,
                "risk_mode": self.mode,
                "trailing_stops": stop_stats,
                "position_history_size": len(self.position_history)
            }
            
            return risk_info
            
        except Exception as e:
            logger.error(f"Error getting risk summary: {e}")
            return {"error": str(e)}
    
    def get_active_trailing_stops(self) -> List[Dict[str, Any]]:
        """Получение информации об активных трейлинг-стопах"""
        try:
            active_stops = []
            for stop_key, stop in self.trailing_stops.items():
                if stop.is_active:
                    active_stops.append(stop.get_info())
            return active_stops
        except Exception as e:
            logger.error(f"Error getting active trailing stops: {e}")
            return []
    
    def remove_trailing_stop(self, symbol: str, side: str) -> bool:
        """Удаление трейлинг-стопа"""
        try:
            stop_key = f"{symbol}_{side}"
            if stop_key in self.trailing_stops:
                self.trailing_stops[stop_key].is_active = False
                del self.trailing_stops[stop_key]
                logger.info(f"🗑️ Trailing stop removed for {symbol} {side}")
                return True
            return False
        except Exception as e:
            logger.error(f"Error removing trailing stop: {e}")
            return False 