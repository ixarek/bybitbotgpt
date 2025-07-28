"""Pair Reversal Watcher
=======================
Monitors 1m OHLCV data for multiple symbols and closes profitable
positions that are opposite to the detected reversal direction.
"""

from typing import Callable, Dict, List, Any, Optional
import pandas as pd
import asyncio


class PairReversalWatcher:
    def __init__(
        self,
        symbols: List[str],
        get_ohlcv_func: Callable[[str], pd.DataFrame],
        get_open_positions_func: Callable[[], List[Dict[str, Any]]],
        close_position_func: Callable[[Dict[str, Any]], Any],
        logger=None,
        broadcast_func: Optional[Callable[[Dict[str, Any]], Any]] = None,
    ):
        self.symbols = symbols
        self.get_ohlcv = get_ohlcv_func
        self.get_open_positions = get_open_positions_func
        self.close_position = close_position_func
        self.logger = logger
        self.broadcast = broadcast_func or (lambda data: None)
        self.last_direction: Dict[str, Optional[str]] = {s: None for s in symbols}

    async def check_reversals_and_close(self):
        for symbol in self.symbols:
            df = self.get_ohlcv(symbol)
            if df is None or len(df) < 50:
                if self.logger:
                    self.logger.warning(
                        f"[PairReversalWatcher] Недостаточно данных для {symbol}"
                    )
                continue
            reversal, direction = self.detect_reversal(df)
            if reversal and direction in ("long", "short"):
                self.last_direction[symbol] = direction
                if self.logger:
                    self.logger.info(
                        f"[PairReversalWatcher] {symbol} reversal -> {direction}"
                    )
                try:
                    self.broadcast({"symbol": symbol, "direction": direction})
                except Exception:
                    pass
                positions = self.get_open_positions() or []
                for pos in positions:
                    if pos.get("symbol") != symbol:
                        continue
                    profit = (
                        pos.get("profit")
                        or pos.get("pnl")
                        or pos.get("unrealized_pnl")
                        or 0
                    )
                    side = pos.get("side", "").lower()
                    if profit > 0 and (
                        (direction == "long" and side == "short")
                        or (direction == "short" and side == "long")
                    ):
                        if asyncio.iscoroutinefunction(self.close_position):
                            await self.close_position(pos)
                        else:
                            self.close_position(pos)
                        if self.logger:
                            self.logger.info(
                                f"[PairReversalWatcher] Закрыта прибыльная {symbol} позиция"
                            )

    @staticmethod
    def calc_rsi(series: pd.Series, period: int = 14) -> pd.Series:
        delta = series.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi.fillna(0)

    @staticmethod
    def calc_macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
        ema_fast = series.ewm(span=fast, adjust=False).mean()
        ema_slow = series.ewm(span=slow, adjust=False).mean()
        macd = ema_fast - ema_slow
        macd_signal = macd.ewm(span=signal, adjust=False).mean()
        return macd, macd_signal

    @staticmethod
    def calc_bollinger_bands(series: pd.Series, period: int = 20, std_dev: int = 2):
        sma = series.rolling(window=period).mean()
        std = series.rolling(window=period).std()
        upper = sma + std_dev * std
        lower = sma - std_dev * std
        return upper, lower

    def detect_reversal(self, df: pd.DataFrame):
        rsi = self.calc_rsi(df["close"], period=14)
        macd, macd_signal = self.calc_macd(df["close"])
        upper_bb, lower_bb = self.calc_bollinger_bands(df["close"])
        close = df["close"].iloc[-1]

        signals = 0
        long_votes = 0
        short_votes = 0
        last_rsi = rsi.iloc[-1]
        if last_rsi < 30:
            signals += 1
            long_votes += 1
        elif last_rsi > 70:
            signals += 1
            short_votes += 1
        if macd.iloc[-1] > macd_signal.iloc[-1]:
            signals += 1
            long_votes += 1
        elif macd.iloc[-1] < macd_signal.iloc[-1]:
            signals += 1
            short_votes += 1
        if close < lower_bb.iloc[-1]:
            signals += 1
            long_votes += 1
        elif close > upper_bb.iloc[-1]:
            signals += 1
            short_votes += 1
        if signals >= 2:
            if long_votes >= 2:
                return True, "long"
            elif short_votes >= 2:
                return True, "short"
            else:
                return True, None
        return False, None
