import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
import logging
logger = logging.getLogger(__name__)

class SuperTrendAI:
    """
    SuperTrend AI (Clustering):
    - Классический индикатор SuperTrend
    - ATR-множитель подбирается динамически через кластеризацию (k-means)
    - Источник идеи: https://www.luxalgo.com/library/indicator/supertrend-ai-clustering/
    
    Пример использования:
        ai = SuperTrendAI(window=10, n_clusters=3)
        df = ai.fit_transform(df)
        # df['supertrend'], df['supertrend_signal']
    """
    def __init__(self, window=10, n_clusters=3, min_multiplier=1.0, max_multiplier=5.0):
        self.window = window
        self.n_clusters = n_clusters
        self.min_multiplier = min_multiplier
        self.max_multiplier = max_multiplier

    def _atr(self, df):
        high = df['high']
        low = df['low']
        close = df['close']
        prev_close = close.shift(1)
        tr = np.maximum(high - low, np.maximum(abs(high - prev_close), abs(low - prev_close)))
        atr = tr.rolling(self.window, min_periods=1).mean()
        return atr

    def _find_best_multiplier(self, df):
        """
        Подбирает оптимальный ATR-множитель через кластеризацию (k-means)
        """
        atr = self._atr(df)
        price_range = df['high'] - df['low']
        X = np.column_stack([
            price_range.values,
            atr.values
        ])
        # Только строки без NaN
        mask = ~np.isnan(X).any(axis=1)
        X_clean = X[mask]
        if len(X_clean) < self.n_clusters:
            return 3.0  # fallback если данных мало
        kmeans = KMeans(n_clusters=self.n_clusters, n_init=10, random_state=42)
        labels = kmeans.fit_predict(X_clean)
        multipliers = []
        for i in range(self.n_clusters):
            cluster_mask = labels == i
            if np.any(cluster_mask):
                ratio = X_clean[cluster_mask, 0] / (X_clean[cluster_mask, 1] + 1e-8)
                median = np.median(ratio)
                multipliers.append(median)
        multipliers = [max(self.min_multiplier, min(self.max_multiplier, m)) for m in multipliers]
        if multipliers:
            return float(np.median(multipliers))
        return 3.0  # fallback

    def supertrend(self, df, multiplier=None):
        """
        Вычисляет SuperTrend для DataFrame с колонками: open, high, low, close
        """
        try:
            atr = self._atr(df)
            if multiplier is None:
                multiplier = self._find_best_multiplier(df)
            hl2 = (df['high'] + df['low']) / 2
            upperband = hl2 + (multiplier * atr)
            lowerband = hl2 - (multiplier * atr)
            supertrend = pd.Series(index=df.index, dtype=float)
            direction = pd.Series(index=df.index, dtype=int)
            in_uptrend = True
            for i in range(len(df)):
                if i == 0:
                    supertrend.iloc[i] = upperband.iloc[i]
                    direction.iloc[i] = 1
                    continue
                if df['close'].iloc[i] > upperband.iloc[i-1]:
                    in_uptrend = True
                elif df['close'].iloc[i] < lowerband.iloc[i-1]:
                    in_uptrend = False
                if in_uptrend:
                    supertrend.iloc[i] = lowerband.iloc[i]
                    direction.iloc[i] = 1
                else:
                    supertrend.iloc[i] = upperband.iloc[i]
                    direction.iloc[i] = -1
            # Лог последних значений
            # logger.info(f"[SuperTrendAI] supertrend: {supertrend.iloc[-5:].to_list()} direction: {direction.iloc[-5:].to_list()} multiplier: {multiplier}")
            return supertrend, direction, multiplier
        except Exception as e:
            logger.error(f"[SuperTrendAI] Ошибка в supertrend: {e}")
            return pd.Series(dtype=float), pd.Series(dtype=int), None

    def fit_transform(self, df):
        """
        Добавляет в DataFrame колонки: supertrend, supertrend_signal, supertrend_multiplier
        """
        try:
            # logger.info(f"[SuperTrendAI] fit_transform: df.shape={df.shape}")
            multiplier = self._find_best_multiplier(df)
            st, signal, _ = self.supertrend(df, multiplier)
            df = df.copy()
            df['supertrend'] = st
            df['supertrend_signal'] = signal
            df['supertrend_multiplier'] = multiplier
            # logger.info(f"[SuperTrendAI] Последние: close={df['close'].iloc[-1]}, supertrend={st.iloc[-1]}, signal={signal.iloc[-1]}, multiplier={multiplier}")
            return df
        except Exception as e:
            logger.error(f"[SuperTrendAI] Ошибка в fit_transform: {e}")
            return df 