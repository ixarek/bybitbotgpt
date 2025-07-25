from typing import Dict, Any, Tuple
import logging

logger = logging.getLogger(__name__)

def log_param_adjustment(symbol: str, old_params: Dict[str, Any], new_params: Dict[str, Any], log: str):
    from datetime import datetime
    import os
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "param_adjustments.log")
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"[{datetime.now().isoformat()}] {symbol}\nOLD: {old_params}\nNEW: {new_params}\nLOG: {log}\n---\n")

def adjust_params(summary: Dict[str, Any], current_params: Dict[str, Any]) -> Tuple[Dict[str, Any], str]:
    """
    Корректирует параметры торговли на основе summary-анализа истории сделок.
    Возвращает новые параметры и лог изменений.
    """
    log = []
    params = current_params.copy()
    # Примеры простых правил:
    # 1. Если серия убытков > 3 — уменьшить размер позиции
    if summary.get('max_loss_streak', 0) > 3:
        old = params.get('position_size', 1.0)
        params['position_size'] = max(0.1, old * 0.7)
        log.append(f"Серия убытков {summary['max_loss_streak']} > 3: уменьшен размер позиции с {old} до {params['position_size']}")
    # 2. Если winrate < 0.4 — уменьшить TP, увеличить SL
    if summary.get('winrate', 1.0) < 0.4:
        old_tp = params.get('take_profit', 0.03)
        old_sl = params.get('stop_loss', 0.01)
        params['take_profit'] = max(0.01, old_tp * 0.8)
        params['stop_loss'] = min(0.05, old_sl * 1.2)
        log.append(f"Winrate {summary['winrate']:.2f} < 0.4: TP {old_tp}->{params['take_profit']}, SL {old_sl}->{params['stop_loss']}")
    # 3. Если TP почти не срабатывает, а SL часто — уменьшить TP
    sl_tp = summary.get('sl_tp_stats', {})
    if sl_tp.get('sl', 0) > sl_tp.get('tp', 0) * 2 and sl_tp.get('sl', 0) > 2:
        old_tp = params.get('take_profit', 0.03)
        params['take_profit'] = max(0.01, old_tp * 0.8)
        log.append(f"SL ({sl_tp.get('sl')}) срабатывает чаще TP ({sl_tp.get('tp')}): TP уменьшен {old_tp}->{params['take_profit']}")
    # 4. Если средний PNL < 0 — уменьшить риск
    if summary.get('avg_pnl', 0) < 0:
        old = params.get('position_size', 1.0)
        params['position_size'] = max(0.1, old * 0.8)
        log.append(f"Средний PNL {summary['avg_pnl']:.4f} < 0: уменьшен размер позиции {old}->{params['position_size']}")
    # 5. Логировать все изменения
    if not log:
        log.append("Изменения не требуются. Параметры стабильны.")
    logger.info("; ".join(log))
    return params, "\n".join(log) 