#!/usr/bin/env python3
"""
Тестовый скрипт для проверки загрузки конфигурации
"""

import sys
import os

# Добавляем путь к backend
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

try:
    from utils.config import settings
    print(f"✅ Конфигурация загружена успешно")
    print(f"CLOSE_POSITIONS_ON_SHUTDOWN = {settings.close_positions_on_shutdown}")
    print(f"BYBIT_TESTNET = {settings.bybit_testnet}")
    print(f"TRADING_PAIRS = {settings.trading_pairs}")
except Exception as e:
    print(f"❌ Ошибка загрузки конфигурации: {e}")
    import traceback
    traceback.print_exc() 