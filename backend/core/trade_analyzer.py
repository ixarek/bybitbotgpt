import pandas as pd
from typing import List, Dict, Any, Optional
from datetime import datetime

class TradeAnalyzer:
    """
    Анализатор истории сделок и закрытых позиций для автоматической корректировки параметров торговли.
    """
    def __init__(self, trades: Optional[List[Dict]] = None, closed: Optional[List[Dict]] = None):
        self.trades = trades or []
        self.closed = closed or []
        self.df_trades = pd.DataFrame(self.trades)
        self.df_closed = pd.DataFrame(self.closed)

    def winrate(self) -> float:
        """Вычисляет winrate по закрытым позициям (PNL > 0)"""
        if self.df_closed.empty or 'closedPnl' not in self.df_closed:
            return 0.0
        wins = (self.df_closed['closedPnl'].astype(float) > 0).sum()
        total = len(self.df_closed)
        return wins / total if total > 0 else 0.0

    def avg_pnl(self) -> float:
        """Средний PNL по закрытым позициям"""
        if self.df_closed.empty or 'closedPnl' not in self.df_closed:
            return 0.0
        return self.df_closed['closedPnl'].astype(float).mean()

    def avg_holding_time(self) -> float:
        """Среднее время удержания позиции (в минутах)"""
        if self.df_closed.empty or 'createdTime' not in self.df_closed or 'updatedTime' not in self.df_closed:
            return 0.0
        times = (self.df_closed['updatedTime'].astype(float) - self.df_closed['createdTime'].astype(float)) / 1000 / 60
        return times.mean()

    def sl_tp_stats(self) -> Dict[str, int]:
        """Частота срабатывания SL и TP (по причине закрытия)"""
        if self.df_closed.empty or 'reason' not in self.df_closed:
            return {"sl": 0, "tp": 0, "other": 0}
        sl = (self.df_closed['reason'] == 'Stop Loss').sum()
        tp = (self.df_closed['reason'] == 'Take Profit').sum()
        other = len(self.df_closed) - sl - tp
        return {"sl": int(sl), "tp": int(tp), "other": int(other)}

    def loss_streak(self) -> int:
        """Максимальная серия убытков подряд"""
        if self.df_closed.empty or 'closedPnl' not in self.df_closed:
            return 0
        pnl = self.df_closed['closedPnl'].astype(float)
        max_streak = streak = 0
        for v in pnl:
            if v < 0:
                streak += 1
                max_streak = max(max_streak, streak)
            else:
                streak = 0
        return max_streak

    def profit_streak(self) -> int:
        """Максимальная серия профитных сделок подряд"""
        if self.df_closed.empty or 'closedPnl' not in self.df_closed:
            return 0
        pnl = self.df_closed['closedPnl'].astype(float)
        max_streak = streak = 0
        for v in pnl:
            if v > 0:
                streak += 1
                max_streak = max(max_streak, streak)
            else:
                streak = 0
        return max_streak

    def summary(self) -> Dict[str, Any]:
        """Сводная статистика по истории сделок"""
        return {
            "winrate": self.winrate(),
            "avg_pnl": self.avg_pnl(),
            "avg_holding_time_min": self.avg_holding_time(),
            "sl_tp_stats": self.sl_tp_stats(),
            "max_loss_streak": self.loss_streak(),
            "max_profit_streak": self.profit_streak(),
            "total_trades": int(len(self.df_closed)),
        } 