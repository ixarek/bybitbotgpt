"""
Strategy Manager - Управление торговыми стратегиями
Централизованная система выбора и применения торговых режимов
"""

import asyncio
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime

from .trading_mode import TradingMode, ModeConfig, get_mode_config, TRADING_MODE_CONFIGS
from .signal_processor import SignalProcessor
from .enhanced_signal_processor import EnhancedSignalProcessor
from .market_analyzer import MarketAnalyzer
from .enhanced_risk_manager import EnhancedRiskManager
from ..utils.config import settings


logger = logging.getLogger(__name__)


class StrategyManager:
    """Менеджер торговых стратегий"""
    
    def __init__(self, signal_processor: SignalProcessor):
        self.signal_processor = signal_processor
        self.enhanced_signal_processor = EnhancedSignalProcessor()
        self.market_analyzer = MarketAnalyzer()
        self.enhanced_risk_manager = EnhancedRiskManager()
        
        self.current_mode = TradingMode.CONSERVATIVE  # По умолчанию консервативный режим
        self.mode_configs = TRADING_MODE_CONFIGS
        self.mode_switch_time = datetime.now()
        self._active_indicators = {}
        
        # Флаг для включения улучшенных функций
        self.use_enhanced_features = True
        
        logger.info(f"🎯 StrategyManager инициализирован с режимом: {self.current_mode.value}")
        logger.info(f"🔧 Улучшенные функции: {'ВКЛЮЧЕНЫ' if self.use_enhanced_features else 'ОТКЛЮЧЕНЫ'}")
    
    async def switch_mode(self, new_mode: TradingMode) -> Dict[str, Any]:
        """Переключение торгового режима"""
        try:
            old_mode = self.current_mode
            self.current_mode = new_mode
            self.mode_switch_time = datetime.now()
            
            # Получаем конфигурацию нового режима
            config = self.get_current_config()
            
            # Обновляем индикаторы в signal_processor
            await self._update_indicators(config)
            
            logger.info(f"Торговый режим изменен: {old_mode.value} → {new_mode.value}")
            
            return {
                "success": True,
                "old_mode": old_mode.value,
                "new_mode": new_mode.value,
                "switch_time": self.mode_switch_time.isoformat(),
                "config": self._config_to_dict(config)
            }
            
        except Exception as e:
            logger.error(f"Ошибка переключения режима: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def get_current_mode(self) -> TradingMode:
        """Получить текущий торговый режим"""
        return self.current_mode
    
    def get_current_config(self) -> ModeConfig:
        """Получить конфигурацию текущего режима"""
        return get_mode_config(self.current_mode)
    
    def get_mode_parameters(self, mode: Optional[TradingMode] = None) -> Dict[str, Any]:
        """Получить параметры режима"""
        target_mode = mode or self.current_mode
        config = get_mode_config(target_mode)
        
        return {
            "mode": target_mode.value,
            "name": config.name,
            "description": config.description,
            "risk_level": config.risk_level,
            "strategy_type": config.strategy_type,
            "timeframes": config.timeframes,
            "leverage_range": {
                "min": config.leverage_range[0],
                "max": config.leverage_range[1]
            },
            "tp_range": {
                "min": config.tp_range[0],
                "max": config.tp_range[1]
            },
            "sl_range": {
                "min": config.sl_range[0],
                "max": config.sl_range[1]
            },
            "trading_pairs": config.trading_pairs,
            "indicators": config.indicators,
            "is_current": target_mode == self.current_mode
        }
    
    def get_available_pairs(self, mode: Optional[TradingMode] = None) -> List[str]:
        """Получить доступные торговые пары для режима"""
        target_mode = mode or self.current_mode
        config = get_mode_config(target_mode)
        return config.trading_pairs
    
    def get_leverage_for_mode(self, mode: Optional[TradingMode] = None) -> float:
        """Получить рекомендуемое плечо для режима"""
        target_mode = mode or self.current_mode
        config = get_mode_config(target_mode)
        
        # Возвращаем среднее значение из диапазона
        min_lev, max_lev = config.leverage_range
        return (min_lev + max_lev) / 2
    
    def get_tp_sl_for_mode(self, mode: Optional[TradingMode] = None) -> Dict[str, float]:
        """Получить рекомендуемые TP/SL для режима"""
        target_mode = mode or self.current_mode
        config = get_mode_config(target_mode)
        
        return {
            "take_profit": (config.tp_range[0] + config.tp_range[1]) / 2,
            "stop_loss": (config.sl_range[0] + config.sl_range[1]) / 2
        }
    
    async def get_signals_for_mode(self, symbol: str, mode: Optional[TradingMode] = None) -> Dict[str, Any]:
        """Получить торговые сигналы для конкретного режима и символа"""
        target_mode = mode or self.current_mode
        config = get_mode_config(target_mode)
        
        # Конвертируем символ для сравнения (убираем "/")
        normalized_symbol = symbol.replace("/", "")
        normalized_pairs = [pair.replace("/", "") for pair in config.trading_pairs]
        
        # Проверяем, поддерживается ли символ в данном режиме
        if normalized_symbol not in normalized_pairs:
            return {
                "error": f"Символ {symbol} не поддерживается в режиме {config.name}",
                "supported_pairs": config.trading_pairs
            }
        
        # Получаем сигналы от signal_processor с учетом режима
        try:
            # ✅ ИСПРАВЛЕНИЕ: Используем правильный таймфрейм для каждого режима
            # Берём первый таймфрейм из списка режима
            timeframe = config.timeframes[0] if config.timeframes else "5m"
            
            # Конвертируем таймфрейм в формат, понятный SignalProcessor
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
            
            logger.info(f"🎯 Получение сигналов для {symbol} в режиме {config.name}")
            logger.info(f"📊 Таймфрейм режима: {timeframe} → API: {api_timeframe}")
            
            # Получаем базовые сигналы
            base_signals = self.signal_processor.get_signals(normalized_symbol, api_timeframe)
            
            # Создаем базовый результат
            result = {
                "signals": base_signals,
                "trading_mode": target_mode.value,
                "mode_name": config.name,
                "risk_level": config.risk_level,
                "strategy_type": config.strategy_type,
                "recommended_leverage": self.get_leverage_for_mode(target_mode),
                "recommended_tp_sl": self.get_tp_sl_for_mode(target_mode),
                "symbol": symbol,
                "timeframe": timeframe,
                "api_timeframe": api_timeframe,
                "timestamp": datetime.now().isoformat()
            }
            
            # Если включены улучшенные функции, добавляем их
            if self.use_enhanced_features:
                try:
                    # Получаем улучшенные сигналы
                    enhanced_signals = self.enhanced_signal_processor.get_enhanced_signals(
                        normalized_symbol, api_timeframe
                    )
                    
                    # Добавляем улучшенные данные в результат
                    result.update({
                        "enhanced_signals": enhanced_signals,
                        "market_analysis": enhanced_signals.get("market_analysis", {}),
                        "signal_strength": enhanced_signals.get("signal_strength", 0.0),
                        "confidence": enhanced_signals.get("confidence", "low"),
                        "final_signal": enhanced_signals.get("final_signal", {}),
                        "should_trade": self.enhanced_signal_processor.should_trade_enhanced(enhanced_signals),
                        "signal_explanation": self.enhanced_signal_processor.get_signal_explanation(enhanced_signals)
                    })
                    
                    logger.info(f"✅ Улучшенные сигналы получены для {symbol}")
                    
                except Exception as e:
                    logger.warning(f"⚠️ Error getting enhanced signals: {e}")
                    # Продолжаем с базовыми сигналами
            
            logger.info(f"✅ Generated signals: {len(base_signals)} indicators for {symbol} on {timeframe}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting signals for {symbol} in mode {target_mode.value}: {e}")
            return {
                "error": str(e),
                "symbol": symbol,
                "mode": target_mode.value
            }
    
    async def get_enhanced_position_info(self, symbol: str, signals: Dict[str, Any], 
                                       current_price: float, account_balance: float = 1000.0) -> Dict[str, Any]:
        """Получение улучшенной информации о позиции"""
        try:
            if not self.use_enhanced_features:
                return {"error": "Enhanced features are disabled"}
            
            # Получаем улучшенный расчет размера позиции
            position_info = await self.enhanced_risk_manager.calculate_enhanced_position_size(
                symbol, signals, current_price, account_balance
            )
            
            # Добавляем рекомендации по трейлинг-стопам
            market_analysis = position_info.get("market_analysis", {})
            
            # Рекомендуемые параметры трейлинг-стопа
            trailing_recommendations = self._get_trailing_stop_recommendations(market_analysis)
            
            position_info.update({
                "trailing_stop_recommendations": trailing_recommendations,
                "enhanced_features": True
            })
            
            return position_info
            
        except Exception as e:
            logger.error(f"Error getting enhanced position info: {e}")
            return {"error": str(e)}
    
    def _get_trailing_stop_recommendations(self, market_analysis: Dict) -> Dict[str, Any]:
        """Получение рекомендаций по трейлинг-стопам"""
        try:
            if not settings.trailing_stop_enabled:
                return {}
            regime = market_analysis.get("regime", "sideways")
            volatility = market_analysis.get("volatility", {})
            vol_level = volatility.get("level", "medium")
            
            # Рекомендации по типу стопа
            if regime in ["trending_up", "trending_down"]:
                recommended_type = "trailing"
                distance_multiplier = 1.0
            elif regime == "high_volatility":
                recommended_type = "atr_based"
                distance_multiplier = 1.5
            elif vol_level in ["very_low", "low"]:
                recommended_type = "percentage"
                distance_multiplier = 0.8
            else:
                recommended_type = "trailing"
                distance_multiplier = 1.0
            
            # Рекомендуемая дистанция
            base_distance = 0.02  # 2%
            recommended_distance = base_distance * distance_multiplier
            
            return {
                "recommended_type": recommended_type,
                "recommended_distance": recommended_distance,
                "distance_multiplier": distance_multiplier,
                "reasoning": f"Based on {regime} market regime and {vol_level} volatility",
                "market_regime": regime,
                "volatility_level": vol_level
            }
            
        except Exception as e:
            logger.error(f"Error getting trailing stop recommendations: {e}")
            return {
                "recommended_type": "trailing",
                "recommended_distance": 0.02,
                "reasoning": "Default recommendations due to error"
            }
    
    def get_market_summary(self, symbol: str) -> str:
        """Получение краткого резюме рыночных условий"""
        try:
            if not self.use_enhanced_features:
                return "Улучшенные функции отключены"
            
            return self.market_analyzer.get_market_conditions_summary(symbol)
            
        except Exception as e:
            logger.error(f"Error getting market summary: {e}")
            return "Ошибка получения рыночной сводки"
    
    def get_mode_statistics(self) -> Dict[str, Any]:
        """Получить статистику по режимам"""
        base_stats = {
            "current_mode": self.current_mode.value,
            "mode_switch_time": self.mode_switch_time.isoformat(),
            "available_modes": len(self.mode_configs),
            "total_trading_pairs": sum(len(config.trading_pairs) for config in self.mode_configs.values()),
            "enhanced_features_enabled": self.use_enhanced_features,
            "modes_info": {
                mode.value: {
                    "name": config.name,
                    "pairs_count": len(config.trading_pairs),
                    "indicators_count": len(config.indicators),
                    "risk_level": config.risk_level
                }
                for mode, config in self.mode_configs.items()
            }
        }
        
        # Добавляем статистику по улучшенным функциям
        if self.use_enhanced_features:
            try:
                risk_summary = self.enhanced_risk_manager.get_risk_summary()
                base_stats["enhanced_risk_stats"] = risk_summary
            except Exception as e:
                logger.warning(f"Could not get enhanced risk stats: {e}")
        
        return base_stats
    
    def toggle_enhanced_features(self, enabled: bool) -> Dict[str, Any]:
        """Включение/отключение улучшенных функций"""
        old_state = self.use_enhanced_features
        self.use_enhanced_features = enabled
        
        logger.info(f"🔧 Улучшенные функции: {'ВКЛЮЧЕНЫ' if enabled else 'ОТКЛЮЧЕНЫ'}")
        
        return {
            "success": True,
            "old_state": old_state,
            "new_state": enabled,
            "timestamp": datetime.now().isoformat()
        }
    
    async def _update_indicators(self, config: ModeConfig):
        """Обновить индикаторы в signal_processor согласно конфигурации режима"""
        try:
            # Здесь будет логика обновления индикаторов в SignalProcessor
            # Пока что просто логируем
            logger.info(f"Updating indicators for mode {config.name}")
            logger.info(f"Indicators: {list(config.indicators.keys())}")
            
            self._active_indicators = config.indicators
            
        except Exception as e:
            logger.error(f"Error updating indicators: {e}")
    
    def _config_to_dict(self, config: ModeConfig) -> Dict[str, Any]:
        """Конвертация ModeConfig в словарь для API"""
        return {
            "name": config.name,
            "description": config.description,
            "timeframes": config.timeframes,
            "indicators": config.indicators,
            "leverage_range": config.leverage_range,
            "tp_range": config.tp_range,
            "sl_range": config.sl_range,
            "trading_pairs": config.trading_pairs,
            "risk_level": config.risk_level,
            "strategy_type": config.strategy_type
        }
    
    async def get_enhanced_signals_async(self, symbol: str, timeframe: str) -> Dict[str, Any]:
        """
        Получить улучшенные сигналы асинхронно
        """
        try:
            if not self.use_enhanced_features:
                # Возвращаем базовые сигналы
                base_signals = self.signal_processor.get_signals(symbol, timeframe)
                return {
                    "signals": base_signals,
                    "signal_strength": "medium",
                    "confidence": "medium",
                    "market_regime": "unknown",
                    "explanation": "Enhanced features disabled"
                }
            
            # Получаем базовые сигналы
            base_signals = self.signal_processor.get_signals(symbol, timeframe)
            
            # Получаем улучшенные сигналы
            enhanced_signals = self.enhanced_signal_processor.get_enhanced_signals(symbol, timeframe)
            
            # Анализируем рынок
            market_analysis = self.market_analyzer.analyze_market(symbol, timeframe)
            
            return {
                "signals": enhanced_signals.get("signals", base_signals),
                "signal_strength": enhanced_signals.get("signal_strength", "medium"),
                "confidence": enhanced_signals.get("confidence", "medium"),
                "market_regime": market_analysis.get("regime", "unknown"),
                "explanation": enhanced_signals.get("explanation", "Enhanced signals processed")
            }
            
        except Exception as e:
            logger.error(f"Error getting enhanced signals for {symbol}: {e}")
            # Fallback к базовым сигналам
            base_signals = self.signal_processor.get_signals(symbol, timeframe)
            return {
                "signals": base_signals,
                "signal_strength": "unknown",
                "confidence": "low",
                "market_regime": "unknown",
                "explanation": f"Error: {str(e)}"
            } 