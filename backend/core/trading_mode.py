"""
Trading Mode Definitions and Configuration
Определения торговых режимов и их конфигурация
"""

from enum import Enum
from dataclasses import dataclass
from typing import List, Dict, Any, Tuple


class TradingMode(Enum):
    """Торговые режимы с разными уровнями риска"""
    AGGRESSIVE = "aggressive"
    MEDIUM = "medium"
    CONSERVATIVE = "conservative"


@dataclass
class ModeConfig:
    """Конфигурация торгового режима"""
    name: str
    description: str
    timeframes: List[str]
    indicators: Dict[str, Any]
    leverage_range: Tuple[float, float]
    tp_range: Tuple[float, float]  # Take Profit range
    sl_range: Tuple[float, float]  # Stop Loss range
    trading_pairs: List[str]
    risk_level: str
    strategy_type: str


# Конфигурации для каждого режима
TRADING_MODE_CONFIGS = {
    TradingMode.AGGRESSIVE: ModeConfig(
        name="Агрессивный",
        description="Скальпинг + Event-driven торговля",
        timeframes=["1m", "5m"],
        indicators={
            "rsi": [{"period": 7}, {"period": 14}],
            "ema": [{"period": 9}, {"period": 21}],
            "macd": [{"fast": 12, "slow": 26, "signal": 9}],
            "volume": [{"period": 20}],
            "atr": [{"period": 7}]
        },
        leverage_range=(10.0, 20.0),
        tp_range=(5.0, 5.0),  # 5%
        sl_range=(3.0, 3.0),  # 3%
        trading_pairs=["BTC/USDT", "ETH/USDT", "SOL/USDT", "DOGE/USDT", "XRP/USDT"],
        risk_level="HIGH",
        strategy_type="SCALPING"
    ),
    
    TradingMode.MEDIUM: ModeConfig(
        name="Средний",
        description="Moving Average Crossover + Trend Following",
        timeframes=["15m", "1h"],
        indicators={
            "ema": [{"period": 20}, {"period": 50}, {"period": 200}],
            "rsi": [{"period": 14}],
            "bollinger_bands": [{"period": 20, "std": 2}],
            "stochastic": [{"k_period": 14, "d_period": 3, "smooth": 3}],
            "volume": [{"period": 20}]
        },
        leverage_range=(3.0, 5.0),
        tp_range=(5.0, 5.0),  # 5%
        sl_range=(3.0, 3.0),  # 3%
        trading_pairs=["BTC/USDT", "ETH/USDT", "BNB/USDT", "SOL/USDT", "ADA/USDT"],
        risk_level="MEDIUM",
        strategy_type="TREND_FOLLOWING"
    ),
    
    TradingMode.CONSERVATIVE: ModeConfig(
        name="Консервативный", 
        description="DCA + Long-term Trend",
        timeframes=["4h", "1d"],
        indicators={
            "sma": [{"period": 50}, {"period": 200}],
            "rsi": [{"period": 14}],
            "support_resistance": [{"lookback": 50}],
            "volume": [{"period": 50}]
        },
        leverage_range=(1.0, 1.0),  # Без плеча
        tp_range=(5.0, 5.0),  # 5%
        sl_range=(3.0, 3.0),  # 3%
        trading_pairs=["BTC/USDT", "ETH/USDT", "SOL/USDT"],
        risk_level="LOW",
        strategy_type="DCA"
    )
}


def get_mode_config(mode: TradingMode) -> ModeConfig:
    """Получить конфигурацию для указанного режима"""
    return TRADING_MODE_CONFIGS[mode]


def get_available_modes() -> List[Dict[str, Any]]:
    """Получить список доступных режимов для API"""
    return [
        {
            "mode": mode.value,
            "name": config.name,
            "description": config.description,
            "risk_level": config.risk_level,
            "strategy_type": config.strategy_type,
            "trading_pairs": config.trading_pairs,
            "timeframes": config.timeframes
        }
        for mode, config in TRADING_MODE_CONFIGS.items()
    ]


def validate_mode(mode_str: str) -> TradingMode:
    """Валидация и конвертация строки в TradingMode"""
    try:
        return TradingMode(mode_str.lower())
    except ValueError:
        raise ValueError(f"Неподдерживаемый торговый режим: {mode_str}") 