"""
Configuration management for Bybit Trading Bot
Uses pydantic-settings for type-safe configuration
"""

from pydantic_settings import BaseSettings
from pydantic import Field
from typing import List, Optional
import os


class Settings(BaseSettings):
    """
    Application settings with environment variable support
    """
    
    # Application
    app_name: str = "Bybit Trading Bot"
    version: str = "1.0.0"
    debug: bool = False
    
    # Server
    host: str = "0.0.0.0"
    port: int = 5000
    
    # Bybit API Configuration
    bybit_api_key: Optional[str] = Field(None, description="Bybit API Key")
    bybit_api_secret: Optional[str] = Field(None, description="Bybit API Secret")
    bybit_testnet: bool = Field(True, description="Use Bybit testnet")
    bybit_demo: bool = Field(False, description="Use Bybit demo account (real prices, virtual money)")
    
    # Trading Configuration
    trading_pairs: List[str] = Field(
        default=["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"],
        description="Trading pairs to monitor"
    )
    
    # Risk Management
    risk_mode: str = Field(
        default="conservative",
        description="Risk mode: conservative"
    )
    max_position_size: float = Field(
        default=100.0,
        description="Maximum position size in USDT"
    )
    
    # Technical Indicators
    rsi_period: int = 14
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9
    bollinger_period: int = 20
    bollinger_std: float = 2.0
    sma_period: int = 50
    ema_period: int = 21
    atr_period: int = 14
    adx_period: int = 14
    stochastic_k: int = 14
    stochastic_d: int = 3
    williams_period: int = 14
    mfi_period: int = 14
    psar_step: float = 0.02
    psar_max: float = 0.2
    
    # Signal Processing
    signal_confirmation_count: int = Field(
        default=5,
        description="Number of indicators needed for signal confirmation"
    )
    
    # WebSocket
    websocket_ping_interval: int = 30
    websocket_ping_timeout: int = 10
    
    # Database
    database_url: str = "sqlite:///./trading_bot.db"
    
    # Redis
    redis_url: str = "redis://localhost:6379"
    redis_db: int = 0
    
    # Shutdown behavior
    close_positions_on_shutdown: bool = Field(
        default=False,
        description="Close all open positions when the bot shuts down"
    )
    
    # Logging
    log_level: str = "INFO"
    log_file: Optional[str] = "logs/trading_bot.log"
    
    model_config = {
        "env_file": "config.env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
        "extra": "ignore"
    }


# Global settings instance - инициализируем безопасно
try:
    settings = Settings()
    # Принудительно подхватываем TRADING_PAIRS из переменной окружения, если она задана
    env_pairs = os.getenv('TRADING_PAIRS')
    if env_pairs:
        # Удаляем пробелы и разбиваем по запятой
        settings.trading_pairs = [p.strip() for p in env_pairs.split(',') if p.strip()]
except Exception as e:
    print(f"Warning: Could not load config.env file: {e}")
    settings = Settings(_env_file=None)  # Fallback без .env файла


# Risk mode configurations
RISK_MODES = {
    "conservative": {
        "timeframe": "5",
        "min_signals": 6,
        "position_size_multiplier": 0.5,
        "stop_loss_pct": 1.0,
        "take_profit_pct": 2.0
    }
}


def get_risk_config(mode: str = None) -> dict:
    """Get risk configuration for the specified mode"""
    mode = mode or settings.risk_mode
    return RISK_MODES.get(mode, RISK_MODES["conservative"]) 