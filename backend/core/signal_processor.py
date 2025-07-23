"""
Signal Processor for Bybit Trading Bot
Analyzes market data and generates trading signals using technical indicators
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Any
import logging
from datetime import datetime

# --- SuperTrendAI ---
from backend.core.supertrend_ai import SuperTrendAI

logger = logging.getLogger(__name__)


class SignalProcessor:
    """
    Processes market data and generates trading signals using technical indicators
    """
    
    def __init__(self):
        self.indicators = [
            "RSI", "MACD", "SMA", "EMA", "BB", "STOCH", 
            "WILLIAMS", "ATR", "ADX", "MFI", "OBV"
        ]
        self.signal_cache = {}
        self.last_update = {}
        
    def get_signals(self, symbol: str, timeframe: str = "5") -> Dict[str, str]:
        """
        Get trading signals for a specific symbol and timeframe
        """
        try:
            logger.info(f"📊 Generating signals for {symbol} {timeframe}")
            cache_key = f"{symbol}_{timeframe}"
            now = datetime.now()
            if (cache_key in self.signal_cache and 
                cache_key in self.last_update and 
                (now - self.last_update[cache_key]).seconds < 30):
                logger.debug(f"Using cached signals for {symbol} {timeframe}")
                return self.signal_cache[cache_key]
            
            # Получаем bybit_client из main.py вместо прямого импорта
            from backend.main import bybit_client
            if bybit_client is None:
                logger.warning("Bybit client not available, using mock signals")
                return self._generate_mock_signals()
            
            df = bybit_client.get_kline(symbol, timeframe, limit=200)
            if df is None or df.empty:
                logger.warning(f"No market data for {symbol} {timeframe}, using mock signals")
                return self._generate_mock_signals()
            
            signals = self._calculate_indicators(df)
            self.signal_cache[cache_key] = signals
            self.last_update[cache_key] = now
            logger.info(f"✅ Generated {len(signals)} signals for {symbol} {timeframe}")
            return signals
        except Exception as e:
            logger.error(f"❌ Error generating signals for {symbol} {timeframe}: {e}")
            return self._generate_mock_signals()
    
    def get_indicator_value(self, symbol: str, timeframe: str, indicator: str) -> str:
        """
        Get the actual value of a specific indicator
        """
        try:
            # Получаем bybit_client из main.py вместо прямого импорта
            from backend.main import bybit_client
            
            if bybit_client is None:
                return "N/A"
            
            df = bybit_client.get_kline(symbol, timeframe, limit=200)
            
            if df is None or df.empty or len(df) < 50:
                return "N/A"
            
            close = df['close']
            high = df['high']
            low = df['low']
            volume = df['volume']
            
            # Calculate specific indicator value
            if indicator == "RSI":
                rsi = self._calculate_rsi(close, 14)
                return f"{rsi.iloc[-1]:.1f}" if not rsi.empty and not pd.isna(rsi.iloc[-1]) else "N/A"
                
            elif indicator == "MACD":
                macd_line, _, _ = self._calculate_macd(close, 12, 26, 9)
                return f"{macd_line.iloc[-1]:.3f}" if len(macd_line) > 0 and not pd.isna(macd_line.iloc[-1]) else "N/A"
                
            elif indicator == "SMA":
                sma_20 = close.rolling(window=20).mean()
                return f"${sma_20.iloc[-1]:.0f}" if not pd.isna(sma_20.iloc[-1]) else "N/A"
                
            elif indicator == "EMA":
                ema_12 = close.ewm(span=12).mean()
                return f"${ema_12.iloc[-1]:.0f}" if not pd.isna(ema_12.iloc[-1]) else "N/A"
                
            elif indicator == "BB":
                bb_upper, bb_lower = self._calculate_bollinger_bands(close, 20, 2)
                if not pd.isna(bb_upper.iloc[-1]) and not pd.isna(bb_lower.iloc[-1]):
                    return f"${bb_lower.iloc[-1]:.0f}-${bb_upper.iloc[-1]:.0f}"
                return "N/A"
                
            elif indicator == "STOCH":
                stoch_k, _ = self._calculate_stochastic(high, low, close, 14, 3)
                return f"{stoch_k.iloc[-1]:.1f}%" if not pd.isna(stoch_k.iloc[-1]) else "N/A"
                
            elif indicator == "WILLIAMS":
                williams_r = self._calculate_williams_r(high, low, close, 14)
                return f"{williams_r.iloc[-1]:.1f}%" if not pd.isna(williams_r.iloc[-1]) else "N/A"
                
            elif indicator == "ATR":
                atr = self._calculate_atr(high, low, close, 14)
                return f"{atr.iloc[-1]:.2f}" if len(atr) > 0 and not pd.isna(atr.iloc[-1]) else "N/A"
                
            elif indicator == "ADX":
                ema_short = close.ewm(span=10).mean()
                ema_long = close.ewm(span=20).mean()
                trend_strength = abs(ema_short.iloc[-1] - ema_long.iloc[-1]) / ema_long.iloc[-1] * 100
                return f"{trend_strength:.1f}%"
                
            elif indicator == "MFI":
                typical_price = (high + low + close) / 3
                money_flow = typical_price * volume
                mf_ratio = money_flow.rolling(14).sum() / volume.rolling(14).sum()
                mf_normalized = (mf_ratio - mf_ratio.rolling(14).min()) / (mf_ratio.rolling(14).max() - mf_ratio.rolling(14).min()) * 100
                return f"{mf_normalized.iloc[-1]:.1f}%" if not pd.isna(mf_normalized.iloc[-1]) else "N/A"
                
            elif indicator == "OBV":
                obv = self._calculate_obv(close, volume)
                return f"{obv.iloc[-1]:.0f}" if len(obv) > 0 and not pd.isna(obv.iloc[-1]) else "N/A"
                
            else:
                return "N/A"
                
        except Exception as e:
            logger.error(f"Error getting indicator value for {indicator}: {e}")
            return "N/A"
    
    def get_detailed_signals(self, symbol: str, timeframe: str = "5") -> Dict[str, Dict[str, str]]:
        """
        Get detailed trading signals with both numeric values and signals
        """
        try:
            logger.info(f"📊 Generating detailed signals for {symbol} {timeframe}")
            
            # Получаем bybit_client из main.py вместо прямого импорта
            from backend.main import bybit_client
            if bybit_client is None:
                logger.warning("Bybit client not available, using mock signals")
                return self._generate_mock_detailed_signals()
            
            df = bybit_client.get_kline(symbol, timeframe, limit=200)
            if df is None or df.empty:
                logger.warning(f"No market data for {symbol} {timeframe}, using mock signals")
                return self._generate_mock_detailed_signals()
            
            detailed_signals = self._calculate_detailed_indicators(df)
            logger.info(f"✅ Generated {len(detailed_signals)} detailed signals for {symbol} {timeframe}")
            return detailed_signals
        except Exception as e:
            logger.error(f"❌ Error generating detailed signals for {symbol} {timeframe}: {e}")
            return self._generate_mock_detailed_signals()
    
    def _calculate_indicators(self, df: pd.DataFrame) -> Dict[str, str]:
        """
        Calculate technical indicators and generate signals using simple math
        """
        signals = {}
        
        try:
            # Ensure we have enough data
            if len(df) < 50:
                logger.warning("Not enough data for indicators, using mock signals")
                return self._generate_mock_signals()
            
            close = df['close']
            high = df['high']
            low = df['low']
            volume = df['volume']
            
            # RSI (Relative Strength Index)
            rsi = self._calculate_rsi(close, 14)
            if not rsi.empty and not pd.isna(rsi.iloc[-1]):
                rsi_val = rsi.iloc[-1]
                if rsi_val < 30:
                    signals["RSI"] = "BUY"
                elif rsi_val > 70:
                    signals["RSI"] = "SELL"
                else:
                    signals["RSI"] = "HOLD"
            else:
                signals["RSI"] = "HOLD"
            
            # MACD
            macd_line, macd_signal_line, _ = self._calculate_macd(close, 12, 26, 9)
            if len(macd_line) > 1 and len(macd_signal_line) > 1:
                if not pd.isna(macd_line.iloc[-1]) and not pd.isna(macd_signal_line.iloc[-1]):
                    if (macd_line.iloc[-1] > macd_signal_line.iloc[-1] and 
                        macd_line.iloc[-2] <= macd_signal_line.iloc[-2]):
                        signals["MACD"] = "BUY"
                    elif (macd_line.iloc[-1] < macd_signal_line.iloc[-1] and 
                          macd_line.iloc[-2] >= macd_signal_line.iloc[-2]):
                        signals["MACD"] = "SELL"
                    else:
                        signals["MACD"] = "HOLD"
                else:
                    signals["MACD"] = "HOLD"
            else:
                signals["MACD"] = "HOLD"
            
            # Simple Moving Average
            sma_20 = close.rolling(window=20).mean()
            sma_50 = close.rolling(window=50).mean()
            if not pd.isna(sma_20.iloc[-1]) and not pd.isna(sma_50.iloc[-1]):
                if sma_20.iloc[-1] > sma_50.iloc[-1]:
                    signals["SMA"] = "BUY"
                elif sma_20.iloc[-1] < sma_50.iloc[-1]:
                    signals["SMA"] = "SELL"
                else:
                    signals["SMA"] = "HOLD"
            else:
                signals["SMA"] = "HOLD"
            
            # Exponential Moving Average
            ema_12 = close.ewm(span=12).mean()
            ema_26 = close.ewm(span=26).mean()
            if not pd.isna(ema_12.iloc[-1]) and not pd.isna(ema_26.iloc[-1]):
                if ema_12.iloc[-1] > ema_26.iloc[-1]:
                    signals["EMA"] = "BUY"
                elif ema_12.iloc[-1] < ema_26.iloc[-1]:
                    signals["EMA"] = "SELL"
                else:
                    signals["EMA"] = "HOLD"
            else:
                signals["EMA"] = "HOLD"
            
            # Bollinger Bands
            bb_upper, bb_lower = self._calculate_bollinger_bands(close, 20, 2)
            if not pd.isna(bb_upper.iloc[-1]) and not pd.isna(bb_lower.iloc[-1]):
                current_price = close.iloc[-1]
                if current_price < bb_lower.iloc[-1]:
                    signals["BB"] = "BUY"
                elif current_price > bb_upper.iloc[-1]:
                    signals["BB"] = "SELL"
                else:
                    signals["BB"] = "HOLD"
            else:
                signals["BB"] = "HOLD"
            
            # Stochastic Oscillator
            stoch_k, stoch_d = self._calculate_stochastic(high, low, close, 14, 3)
            if not pd.isna(stoch_k.iloc[-1]) and not pd.isna(stoch_d.iloc[-1]):
                if stoch_k.iloc[-1] < 20 and stoch_d.iloc[-1] < 20:
                    signals["STOCH"] = "BUY"
                elif stoch_k.iloc[-1] > 80 and stoch_d.iloc[-1] > 80:
                    signals["STOCH"] = "SELL"
                else:
                    signals["STOCH"] = "HOLD"
            else:
                signals["STOCH"] = "HOLD"
            
            # Williams %R
            williams_r = self._calculate_williams_r(high, low, close, 14)
            if not pd.isna(williams_r.iloc[-1]):
                willr_val = williams_r.iloc[-1]
                if willr_val < -80:
                    signals["WILLIAMS"] = "BUY"
                elif willr_val > -20:
                    signals["WILLIAMS"] = "SELL"
                else:
                    signals["WILLIAMS"] = "HOLD"
            else:
                signals["WILLIAMS"] = "HOLD"
            
            # ATR (Average True Range)
            atr = self._calculate_atr(high, low, close, 14)
            if len(atr) > 1 and not pd.isna(atr.iloc[-1]):
                signals["ATR"] = "NONE"  # Больше не BUY/SELL
            else:
                signals["ATR"] = "NONE"
            
            # ADX (simplified version)
            # For simplicity, we'll use a basic trend strength indicator
            ema_short = close.ewm(span=10).mean()
            ema_long = close.ewm(span=20).mean()
            trend_strength = abs(ema_short.iloc[-1] - ema_long.iloc[-1]) / ema_long.iloc[-1] * 100
            if trend_strength > 2:  # Strong trend
                if ema_short.iloc[-1] > ema_long.iloc[-1]:
                    signals["ADX"] = "BUY"
                else:
                    signals["ADX"] = "SELL"
            else:
                signals["ADX"] = "HOLD"
            
            # MFI (Money Flow Index) - simplified
            typical_price = (high + low + close) / 3
            money_flow = typical_price * volume
            mf_ratio = money_flow.rolling(14).sum() / volume.rolling(14).sum()
            mf_normalized = (mf_ratio - mf_ratio.rolling(14).min()) / (mf_ratio.rolling(14).max() - mf_ratio.rolling(14).min()) * 100
            
            if not pd.isna(mf_normalized.iloc[-1]):
                mfi_val = mf_normalized.iloc[-1]
                if mfi_val < 20:
                    signals["MFI"] = "BUY"
                elif mfi_val > 80:
                    signals["MFI"] = "SELL"
                else:
                    signals["MFI"] = "HOLD"
            else:
                signals["MFI"] = "HOLD"
            
            # OBV (On Balance Volume)
            obv = self._calculate_obv(close, volume)
            if len(obv) > 5:
                obv_sma = obv.rolling(window=5).mean()
                if len(obv_sma) > 1 and not pd.isna(obv_sma.iloc[-1]) and not pd.isna(obv_sma.iloc[-2]):
                    if obv_sma.iloc[-1] > obv_sma.iloc[-2]:
                        signals["OBV"] = "BUY"
                    elif obv_sma.iloc[-1] < obv_sma.iloc[-2]:
                        signals["OBV"] = "SELL"
                    else:
                        signals["OBV"] = "HOLD"
                else:
                    signals["OBV"] = "HOLD"
            else:
                signals["OBV"] = "HOLD"
            
            # CMF (Chaikin Money Flow)
            cmf = self._calculate_cmf(high, low, close, volume, 20)
            if len(cmf) > 1 and not pd.isna(cmf.iloc[-1]):
                cmf_val = cmf.iloc[-1]
                if cmf_val > 0.05:
                    signals["CMF"] = "BUY"
                elif cmf_val < -0.05:
                    signals["CMF"] = "SELL"
                else:
                    signals["CMF"] = "HOLD"
            else:
                signals["CMF"] = "HOLD"
            
            # --- SuperTrend AI (Clustering) ---
            try:
                st_ai = SuperTrendAI(window=10, n_clusters=3)
                df_st = st_ai.fit_transform(df)
                st_signal = df_st['supertrend_signal'].iloc[-1]
                st_value = df_st['supertrend'].iloc[-1]
                close = df['close'].iloc[-1]
                if st_signal == 1 and close > st_value:
                    signals["SuperTrendAI"] = "BUY"
                elif st_signal == -1 and close < st_value:
                    signals["SuperTrendAI"] = "SELL"
                else:
                    signals["SuperTrendAI"] = "HOLD"
            except Exception as e:
                signals["SuperTrendAI"] = "HOLD"
            
        except Exception as e:
            logger.error(f"Error calculating indicators: {e}")
            return self._generate_mock_signals()
        
        return signals
    
    def _calculate_rsi(self, close: pd.Series, period: int = 14) -> pd.Series:
        """Calculate RSI"""
        delta = close.diff()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        avg_gain = gain.rolling(window=period).mean()
        avg_loss = loss.rolling(window=period).mean()
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def _calculate_macd(self, close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
        """Calculate MACD"""
        ema_fast = close.ewm(span=fast).mean()
        ema_slow = close.ewm(span=slow).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal).mean()
        histogram = macd_line - signal_line
        return macd_line, signal_line, histogram
    
    def _calculate_bollinger_bands(self, close: pd.Series, period: int = 20, std_dev: int = 2):
        """Calculate Bollinger Bands"""
        sma = close.rolling(window=period).mean()
        std = close.rolling(window=period).std()
        upper_band = sma + (std * std_dev)
        lower_band = sma - (std * std_dev)
        return upper_band, lower_band
    
    def _calculate_stochastic(self, high: pd.Series, low: pd.Series, close: pd.Series, k_period: int = 14, d_period: int = 3):
        """Calculate Stochastic Oscillator"""
        lowest_low = low.rolling(window=k_period).min()
        highest_high = high.rolling(window=k_period).max()
        k_percent = 100 * ((close - lowest_low) / (highest_high - lowest_low))
        d_percent = k_percent.rolling(window=d_period).mean()
        return k_percent, d_percent
    
    def _calculate_williams_r(self, high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14):
        """Calculate Williams %R"""
        highest_high = high.rolling(window=period).max()
        lowest_low = low.rolling(window=period).min()
        williams_r = -100 * ((highest_high - close) / (highest_high - lowest_low))
        return williams_r
    
    def _calculate_atr(self, high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14):
        """Calculate Average True Range"""
        high_low = high - low
        high_close = np.abs(high - close.shift())
        low_close = np.abs(low - close.shift())
        true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = true_range.rolling(window=period).mean()
        return atr
    
    def _calculate_obv(self, close: pd.Series, volume: pd.Series):
        """Calculate On Balance Volume"""
        obv = pd.Series(index=close.index, dtype=float)
        obv.iloc[0] = volume.iloc[0]
        
        for i in range(1, len(close)):
            if close.iloc[i] > close.iloc[i-1]:
                obv.iloc[i] = obv.iloc[i-1] + volume.iloc[i]
            elif close.iloc[i] < close.iloc[i-1]:
                obv.iloc[i] = obv.iloc[i-1] - volume.iloc[i]
            else:
                obv.iloc[i] = obv.iloc[i-1]
        
        return obv
    
    def _calculate_cmf(self, high: pd.Series, low: pd.Series, close: pd.Series, volume: pd.Series, period: int = 20) -> pd.Series:
        """Вычисление Chaikin Money Flow (CMF)"""
        mf_multiplier = ((close - low) - (high - close)) / (high - low)
        mf_multiplier = mf_multiplier.replace([np.inf, -np.inf], 0).fillna(0)
        mf_volume = mf_multiplier * volume
        cmf = mf_volume.rolling(window=period).sum() / volume.rolling(window=period).sum()
        return cmf
    
    def _generate_mock_signals(self) -> Dict[str, str]:
        """
        Generate mock signals when real data is not available
        """
        import random
        
        signals = {}
        signal_types = ["BUY", "SELL", "HOLD"]
        
        for indicator in self.indicators:
            # Generate realistic signal distribution
            if indicator in ["RSI", "STOCH", "WILLIAMS", "MFI"]:
                # Oscillators - more likely to be HOLD
                weights = [0.2, 0.2, 0.6]
            elif indicator in ["MACD", "ADX"]:
                # Trend indicators - more likely to have direction
                weights = [0.3, 0.3, 0.4]
            else:
                # Moving averages and other indicators
                weights = [0.25, 0.25, 0.5]
            
            signals[indicator] = random.choices(signal_types, weights=weights)[0]
        
        return signals
    
    def _generate_mock_detailed_signals(self) -> Dict[str, Dict[str, str]]:
        """
        Generate mock detailed signals for testing
        """
        return {
            "RSI": {"value": "45.67", "signal": "HOLD"},
            "MACD": {"value": "0.0123", "signal": "HOLD"},
            "SMA": {"value": "98765.43", "signal": "BUY"},
            "EMA": {"value": "98432.12", "signal": "SELL"},
            "BB": {"value": "67.3%", "signal": "HOLD"},
            "STOCH": {"value": "56.78", "signal": "BUY"},
            "WILLIAMS": {"value": "-45.67", "signal": "BUY"},
            "ATR": {"value": "1234.56", "signal": "BUY"},
            "ADX": {"value": "3.2%", "signal": "SELL"},
            "MFI": {"value": "65.4", "signal": "BUY"},
            "OBV": {"value": "12345678", "signal": "SELL"}
        }
    
    def _calculate_detailed_indicators(self, df: pd.DataFrame) -> Dict[str, Dict[str, str]]:
        """
        Calculate technical indicators with both numeric values and signals
        """
        detailed_signals = {}
        
        try:
            # Ensure we have enough data
            if len(df) < 50:
                logger.warning("Not enough data for indicators, using mock signals")
                return self._generate_mock_detailed_signals()
            
            close = df['close']
            high = df['high']
            low = df['low']
            volume = df['volume']
            
            # RSI (Relative Strength Index)
            rsi = self._calculate_rsi(close, 14)
            if not rsi.empty and not pd.isna(rsi.iloc[-1]):
                rsi_val = rsi.iloc[-1]
                if rsi_val < 30:
                    signal = "BUY"
                elif rsi_val > 70:
                    signal = "SELL"
                else:
                    signal = "HOLD"
                detailed_signals["RSI"] = {
                    "value": f"{rsi_val:.2f}",
                    "signal": signal
                }
            else:
                detailed_signals["RSI"] = {"value": "N/A", "signal": "HOLD"}
            
            # MACD
            macd_line, macd_signal_line, _ = self._calculate_macd(close, 12, 26, 9)
            if len(macd_line) > 1 and len(macd_signal_line) > 1:
                if not pd.isna(macd_line.iloc[-1]) and not pd.isna(macd_signal_line.iloc[-1]):
                    macd_val = macd_line.iloc[-1]
                    if (macd_line.iloc[-1] > macd_signal_line.iloc[-1] and 
                        macd_line.iloc[-2] <= macd_signal_line.iloc[-2]):
                        signal = "BUY"
                    elif (macd_line.iloc[-1] < macd_signal_line.iloc[-1] and 
                          macd_line.iloc[-2] >= macd_signal_line.iloc[-2]):
                        signal = "SELL"
                    else:
                        signal = "HOLD"
                    detailed_signals["MACD"] = {
                        "value": f"{macd_val:.4f}",
                        "signal": signal
                    }
                else:
                    detailed_signals["MACD"] = {"value": "N/A", "signal": "HOLD"}
            else:
                detailed_signals["MACD"] = {"value": "N/A", "signal": "HOLD"}
            
            # Simple Moving Average
            sma_20 = close.rolling(window=20).mean()
            sma_50 = close.rolling(window=50).mean()
            if not pd.isna(sma_20.iloc[-1]) and not pd.isna(sma_50.iloc[-1]):
                sma_val = sma_20.iloc[-1]
                if sma_20.iloc[-1] > sma_50.iloc[-1]:
                    signal = "BUY"
                elif sma_20.iloc[-1] < sma_50.iloc[-1]:
                    signal = "SELL"
                else:
                    signal = "HOLD"
                detailed_signals["SMA"] = {
                    "value": f"{sma_val:.2f}",
                    "signal": signal
                }
            else:
                detailed_signals["SMA"] = {"value": "N/A", "signal": "HOLD"}
            
            # Exponential Moving Average
            ema_12 = close.ewm(span=12).mean()
            ema_26 = close.ewm(span=26).mean()
            if not pd.isna(ema_12.iloc[-1]) and not pd.isna(ema_26.iloc[-1]):
                ema_val = ema_12.iloc[-1]
                if ema_12.iloc[-1] > ema_26.iloc[-1]:
                    signal = "BUY"
                elif ema_12.iloc[-1] < ema_26.iloc[-1]:
                    signal = "SELL"
                else:
                    signal = "HOLD"
                detailed_signals["EMA"] = {
                    "value": f"{ema_val:.2f}",
                    "signal": signal
                }
            else:
                detailed_signals["EMA"] = {"value": "N/A", "signal": "HOLD"}
            
            # Bollinger Bands
            bb_upper, bb_lower = self._calculate_bollinger_bands(close, 20, 2)
            if not pd.isna(bb_upper.iloc[-1]) and not pd.isna(bb_lower.iloc[-1]):
                current_price = close.iloc[-1]
                bb_position = (current_price - bb_lower.iloc[-1]) / (bb_upper.iloc[-1] - bb_lower.iloc[-1]) * 100
                if current_price < bb_lower.iloc[-1]:
                    signal = "BUY"
                elif current_price > bb_upper.iloc[-1]:
                    signal = "SELL"
                else:
                    signal = "HOLD"
                detailed_signals["BB"] = {
                    "value": f"{bb_position:.1f}%",
                    "signal": signal
                }
            else:
                detailed_signals["BB"] = {"value": "N/A", "signal": "HOLD"}
            
            # Stochastic Oscillator
            stoch_k, stoch_d = self._calculate_stochastic(high, low, close, 14, 3)
            if not pd.isna(stoch_k.iloc[-1]) and not pd.isna(stoch_d.iloc[-1]):
                stoch_val = stoch_k.iloc[-1]
                if stoch_k.iloc[-1] < 20 and stoch_d.iloc[-1] < 20:
                    signal = "BUY"
                elif stoch_k.iloc[-1] > 80 and stoch_d.iloc[-1] > 80:
                    signal = "SELL"
                else:
                    signal = "HOLD"
                detailed_signals["STOCH"] = {
                    "value": f"{stoch_val:.2f}",
                    "signal": signal
                }
            else:
                detailed_signals["STOCH"] = {"value": "N/A", "signal": "HOLD"}
            
            # Williams %R
            williams_r = self._calculate_williams_r(high, low, close, 14)
            if not pd.isna(williams_r.iloc[-1]):
                willr_val = williams_r.iloc[-1]
                if willr_val < -80:
                    signal = "BUY"
                elif willr_val > -20:
                    signal = "SELL"
                else:
                    signal = "HOLD"
                detailed_signals["WILLIAMS"] = {
                    "value": f"{willr_val:.2f}",
                    "signal": signal
                }
            else:
                detailed_signals["WILLIAMS"] = {"value": "N/A", "signal": "HOLD"}
            
            # ATR (Average True Range)
            atr = self._calculate_atr(high, low, close, 14)
            if len(atr) > 1 and not pd.isna(atr.iloc[-1]):
                atr_val = atr.iloc[-1]
                price = close.iloc[-1]
                ratio = atr_val / price if price else 0
                if ratio < 0.01:
                    strength = "Слабый"
                elif ratio < 0.03:
                    strength = "Средний"
                else:
                    strength = "Сильный"
                detailed_signals["ATR"] = {
                    "value": f"{atr_val:.2f}",
                    "signal": "NONE",
                    "strength": strength
                }
            else:
                detailed_signals["ATR"] = {"value": "N/A", "signal": "NONE", "strength": "N/A"}
            
            # ADX (simplified version)
            ema_short = close.ewm(span=10).mean()
            ema_long = close.ewm(span=20).mean()
            trend_strength = abs(ema_short.iloc[-1] - ema_long.iloc[-1]) / ema_long.iloc[-1] * 100
            if trend_strength > 2:  # Strong trend
                if ema_short.iloc[-1] > ema_long.iloc[-1]:
                    signal = "BUY"
                else:
                    signal = "SELL"
            else:
                signal = "HOLD"
            detailed_signals["ADX"] = {
                "value": f"{trend_strength:.1f}%",
                "signal": signal
            }
            
            # MFI (Money Flow Index) - simplified
            typical_price = (high + low + close) / 3
            money_flow = typical_price * volume
            mf_ratio = money_flow.rolling(14).sum() / volume.rolling(14).sum()
            mf_normalized = (mf_ratio - mf_ratio.rolling(14).min()) / (mf_ratio.rolling(14).max() - mf_ratio.rolling(14).min()) * 100
            
            if not pd.isna(mf_normalized.iloc[-1]):
                mfi_val = mf_normalized.iloc[-1]
                if mfi_val < 20:
                    signal = "BUY"
                elif mfi_val > 80:
                    signal = "SELL"
                else:
                    signal = "HOLD"
                detailed_signals["MFI"] = {
                    "value": f"{mfi_val:.1f}",
                    "signal": signal
                }
            else:
                detailed_signals["MFI"] = {"value": "N/A", "signal": "HOLD"}
            
            # OBV (On-Balance Volume)
            obv = self._calculate_obv(close, volume)
            if len(obv) > 1 and not pd.isna(obv.iloc[-1]) and not pd.isna(obv.iloc[-2]):
                obv_val = obv.iloc[-1]
                if obv.iloc[-1] > obv.iloc[-2]:
                    signal = "BUY"
                elif obv.iloc[-1] < obv.iloc[-2]:
                    signal = "SELL"
                else:
                    signal = "HOLD"
                detailed_signals["OBV"] = {
                    "value": f"{obv_val:.0f}",
                    "signal": signal
                }
            else:
                detailed_signals["OBV"] = {"value": "N/A", "signal": "HOLD"}
            
            # CMF (Chaikin Money Flow)
            cmf = self._calculate_cmf(high, low, close, volume, 20)
            if len(cmf) > 1 and not pd.isna(cmf.iloc[-1]):
                cmf_val = cmf.iloc[-1]
                if cmf_val > 0.05:
                    signal = "BUY"
                elif cmf_val < -0.05:
                    signal = "SELL"
                else:
                    signal = "HOLD"
                detailed_signals["CMF"] = {
                    "value": f"{cmf_val:.4f}",
                    "signal": signal
                }
            else:
                detailed_signals["CMF"] = {"value": "N/A", "signal": "HOLD"}
            
            # --- SuperTrend AI (Clustering) ---
            try:
                st_ai = SuperTrendAI(window=10, n_clusters=3)
                df_st = st_ai.fit_transform(df)
                st_signal = df_st['supertrend_signal'].iloc[-1]
                st_value = df_st['supertrend'].iloc[-1]
                st_mult = df_st['supertrend_multiplier'].iloc[-1]
                close = df['close'].iloc[-1]
                logger.info(f"[SuperTrendAI] UI: close={close}, supertrend={st_value}, signal={st_signal}, multiplier={st_mult}")
                if st_signal == 1 and close > st_value:
                    signal = "BUY"
                elif st_signal == -1 and close < st_value:
                    signal = "SELL"
                else:
                    signal = "HOLD"
                detailed_signals["SuperTrendAI"] = {
                    "value": f"{st_value:.2f}",
                    "signal": signal,
                    "multiplier": f"{st_mult:.2f}",
                    "close": f"{close:.2f}",
                    "supertrend": f"{st_value:.2f}",
                    "supertrend_signal": int(st_signal) if pd.notna(st_signal) else 'N/A'
                }
            except Exception as e:
                logger.error(f"[SuperTrendAI] Ошибка detailed_signals: {e}")
                detailed_signals["SuperTrendAI"] = {"value": "N/A", "signal": "HOLD", "multiplier": "N/A", "close": "N/A", "supertrend": "N/A", "supertrend_signal": "N/A"}
            
            return detailed_signals
            
        except Exception as e:
            logger.error(f"Error calculating detailed indicators: {e}")
            return self._generate_mock_detailed_signals()

    def get_signal_strength(self, signals: Dict[str, str]) -> Dict[str, int]:
        """
        Calculate signal strength based on indicator consensus
        """
        buy_count = sum(1 for signal in signals.values() if signal == "BUY")
        sell_count = sum(1 for signal in signals.values() if signal == "SELL")
        hold_count = sum(1 for signal in signals.values() if signal == "HOLD")
        
        return {
            "BUY": buy_count,
            "SELL": sell_count,
            "HOLD": hold_count,
            "total": len(signals)
        }
    
    def should_trade(self, signals: Dict[str, str], min_confirmation: int = 5) -> Optional[str]:
        """
        Determine if we should trade based on signal confirmation и фильтра по CMF
        """
        strength = self.get_signal_strength(signals)
        cmf_signal = signals.get("CMF", "HOLD")
        # Для BUY CMF должен быть BUY, для SELL — SELL
        if strength["BUY"] >= min_confirmation and cmf_signal == "BUY":
            return "BUY"
        elif strength["SELL"] >= min_confirmation and cmf_signal == "SELL":
            return "SELL"
        else:
            return None 