"""
Enhanced Signal Processor for Bybit Trading Bot
Улучшенная обработка сигналов с весовыми коэффициентами и фильтрацией
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Any, Tuple
import logging
from datetime import datetime
from enum import Enum

from .signal_processor import SignalProcessor
from .market_analyzer import MarketAnalyzer, MarketRegime

logger = logging.getLogger(__name__)


class SignalStrength(Enum):
    """Уровни силы сигналов"""
    VERY_WEAK = "very_weak"
    WEAK = "weak"
    MEDIUM = "medium"
    STRONG = "strong"
    VERY_STRONG = "very_strong"


class SignalConfidence(Enum):
    """Уровни уверенности в сигнале"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"


class EnhancedSignalProcessor(SignalProcessor):
    """
    Улучшенный процессор сигналов с весовыми коэффициентами
    и адаптивной фильтрацией на основе рыночных условий
    """
    
    def __init__(self):
        super().__init__()
        self.market_analyzer = MarketAnalyzer()
        
        # Весовые коэффициенты для индикаторов (базовые)
        self.base_weights = {
            "RSI": 0.12,
            "MACD": 0.15,
            "SMA": 0.10,
            "EMA": 0.13,
            "BB": 0.11,
            "STOCH": 0.08,
            "WILLIAMS": 0.07,
            "ATR": 0.06,
            "ADX": 0.10,
            "MFI": 0.04,
            "OBV": 0.04
        }
        
        # Адаптивные веса для разных рыночных режимов
        self.regime_weight_adjustments = {
            MarketRegime.TRENDING_UP: {
                "MACD": 1.3, "EMA": 1.2, "ADX": 1.4, "RSI": 0.8, "STOCH": 0.7
            },
            MarketRegime.TRENDING_DOWN: {
                "MACD": 1.3, "EMA": 1.2, "ADX": 1.4, "RSI": 0.8, "STOCH": 0.7
            },
            MarketRegime.SIDEWAYS: {
                "RSI": 1.4, "STOCH": 1.3, "WILLIAMS": 1.2, "BB": 1.3, "MACD": 0.7
            },
            MarketRegime.HIGH_VOLATILITY: {
                "ATR": 1.5, "BB": 1.3, "RSI": 1.2, "SMA": 0.8, "EMA": 0.8
            },
            MarketRegime.CONSOLIDATION: {
                "RSI": 1.3, "STOCH": 1.2, "BB": 1.4, "MACD": 0.8, "ADX": 0.7
            },
            MarketRegime.BREAKOUT: {
                "OBV": 1.5, "MFI": 1.4, "ATR": 1.3, "MACD": 1.2, "RSI": 0.9
            }
        }
        
        # Пороговые значения для фильтрации сигналов
        self.signal_thresholds = {
            SignalStrength.VERY_WEAK: 0.3,
            SignalStrength.WEAK: 0.4,
            SignalStrength.MEDIUM: 0.5,
            SignalStrength.STRONG: 0.6,
            SignalStrength.VERY_STRONG: 0.7
        }
        
        logger.info("🔧 Enhanced Signal Processor initialized with weighted filtering")
    
    def get_enhanced_signals(self, symbol: str, timeframe: str = "5") -> Dict[str, Any]:
        """
        Получение улучшенных сигналов с весовыми коэффициентами
        и адаптацией к рыночным условиям
        """
        try:
            # Получаем базовые сигналы
            base_signals = self.get_signals(symbol, timeframe)
            
            # Анализируем рыночные условия
            market_analysis = self.market_analyzer.analyze_market(symbol, timeframe)
            
            # Рассчитываем адаптивные веса
            adaptive_weights = self._calculate_adaptive_weights(market_analysis)
            
            # Рассчитываем взвешенные сигналы
            weighted_signals = self._calculate_weighted_signals(base_signals, adaptive_weights)
            
            # Фильтруем сигналы по силе
            filtered_signals = self._filter_signals_by_strength(weighted_signals, market_analysis)
            
            # Определяем окончательный сигнал
            final_signal = self._determine_final_signal(filtered_signals, market_analysis)
            
            return {
                "base_signals": base_signals,
                "weighted_signals": weighted_signals,
                "filtered_signals": filtered_signals,
                "final_signal": final_signal,
                "market_analysis": market_analysis,
                "adaptive_weights": adaptive_weights,
                "signal_strength": self._calculate_signal_strength(weighted_signals),
                "confidence": self._calculate_confidence(weighted_signals, market_analysis),
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"❌ Error in enhanced signal processing for {symbol}: {e}")
            return self._generate_fallback_signals()
    
    def _calculate_adaptive_weights(self, market_analysis: Dict) -> Dict[str, float]:
        """Расчет адаптивных весов на основе рыночных условий"""
        try:
            regime_str = market_analysis.get("regime", "sideways")
            
            # Находим соответствующий режим
            regime = None
            for r in MarketRegime:
                if r.value == regime_str:
                    regime = r
                    break
            
            if regime is None:
                regime = MarketRegime.SIDEWAYS
            
            # Начинаем с базовых весов
            adaptive_weights = self.base_weights.copy()
            
            # Применяем корректировки для режима
            if regime in self.regime_weight_adjustments:
                adjustments = self.regime_weight_adjustments[regime]
                for indicator, multiplier in adjustments.items():
                    if indicator in adaptive_weights:
                        adaptive_weights[indicator] *= multiplier
            
            # Дополнительные корректировки на основе волатильности
            volatility = market_analysis.get("volatility", {})
            if volatility.get("is_high", False):
                # При высокой волатильности увеличиваем вес ATR и BB
                adaptive_weights["ATR"] *= 1.3
                adaptive_weights["BB"] *= 1.2
                # Уменьшаем вес трендовых индикаторов
                adaptive_weights["SMA"] *= 0.8
                adaptive_weights["EMA"] *= 0.8
            
            # Корректировки на основе объема
            volume = market_analysis.get("volume", {})
            if volume.get("is_high", False):
                # При высоком объеме увеличиваем вес OBV и MFI
                adaptive_weights["OBV"] *= 1.4
                adaptive_weights["MFI"] *= 1.3
            
            # Нормализуем веса чтобы сумма была 1.0
            total_weight = sum(adaptive_weights.values())
            if total_weight > 0:
                adaptive_weights = {k: v/total_weight for k, v in adaptive_weights.items()}
            
            return adaptive_weights
            
        except Exception as e:
            logger.error(f"Error calculating adaptive weights: {e}")
            return self.base_weights
    
    def _calculate_weighted_signals(self, base_signals: Dict[str, str], weights: Dict[str, float]) -> Dict[str, Any]:
        """Расчет взвешенных сигналов"""
        try:
            # Конвертируем сигналы в числовые значения
            signal_values = {}
            for indicator, signal in base_signals.items():
                if signal == "BUY":
                    signal_values[indicator] = 1.0
                elif signal == "SELL":
                    signal_values[indicator] = -1.0
                else:  # HOLD
                    signal_values[indicator] = 0.0
            
            # Рассчитываем взвешенные значения
            weighted_buy_score = 0.0
            weighted_sell_score = 0.0
            weighted_hold_score = 0.0
            
            for indicator, value in signal_values.items():
                weight = weights.get(indicator, 0.0)
                
                if value > 0:  # BUY
                    weighted_buy_score += weight * value
                elif value < 0:  # SELL
                    weighted_sell_score += weight * abs(value)
                else:  # HOLD
                    weighted_hold_score += weight
            
            # Нормализуем счета
            total_score = weighted_buy_score + weighted_sell_score + weighted_hold_score
            if total_score > 0:
                weighted_buy_score /= total_score
                weighted_sell_score /= total_score
                weighted_hold_score /= total_score
            
            return {
                "buy_score": weighted_buy_score,
                "sell_score": weighted_sell_score,
                "hold_score": weighted_hold_score,
                "net_score": weighted_buy_score - weighted_sell_score,
                "signal_values": signal_values,
                "total_weight": total_score
            }
            
        except Exception as e:
            logger.error(f"Error calculating weighted signals: {e}")
            return {"buy_score": 0.33, "sell_score": 0.33, "hold_score": 0.34, "net_score": 0.0}
    
    def _filter_signals_by_strength(self, weighted_signals: Dict[str, Any], market_analysis: Dict) -> Dict[str, Any]:
        """Фильтрация сигналов по силе"""
        try:
            buy_score = weighted_signals.get("buy_score", 0.0)
            sell_score = weighted_signals.get("sell_score", 0.0)
            net_score = weighted_signals.get("net_score", 0.0)
            
            # Определяем силу сигнала
            signal_strength = max(buy_score, sell_score)
            
            # Определяем уровень силы
            strength_level = SignalStrength.VERY_WEAK
            for level, threshold in self.signal_thresholds.items():
                if signal_strength >= threshold:
                    strength_level = level
            
            # Адаптивные пороги на основе рыночных условий
            market_score = market_analysis.get("market_score", 50)
            volatility_is_high = market_analysis.get("volatility", {}).get("is_high", False)
            
            # Корректируем пороги
            adjusted_threshold = 0.5  # Базовый порог
            
            if market_score > 70:
                adjusted_threshold *= 0.9  # Снижаем порог при хороших условиях
            elif market_score < 30:
                adjusted_threshold *= 1.2  # Повышаем порог при плохих условиях
            
            if volatility_is_high:
                adjusted_threshold *= 1.1  # Повышаем порог при высокой волатильности
            
            # Определяем, проходит ли сигнал фильтрацию
            passes_filter = signal_strength >= adjusted_threshold
            
            return {
                "signal_strength": signal_strength,
                "strength_level": strength_level.value,
                "adjusted_threshold": adjusted_threshold,
                "passes_filter": passes_filter,
                "buy_score": buy_score,
                "sell_score": sell_score,
                "net_score": net_score,
                "market_score": market_score
            }
            
        except Exception as e:
            logger.error(f"Error filtering signals: {e}")
            return {"signal_strength": 0.0, "passes_filter": False}
    
    def _determine_final_signal(self, filtered_signals: Dict[str, Any], market_analysis: Dict) -> Dict[str, Any]:
        """Определение окончательного торгового сигнала"""
        try:
            passes_filter = filtered_signals.get("passes_filter", False)
            buy_score = filtered_signals.get("buy_score", 0.0)
            sell_score = filtered_signals.get("sell_score", 0.0)
            net_score = filtered_signals.get("net_score", 0.0)
            
            # Если сигнал не проходит фильтрацию, возвращаем HOLD
            if not passes_filter:
                return {
                    "action": "HOLD",
                    "confidence": "low",
                    "reason": "Signal too weak to pass filter",
                    "score": 0.0
                }
            
            # Определяем действие на основе счетов
            if buy_score > sell_score and net_score > 0.1:
                action = "BUY"
                score = buy_score
            elif sell_score > buy_score and net_score < -0.1:
                action = "SELL"
                score = sell_score
            else:
                action = "HOLD"
                score = max(buy_score, sell_score)
            
            # Определяем уверенность
            confidence = self._calculate_confidence(filtered_signals, market_analysis)
            
            # Дополнительная проверка на основе рыночных условий
            regime = market_analysis.get("regime", "sideways")
            trend_strength = market_analysis.get("trend_strength", 50)
            
            # Корректируем сигнал на основе тренда
            if action == "BUY" and regime == "trending_down" and trend_strength > 60:
                action = "HOLD"
                confidence = "low"
                reason = "Strong downtrend detected"
            elif action == "SELL" and regime == "trending_up" and trend_strength > 60:
                action = "HOLD"
                confidence = "low"
                reason = "Strong uptrend detected"
            else:
                reason = f"Signal confirmed by {regime} market conditions"
            
            return {
                "action": action,
                "confidence": confidence,
                "score": score,
                "reason": reason,
                "market_regime": regime,
                "trend_strength": trend_strength
            }
            
        except Exception as e:
            logger.error(f"Error determining final signal: {e}")
            return {"action": "HOLD", "confidence": "low", "score": 0.0, "reason": "Error in signal processing"}
    
    def _calculate_signal_strength(self, weighted_signals: Dict[str, Any]) -> float:
        """Расчет общей силы сигнала (0-100)"""
        try:
            buy_score = weighted_signals.get("buy_score", 0.0)
            sell_score = weighted_signals.get("sell_score", 0.0)
            
            # Сила сигнала = максимальный счет * 100
            strength = max(buy_score, sell_score) * 100
            
            return min(max(strength, 0), 100)
            
        except Exception as e:
            logger.error(f"Error calculating signal strength: {e}")
            return 0.0
    
    def _calculate_confidence(self, signals: Dict[str, Any], market_analysis: Dict) -> str:
        """Расчет уверенности в сигнале"""
        try:
            signal_strength = signals.get("signal_strength", 0.0)
            market_score = market_analysis.get("market_score", 50)
            volatility_is_high = market_analysis.get("volatility", {}).get("is_high", False)
            
            # Базовая уверенность на основе силы сигнала
            if signal_strength >= 0.7:
                base_confidence = "very_high"
            elif signal_strength >= 0.6:
                base_confidence = "high"
            elif signal_strength >= 0.5:
                base_confidence = "medium"
            else:
                base_confidence = "low"
            
            # Корректируем на основе рыночных условий
            if market_score < 30:
                # Плохие рыночные условия снижают уверенность
                confidence_levels = ["low", "medium", "high", "very_high"]
                current_index = confidence_levels.index(base_confidence)
                new_index = max(0, current_index - 1)
                base_confidence = confidence_levels[new_index]
            
            if volatility_is_high:
                # Высокая волатильность снижает уверенность
                confidence_levels = ["low", "medium", "high", "very_high"]
                current_index = confidence_levels.index(base_confidence)
                new_index = max(0, current_index - 1)
                base_confidence = confidence_levels[new_index]
            
            return base_confidence
            
        except Exception as e:
            logger.error(f"Error calculating confidence: {e}")
            return "low"
    
    def _generate_fallback_signals(self) -> Dict[str, Any]:
        """Генерация резервных сигналов при ошибке"""
        return {
            "base_signals": self._generate_mock_signals(),
            "weighted_signals": {"buy_score": 0.33, "sell_score": 0.33, "hold_score": 0.34, "net_score": 0.0},
            "filtered_signals": {"signal_strength": 0.0, "passes_filter": False},
            "final_signal": {"action": "HOLD", "confidence": "low", "score": 0.0, "reason": "Fallback signal"},
            "market_analysis": self.market_analyzer._generate_mock_analysis(),
            "adaptive_weights": self.base_weights,
            "signal_strength": 0.0,
            "confidence": "low",
            "timestamp": datetime.now().isoformat()
        }
    
    def get_signal_explanation(self, enhanced_signals: Dict[str, Any]) -> str:
        """Получение объяснения сигнала для пользователя"""
        try:
            final_signal = enhanced_signals.get("final_signal", {})
            market_analysis = enhanced_signals.get("market_analysis", {})
            filtered_signals = enhanced_signals.get("filtered_signals", {})
            
            action = final_signal.get("action", "HOLD")
            confidence = final_signal.get("confidence", "low")
            score = final_signal.get("score", 0.0)
            regime = market_analysis.get("regime", "unknown")
            signal_strength = filtered_signals.get("signal_strength", 0.0)
            
            explanation = f"🎯 Сигнал: {action} | Уверенность: {confidence.upper()} | Счет: {score:.2f}\n"
            explanation += f"📊 Рыночный режим: {regime} | Сила сигнала: {signal_strength:.1%}\n"
            explanation += f"💡 Причина: {final_signal.get('reason', 'Нет данных')}"
            
            return explanation
            
        except Exception as e:
            logger.error(f"Error generating signal explanation: {e}")
            return "Ошибка при генерации объяснения сигнала"
    
    def should_trade_enhanced(self, enhanced_signals: Dict[str, Any]) -> bool:
        """Улучшенная проверка необходимости торговли"""
        try:
            final_signal = enhanced_signals.get("final_signal", {})
            filtered_signals = enhanced_signals.get("filtered_signals", {})
            
            action = final_signal.get("action", "HOLD")
            confidence = final_signal.get("confidence", "low")
            passes_filter = filtered_signals.get("passes_filter", False)
            
            # Торгуем только если:
            # 1. Действие не HOLD
            # 2. Сигнал проходит фильтрацию
            # 3. Уверенность не низкая
            return (action != "HOLD" and 
                   passes_filter and 
                   confidence not in ["low"])
            
        except Exception as e:
            logger.error(f"Error in enhanced trade decision: {e}")
            return False 