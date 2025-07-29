"""Pair Reversal Watcher
=======================
Monitors 1m OHLCV data for multiple symbols and closes profitable
positions that are opposite to the detected reversal direction.
"""

from typing import Callable, Dict, List, Any, Optional
import pandas as pd
import asyncio

from .market_analyzer import MarketAnalyzer


class PairReversalWatcher:
    def __init__(
        self,
        symbols: List[str],
        get_ohlcv_func: Callable[[str, str], pd.DataFrame],
        get_open_positions_func: Callable[[], List[Dict[str, Any]]],
        close_position_func: Callable[[Dict[str, Any]], Any],
        logger=None,
        broadcast_func: Optional[Callable[[Dict[str, Any]], Any]] = None,
        timeframe: str = "1",
        confirm_timeframe: Optional[str] = None,
        close_losing: bool = False,
    ):
        self.symbols = symbols
        self.get_ohlcv = get_ohlcv_func
        self.get_open_positions = get_open_positions_func
        self.close_position = close_position_func
        self.logger = logger
        self.broadcast = broadcast_func or (lambda data: None)
        self.last_direction: Dict[str, Optional[str]] = {s: None for s in symbols}
        self.timeframe = timeframe
        self.confirm_timeframe = confirm_timeframe
        self.close_losing = close_losing
        self.market_analyzer = MarketAnalyzer()

    async def check_reversals_and_close(self):
        positions = self.get_open_positions() or []
        for symbol in self.symbols:
            df = self.get_ohlcv(symbol, self.timeframe)
            if df is None or len(df) < 50:
                if self.logger:
                    self.logger.warning(
                        f"[PairReversalWatcher] Недостаточно данных для {symbol}"
                    )
                continue
            reversal, direction = self.detect_reversal(df, symbol)
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
                for pos in positions:
                    if pos.get("symbol") != symbol:
                        continue
                    profit = (
                        pos.get("profit")
                        or pos.get("pnl")
                        or pos.get("unrealized_pnl")
                        or 0
                    )
                    raw_side = pos.get("side", "").lower()  # 'buy' или 'sell'
                    side = "long" if raw_side == "buy" else "short" if raw_side == "sell" else raw_side
                    should_close = (
                        profit > 0
                        or (self.close_losing and profit < 0)
                    ) and (
                        (direction == "long" and side == "short")
                        or (direction == "short" and side == "long")
                    )
                    if should_close:
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

    @staticmethod
    def _detect_candlestick_patterns(df: pd.DataFrame) -> List[str]:
        """Detect simple candlestick patterns on the latest candles"""
        if len(df) < 2:
            return []

        patterns: List[str] = []
        last = df.iloc[-1]
        prev = df.iloc[-2]

        body = abs(last["close"] - last["open"])
        candle_range = last["high"] - last["low"]
        if candle_range == 0:
            candle_range = 1e-8
        lower_shadow = min(last["open"], last["close"]) - last["low"]
        upper_shadow = last["high"] - max(last["open"], last["close"])

        # Hammer pattern
        if body <= candle_range * 0.3 and lower_shadow >= body * 2 and upper_shadow <= body:
            patterns.append("hammer")
        # Shooting star (bearish hammer)
        if body <= candle_range * 0.3 and upper_shadow >= body * 2 and lower_shadow <= body:
            patterns.append("shooting_star")

        # Doji
        if body <= candle_range * 0.1:
            patterns.append("doji")

        # Engulfing patterns
        if (
            last["close"] > last["open"]
            and prev["close"] < prev["open"]
            and last["close"] >= prev["open"]
            and last["open"] <= prev["close"]
        ):
            patterns.append("bullish_engulfing")
        if (
            last["close"] < last["open"]
            and prev["close"] > prev["open"]
            and last["open"] >= prev["close"]
            and last["close"] <= prev["open"]
        ):
            patterns.append("bearish_engulfing")

        return patterns

    def detect_reversal(
        self,
        df: pd.DataFrame,
        symbol: Optional[str] = None,
        check_htf: bool = True,
    ):
        rsi = self.calc_rsi(df["close"], period=14)
        macd, macd_signal = self.calc_macd(df["close"])
        upper_bb, lower_bb = self.calc_bollinger_bands(df["close"])
        close = df["close"].iloc[-1]

        support_res = self.market_analyzer._analyze_support_resistance(
            df["high"], df["low"], df["close"]
        )
        patterns = self._detect_candlestick_patterns(df)

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

        # Support/resistance proximity
        if support_res.get("support_distance", 100) < 1:
            signals += 1
            long_votes += 1
        if support_res.get("resistance_distance", 100) < 1:
            signals += 1
            short_votes += 1

        # Candlestick patterns
        if any(p in patterns for p in ["hammer", "bullish_engulfing"]):
            signals += 1
            long_votes += 1
        if any(p in patterns for p in ["shooting_star", "bearish_engulfing"]):
            signals += 1
            short_votes += 1

        if signals >= 2:
            if long_votes >= 2:
                direction = "long"
            elif short_votes >= 2:
                direction = "short"
            else:
                direction = None
            if direction and check_htf and symbol and self.confirm_timeframe:
                df_htf = self.get_ohlcv(symbol, self.confirm_timeframe)
                if df_htf is not None and len(df_htf) >= 50:
                    htf_rev, htf_dir = self.detect_reversal(df_htf, check_htf=False)
                    if not htf_rev or htf_dir != direction:
                        return False, None
            return True, direction

        return False, None
