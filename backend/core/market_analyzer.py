"""
Market Analyzer for Bybit Trading Bot
Анализирует рыночные условия для оптимизации торговых стратегий
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
import logging
from datetime import datetime, timedelta
from enum import Enum

logger = logging.getLogger(__name__)


class MarketRegime(Enum):
    """Типы рыночных режимов"""
    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    SIDEWAYS = "sideways"
    HIGH_VOLATILITY = "high_volatility"
    LOW_VOLATILITY = "low_volatility"
    BREAKOUT = "breakout"
    CONSOLIDATION = "consolidation"


class VolatilityLevel(Enum):
    """Уровни волатильности"""
    VERY_LOW = "very_low"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"


class MarketAnalyzer:
    """
    Анализатор рыночных условий
    Определяет тренд, волатильность, объемы и другие рыночные характеристики
    """
    
    def __init__(self):
        self.analysis_cache = {}
        self.last_update = {}
        self.cache_duration = 60  # секунд
        
        # Пороговые значения для определения режимов
        self.trend_threshold = 0.02  # 2% для определения тренда
        self.volatility_thresholds = {
            VolatilityLevel.VERY_LOW: 0.01,
            VolatilityLevel.LOW: 0.02,
            VolatilityLevel.MEDIUM: 0.04,
            VolatilityLevel.HIGH: 0.08,
            VolatilityLevel.VERY_HIGH: 0.15
        }
        
        logger.info("🔍 Market Analyzer initialized")
    
    def analyze_market(self, symbol: str, timeframe: str = "5") -> Dict:
        """
        Комплексный анализ рыночных условий
        """
        try:
            # Проверяем кэш
            cache_key = f"{symbol}_{timeframe}"
            if self._is_cached(cache_key):
                logger.debug(f"Using cached market analysis for {symbol}")
                return self.analysis_cache[cache_key]
            
            # Получаем данные
            from backend.integrations.bybit_client import bybit_client
            if bybit_client is None:
                logger.warning("Bybit client not available, using mock analysis")
                return self._generate_mock_analysis()
            
            df = bybit_client.get_kline(symbol, timeframe, limit=200)
            if df is None or df.empty or len(df) < 50:
                logger.warning(f"Insufficient data for {symbol}, using mock analysis")
                return self._generate_mock_analysis()
            
            # Проводим анализ
            analysis = self._perform_analysis(df)
            analysis["symbol"] = symbol
            analysis["timeframe"] = timeframe
            analysis["timestamp"] = datetime.now().isoformat()
            
            # Сохраняем в кэш
            self.analysis_cache[cache_key] = analysis
            self.last_update[cache_key] = datetime.now()
            
            logger.info(f"✅ Market analysis completed for {symbol}: {analysis['regime']}")
            return analysis
            
        except Exception as e:
            logger.error(f"❌ Error analyzing market for {symbol}: {e}")
            return self._generate_mock_analysis()
    
    def _perform_analysis(self, df: pd.DataFrame) -> Dict:
        """Выполняет комплексный анализ рыночных данных"""
        close = df['close']
        high = df['high']
        low = df['low']
        volume = df['volume']
        
        # 1. Анализ тренда
        trend_analysis = self._analyze_trend(close)
        
        # 2. Анализ волатильности
        volatility_analysis = self._analyze_volatility(high, low, close)
        
        # 3. Анализ объемов
        volume_analysis = self._analyze_volume(volume, close)
        
        # 4. Определение режима рынка
        market_regime = self._determine_market_regime(trend_analysis, volatility_analysis)
        
        # 5. Анализ поддержки/сопротивления
        support_resistance = self._analyze_support_resistance(high, low, close)
        
        # 6. Расчет силы тренда
        trend_strength = self._calculate_trend_strength(close)
        
        return {
            "regime": market_regime.value,
            "trend": trend_analysis,
            "volatility": volatility_analysis,
            "volume": volume_analysis,
            "support_resistance": support_resistance,
            "trend_strength": trend_strength,
            "market_score": self._calculate_market_score(trend_analysis, volatility_analysis, volume_analysis),
            "trading_recommendation": self._get_trading_recommendation(market_regime, trend_analysis, volatility_analysis)
        }
    
    def _analyze_trend(self, close: pd.Series) -> Dict:
        """Анализ тренда"""
        try:
            # Скользящие средние разных периодов
            sma_20 = close.rolling(20).mean()
            sma_50 = close.rolling(50).mean()
            sma_100 = close.rolling(100).mean()
            
            current_price = close.iloc[-1]
            sma_20_val = sma_20.iloc[-1]
            sma_50_val = sma_50.iloc[-1]
            sma_100_val = sma_100.iloc[-1]
            
            # Определение направления тренда
            if current_price > sma_20_val > sma_50_val > sma_100_val:
                direction = "up"
                strength = "strong"
            elif current_price < sma_20_val < sma_50_val < sma_100_val:
                direction = "down"
                strength = "strong"
            elif current_price > sma_20_val > sma_50_val:
                direction = "up"
                strength = "medium"
            elif current_price < sma_20_val < sma_50_val:
                direction = "down"
                strength = "medium"
            elif current_price > sma_20_val:
                direction = "up"
                strength = "weak"
            elif current_price < sma_20_val:
                direction = "down"
                strength = "weak"
            else:
                direction = "sideways"
                strength = "none"
            
            # Расчет угла тренда
            if len(sma_20) >= 10:
                recent_sma = sma_20.iloc[-10:]
                trend_angle = np.polyfit(range(len(recent_sma)), recent_sma, 1)[0]
                trend_angle_pct = (trend_angle / current_price) * 100
            else:
                trend_angle_pct = 0
            
            return {
                "direction": direction,
                "strength": strength,
                "angle": trend_angle_pct,
                "sma_20": sma_20_val,
                "sma_50": sma_50_val,
                "sma_100": sma_100_val,
                "current_price": current_price
            }
            
        except Exception as e:
            logger.error(f"Error in trend analysis: {e}")
            return {"direction": "sideways", "strength": "none", "angle": 0}
    
    def _analyze_volatility(self, high: pd.Series, low: pd.Series, close: pd.Series) -> Dict:
        """Анализ волатильности"""
        try:
            # ATR (Average True Range)
            atr = self._calculate_atr(high, low, close, 14)
            current_atr = atr.iloc[-1] if len(atr) > 0 else 0
            
            # Волатильность в процентах
            volatility_pct = (current_atr / close.iloc[-1]) * 100
            
            # Определение уровня волатильности
            volatility_level = VolatilityLevel.MEDIUM
            for level, threshold in self.volatility_thresholds.items():
                if volatility_pct <= threshold:
                    volatility_level = level
                    break
            
            # Историческая волатильность (стандартное отклонение доходности)
            returns = close.pct_change().dropna()
            historical_vol = returns.std() * np.sqrt(len(returns))
            
            # Сравнение с исторической волатильностью
            vol_percentile = (volatility_pct / (historical_vol * 100)) if historical_vol > 0 else 1
            
            return {
                "level": volatility_level.value,
                "atr": current_atr,
                "percentage": volatility_pct,
                "historical": historical_vol * 100,
                "percentile": vol_percentile,
                "is_high": volatility_pct > 0.04,  # Высокая волатильность > 4%
                "is_increasing": self._is_volatility_increasing(atr)
            }
            
        except Exception as e:
            logger.error(f"Error in volatility analysis: {e}")
            return {"level": "medium", "percentage": 2.0, "is_high": False}
    
    def _analyze_volume(self, volume: pd.Series, close: pd.Series) -> Dict:
        """Анализ объемов"""
        try:
            # Средний объем за разные периоды
            avg_volume_20 = volume.rolling(20).mean()
            avg_volume_50 = volume.rolling(50).mean()
            
            current_volume = volume.iloc[-1]
            avg_20 = avg_volume_20.iloc[-1]
            avg_50 = avg_volume_50.iloc[-1]
            
            # Относительный объем
            volume_ratio_20 = current_volume / avg_20 if avg_20 > 0 else 1
            volume_ratio_50 = current_volume / avg_50 if avg_50 > 0 else 1
            
            # Определение уровня объема
            if volume_ratio_20 > 2.0:
                volume_level = "very_high"
            elif volume_ratio_20 > 1.5:
                volume_level = "high"
            elif volume_ratio_20 > 0.8:
                volume_level = "normal"
            elif volume_ratio_20 > 0.5:
                volume_level = "low"
            else:
                volume_level = "very_low"
            
            # Анализ объема с ценой (OBV упрощенный)
            price_change = close.pct_change()
            volume_price_correlation = price_change.corr(volume.pct_change())
            
            return {
                "level": volume_level,
                "current": current_volume,
                "avg_20": avg_20,
                "avg_50": avg_50,
                "ratio_20": volume_ratio_20,
                "ratio_50": volume_ratio_50,
                "price_correlation": volume_price_correlation if not pd.isna(volume_price_correlation) else 0,
                "is_high": volume_ratio_20 > 1.5,
                "is_increasing": self._is_volume_increasing(volume)
            }
            
        except Exception as e:
            logger.error(f"Error in volume analysis: {e}")
            return {"level": "normal", "ratio_20": 1.0, "is_high": False}
    
    def _determine_market_regime(self, trend_analysis: Dict, volatility_analysis: Dict) -> MarketRegime:
        """Определение режима рынка"""
        trend_direction = trend_analysis.get("direction", "sideways")
        trend_strength = trend_analysis.get("strength", "none")
        volatility_level = volatility_analysis.get("level", "medium")
        is_high_vol = volatility_analysis.get("is_high", False)
        
        # Логика определения режима
        if is_high_vol:
            if trend_direction in ["up", "down"] and trend_strength in ["strong", "medium"]:
                return MarketRegime.BREAKOUT
            else:
                return MarketRegime.HIGH_VOLATILITY
        
        if trend_direction == "up" and trend_strength in ["strong", "medium"]:
            return MarketRegime.TRENDING_UP
        elif trend_direction == "down" and trend_strength in ["strong", "medium"]:
            return MarketRegime.TRENDING_DOWN
        elif volatility_level in ["very_low", "low"]:
            return MarketRegime.CONSOLIDATION
        else:
            return MarketRegime.SIDEWAYS
    
    def _analyze_support_resistance(self, high: pd.Series, low: pd.Series, close: pd.Series) -> Dict:
        """Анализ уровней поддержки и сопротивления"""
        try:
            current_price = close.iloc[-1]
            
            # Простой алгоритм поиска уровней
            recent_highs = high.rolling(10).max().dropna()
            recent_lows = low.rolling(10).min().dropna()
            
            # Находим ближайшие уровни
            resistance_levels = recent_highs[recent_highs > current_price].tail(3).tolist()
            support_levels = recent_lows[recent_lows < current_price].tail(3).tolist()
            
            # Ближайшие уровни
            nearest_resistance = min(resistance_levels) if resistance_levels else current_price * 1.05
            nearest_support = max(support_levels) if support_levels else current_price * 0.95
            
            return {
                "nearest_resistance": nearest_resistance,
                "nearest_support": nearest_support,
                "resistance_distance": ((nearest_resistance - current_price) / current_price) * 100,
                "support_distance": ((current_price - nearest_support) / current_price) * 100,
                "all_resistance": resistance_levels,
                "all_support": support_levels
            }
            
        except Exception as e:
            logger.error(f"Error in support/resistance analysis: {e}")
            current_price = close.iloc[-1] if len(close) > 0 else 100
            return {
                "nearest_resistance": current_price * 1.05,
                "nearest_support": current_price * 0.95,
                "resistance_distance": 5.0,
                "support_distance": 5.0
            }
    
    def _calculate_trend_strength(self, close: pd.Series) -> float:
        """Расчет силы тренда (0-100)"""
        try:
            # Используем ADX-подобный расчет
            if len(close) < 20:
                return 50.0
            
            # Расчет направленного движения
            high_diff = close.diff()
            low_diff = -close.diff()
            
            plus_dm = high_diff.where(high_diff > low_diff, 0)
            minus_dm = low_diff.where(low_diff > high_diff, 0)
            
            # Сглаживание
            plus_di = plus_dm.rolling(14).mean()
            minus_di = minus_dm.rolling(14).mean()
            
            # Расчет силы тренда
            dx = abs(plus_di - minus_di) / (plus_di + minus_di) * 100
            strength = dx.rolling(14).mean().iloc[-1]
            
            return min(max(strength, 0), 100) if not pd.isna(strength) else 50.0
            
        except Exception as e:
            logger.error(f"Error calculating trend strength: {e}")
            return 50.0
    
    def _calculate_market_score(self, trend_analysis: Dict, volatility_analysis: Dict, volume_analysis: Dict) -> float:
        """Расчет общего рыночного счета (0-100)"""
        try:
            score = 50.0  # Базовый счет
            
            # Бонусы за тренд
            if trend_analysis.get("strength") == "strong":
                score += 20
            elif trend_analysis.get("strength") == "medium":
                score += 10
            
            # Корректировка за волатильность
            if volatility_analysis.get("level") in ["very_high", "high"]:
                score -= 10  # Высокая волатильность - риск
            elif volatility_analysis.get("level") in ["very_low", "low"]:
                score += 5   # Низкая волатильность - стабильность
            
            # Бонусы за объем
            if volume_analysis.get("is_high"):
                score += 10  # Высокий объем - подтверждение
            elif volume_analysis.get("level") == "very_low":
                score -= 5   # Низкий объем - слабость
            
            return min(max(score, 0), 100)
            
        except Exception as e:
            logger.error(f"Error calculating market score: {e}")
            return 50.0
    
    def _get_trading_recommendation(self, regime: MarketRegime, trend_analysis: Dict, volatility_analysis: Dict) -> Dict:
        """Получение торговых рекомендаций"""
        recommendations = {
            "strategy": "neutral",
            "risk_level": "medium",
            "position_size_multiplier": 1.0,
            "preferred_timeframes": ["5m", "15m"],
            "avoid_trading": False,
            "notes": []
        }
        
        # Рекомендации по режимам
        if regime == MarketRegime.TRENDING_UP:
            recommendations.update({
                "strategy": "trend_following",
                "risk_level": "low",
                "position_size_multiplier": 1.2,
                "preferred_timeframes": ["15m", "30m"],
                "notes": ["Благоприятные условия для лонгов", "Следуйте тренду"]
            })
        elif regime == MarketRegime.TRENDING_DOWN:
            recommendations.update({
                "strategy": "trend_following",
                "risk_level": "low",
                "position_size_multiplier": 1.2,
                "preferred_timeframes": ["15m", "30m"],
                "notes": ["Благоприятные условия для шортов", "Следуйте тренду"]
            })
        elif regime == MarketRegime.HIGH_VOLATILITY:
            recommendations.update({
                "strategy": "scalping",
                "risk_level": "high",
                "position_size_multiplier": 0.7,
                "preferred_timeframes": ["1m", "5m"],
                "notes": ["Высокая волатильность", "Сократите размер позиций"]
            })
        elif regime == MarketRegime.CONSOLIDATION:
            recommendations.update({
                "strategy": "range_trading",
                "risk_level": "medium",
                "position_size_multiplier": 0.9,
                "preferred_timeframes": ["5m", "15m"],
                "notes": ["Торговля в диапазоне", "Используйте поддержку/сопротивление"]
            })
        elif regime == MarketRegime.BREAKOUT:
            recommendations.update({
                "strategy": "breakout",
                "risk_level": "medium",
                "position_size_multiplier": 1.1,
                "preferred_timeframes": ["5m", "15m"],
                "notes": ["Возможен пробой", "Готовьтесь к быстрым движениям"]
            })
        
        # Дополнительные корректировки
        if volatility_analysis.get("is_high"):
            recommendations["risk_level"] = "high"
            recommendations["position_size_multiplier"] *= 0.8
            recommendations["notes"].append("Снижен размер позиций из-за высокой волатильности")
        
        return recommendations
    
    def _calculate_atr(self, high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
        """Расчет ATR"""
        high_low = high - low
        high_close = np.abs(high - close.shift())
        low_close = np.abs(low - close.shift())
        true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        return true_range.rolling(window=period).mean()
    
    def _is_volatility_increasing(self, atr: pd.Series) -> bool:
        """Проверка роста волатильности"""
        if len(atr) < 5:
            return False
        return atr.iloc[-1] > atr.iloc[-5]
    
    def _is_volume_increasing(self, volume: pd.Series) -> bool:
        """Проверка роста объема"""
        if len(volume) < 5:
            return False
        recent_avg = volume.iloc[-5:].mean()
        older_avg = volume.iloc[-10:-5].mean()
        return recent_avg > older_avg
    
    def _is_cached(self, cache_key: str) -> bool:
        """Проверка актуальности кэша"""
        if cache_key not in self.analysis_cache or cache_key not in self.last_update:
            return False
        
        time_diff = (datetime.now() - self.last_update[cache_key]).seconds
        return time_diff < self.cache_duration
    
    def _generate_mock_analysis(self) -> Dict:
        """Генерация моковых данных для анализа"""
        import random
        
        regimes = list(MarketRegime)
        selected_regime = random.choice(regimes)
        
        return {
            "regime": selected_regime.value,
            "trend": {
                "direction": random.choice(["up", "down", "sideways"]),
                "strength": random.choice(["strong", "medium", "weak", "none"]),
                "angle": random.uniform(-2, 2)
            },
            "volatility": {
                "level": random.choice([v.value for v in VolatilityLevel]),
                "percentage": random.uniform(1, 8),
                "is_high": random.choice([True, False])
            },
            "volume": {
                "level": random.choice(["very_low", "low", "normal", "high", "very_high"]),
                "ratio_20": random.uniform(0.5, 2.5),
                "is_high": random.choice([True, False])
            },
            "support_resistance": {
                "resistance_distance": random.uniform(1, 10),
                "support_distance": random.uniform(1, 10)
            },
            "trend_strength": random.uniform(20, 80),
            "market_score": random.uniform(30, 80),
            "trading_recommendation": {
                "strategy": random.choice(["trend_following", "range_trading", "scalping", "breakout"]),
                "risk_level": random.choice(["low", "medium", "high"]),
                "position_size_multiplier": random.uniform(0.7, 1.3),
                "notes": ["Mock analysis data"]
            },
            "symbol": "MOCK",
            "timeframe": "5m",
            "timestamp": datetime.now().isoformat()
        }
    
    def get_market_conditions_summary(self, symbol: str, timeframe: str = "5") -> str:
        """Получение краткого резюме рыночных условий"""
        analysis = self.analyze_market(symbol, timeframe)
        
        regime = analysis.get("regime", "unknown")
        trend = analysis.get("trend", {})
        volatility = analysis.get("volatility", {})
        score = analysis.get("market_score", 50)
        
        trend_dir = trend.get("direction", "sideways")
        trend_str = trend.get("strength", "none")
        vol_level = volatility.get("level", "medium")
        
        return f"{regime.upper()} | Тренд: {trend_dir} ({trend_str}) | Волатильность: {vol_level} | Счет: {score:.0f}/100" 