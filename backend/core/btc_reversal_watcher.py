"""
Модуль для отслеживания разворотных сигналов по BTC (1m) и закрытия всех прибыльных позиций на всех парах при развороте.
"""

import pandas as pd
from typing import List, Dict, Any
import asyncio

class BTCReversalWatcher:
    def __init__(self, get_btc_ohlcv_func, get_open_positions_func, close_position_func, logger=None):
        """
        :param get_btc_ohlcv_func: функция для получения OHLCV по BTC/USDT (1m)
        :param get_open_positions_func: функция для получения открытых позиций (по всем парам)
        :param close_position_func: функция для закрытия позиции
        :param logger: опциональный логгер
        """
        self.get_btc_ohlcv = get_btc_ohlcv_func
        self.get_open_positions = get_open_positions_func
        self.close_position = close_position_func
        self.logger = logger

    async def check_reversal_and_close(self):
        """
        Основная функция: проверяет разворот по BTC и закрывает прибыльные позиции противоположного направления. Подробное логирование на каждом цикле.
        """
        if self.logger:
            self.logger.info("[BTCReversalWatcher] Запуск цикла проверки разворота...")
        df = self.get_btc_ohlcv()
        if df is None or len(df) < 50:
            if self.logger:
                self.logger.warning("Недостаточно данных для анализа BTC.")
            return
        
        rsi = self.calc_rsi(df['close'], period=14)
        macd, macd_signal = self.calc_macd(df['close'])
        if self.logger:
            self.logger.info(f"RSI: {rsi.iloc[-2]:.2f} -> {rsi.iloc[-1]:.2f}, MACD: {macd.iloc[-2]:.2f} -> {macd.iloc[-1]:.2f}, MACD_signal: {macd_signal.iloc[-2]:.2f} -> {macd_signal.iloc[-1]:.2f}")
        reversal, direction = self.detect_reversal(df)
        if self.logger:
            self.logger.info(f"Результат detect_reversal: {reversal}, направление: {direction}")
        if reversal and direction in ('long', 'short'):
            positions = self.get_open_positions()
            if self.logger:
                self.logger.info(f"Открытые позиции: {positions}")
            for pos in positions:
                profit = pos.get('profit') or pos.get('pnl') or pos.get('unrealized_pnl') or 0
                raw_side = pos.get('side', '').lower()  # 'buy' или 'sell'
                side = 'long' if raw_side == 'buy' else 'short' if raw_side == 'sell' else raw_side
                if self.logger:
                    self.logger.info(f"Проверка позиции: {pos}, прибыль: {profit}, side: {side}")
                # Закрываем только противоположные позиции
                if profit > 0:
                    if (direction == 'long' and side == 'short') or (direction == 'short' and side == 'long'):
                        if asyncio.iscoroutinefunction(self.close_position):
                            await self.close_position(pos)
                        else:
                            self.close_position(pos)
                        if self.logger:
                            self.logger.info(f"Закрыта прибыльная позиция: {pos}")

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
        """
        Проверяет разворот по RSI, MACD и Bollinger Bands и возвращает кортеж (is_reversal, direction), где direction: 'long', 'short' или None.
        :param df: DataFrame с минутными свечами BTC
        :return: (True/False, 'long'/'short'/None)
        """
        rsi = self.calc_rsi(df['close'], period=14)
        macd, macd_signal = self.calc_macd(df['close'])
        upper_bb, lower_bb = self.calc_bollinger_bands(df['close'])
        close = df['close'].iloc[-1]

        signals = 0
        long_votes = 0
        short_votes = 0
        # RSI
        last_rsi = rsi.iloc[-1]
        if last_rsi < 30:
            signals += 1
            long_votes += 1
        elif last_rsi > 70:
            signals += 1
            short_votes += 1
        # MACD
        if macd.iloc[-1] > macd_signal.iloc[-1]:
            signals += 1
            long_votes += 1
        elif macd.iloc[-1] < macd_signal.iloc[-1]:
            signals += 1
            short_votes += 1
        # Bollinger Bands
        if close < lower_bb.iloc[-1]:
            signals += 1
            long_votes += 1
        elif close > upper_bb.iloc[-1]:
            signals += 1
            short_votes += 1
        # Если хотя бы 2 из 3 индикаторов совпадают по направлению — это разворот
        if signals >= 2:
            if long_votes >= 2:
                return True, 'long'
            elif short_votes >= 2:
                return True, 'short'
            else:
                return True, None
        return False, None

    @staticmethod
    def calc_supertrend(df: pd.DataFrame, period: int = 10, multiplier: float = 3.0) -> pd.Series:
        hl2 = (df['high'] + df['low']) / 2
        atr = BTCReversalWatcher.calc_atr(df, period)
        upperband = hl2 + (multiplier * atr)
        lowerband = hl2 - (multiplier * atr)
        supertrend = pd.Series(index=df.index, dtype='float64')
        direction = 1  # 1 - long, -1 - short
        for i in range(period, len(df)):
            if df['close'].iloc[i] > upperband.iloc[i-1]:
                direction = 1
            elif df['close'].iloc[i] < lowerband.iloc[i-1]:
                direction = -1
            supertrend.iloc[i] = direction
        return supertrend.ffill().fillna(1)

    @staticmethod
    def calc_atr(df: pd.DataFrame, period: int = 10) -> pd.Series:
        high_low = df['high'] - df['low']
        high_close = (df['high'] - df['close'].shift()).abs()
        low_close = (df['low'] - df['close'].shift()).abs()
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = ranges.max(axis=1)
        atr = true_range.rolling(window=period).mean()
        return atr

# Пример использования:
# watcher = BTCReversalWatcher(get_btc_ohlcv_func, get_open_positions_func, close_position_func, logger)
# watcher.check_reversal_and_close() 