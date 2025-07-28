"""
Risk Manager for Bybit Trading Bot
Handles position sizing, risk assessment, and trade validation
"""

from typing import Dict, Optional
from datetime import datetime
import pandas as pd

from ..utils.config import settings, get_risk_config


class RiskManager:
    """
    Manages trading risks and position sizing
    """
    
    def __init__(self):
        self.mode = settings.risk_mode
        self.max_positions = 4  # Maximum simultaneous positions
        self.max_daily_trades = 20  # Maximum trades per day
        self.daily_trade_count = 0
        self.last_trade_date = datetime.now().date()
        
        # Risk tracking
        self.daily_pnl = 0.0
        self.max_drawdown = 0.0
        
    async def initialize(self):
        """Initialize risk manager"""
        print("🛡️ Risk Manager initialized")
        
    async def should_trade(self, symbol: str, signals: Dict[str, str], current_price: float) -> bool:
        """
        Determine if we should execute a trade based on risk parameters
        """
        try:
            # Calculate signal strength
            buy_count = sum(1 for signal in signals.values() if signal == "BUY")
            sell_count = sum(1 for signal in signals.values() if signal == "SELL")
            total_signals = len(signals)
            
            risk_config = get_risk_config()
            min_signals = risk_config["min_signals"]
            
            # Check if we have enough signals for a trade
            if buy_count < min_signals and sell_count < min_signals:
                return False
            
            # Calculate confidence
            if buy_count >= sell_count:
                confidence = buy_count / total_signals
            else:
                confidence = sell_count / total_signals
            
            # Check confidence level
            if confidence < 0.5:  # Minimum 50% confidence
                return False
            
            # Check daily trade limit
            today = datetime.now().date()
            if today != self.last_trade_date:
                self.daily_trade_count = 0
                self.last_trade_date = today
            
            if self.daily_trade_count >= self.max_daily_trades:
                print(f"⚠️ Daily trade limit reached ({self.max_daily_trades})")
                return False
            
            return True
            
        except Exception as e:
            print(f"❌ Error in risk assessment: {e}")
            return False
    
    async def calculate_position_size(
        self, 
        symbol: str, 
        signals: Dict[str, str], 
        current_price: float
    ) -> float:
        """
        Calculate position size based on risk parameters
        """
        try:
            risk_config = get_risk_config()
            base_position_size = settings.max_position_size
            
            # Apply risk mode multiplier
            position_multiplier = risk_config["position_size_multiplier"]
            adjusted_size = base_position_size * position_multiplier
            
            # Calculate confidence
            buy_count = sum(1 for signal in signals.values() if signal == "BUY")
            sell_count = sum(1 for signal in signals.values() if signal == "SELL")
            total_signals = len(signals)
            
            if buy_count >= sell_count:
                confidence = buy_count / total_signals
            else:
                confidence = sell_count / total_signals
            
            # Adjust based on signal confidence
            confidence_multiplier = min(confidence, 1.0)
            final_size = adjusted_size * confidence_multiplier
            
            # Convert USDT to quantity (simplified)
            if current_price > 0:
                quantity = final_size / current_price
                
                # Round to appropriate decimal places
                if symbol in ["BTCUSDT", "ETHUSDT"]:
                    quantity = round(quantity, 4)
                else:
                    quantity = round(quantity, 2)
                
                return max(quantity, 0.001)  # Minimum order size
            
            return 0.0
            
        except Exception as e:
            print(f"❌ Error calculating position size: {e}")
            return 0.0
    
    def update_trade_count(self):
        """Update daily trade count"""
        self.daily_trade_count += 1
    
    def get_risk_status(self) -> Dict:
        """Get current risk status"""
        return {
            "daily_trades": self.daily_trade_count,
            "max_daily_trades": self.max_daily_trades,
            "daily_pnl": self.daily_pnl,
            "max_drawdown": self.max_drawdown,
            "risk_mode": self.mode
        }
    
    def set_mode(self, mode: str):
        """Set trading risk mode"""
        if mode == "conservative":
            self.mode = mode
            settings.risk_mode = mode
            print(f"📊 Risk mode changed to: {mode}")
        else:
            print(f"⚠️ Invalid risk mode: {mode}")