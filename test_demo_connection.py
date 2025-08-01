"""
Тестовый скрипт для проверки подключения к demo аккаунту Bybit
"""
import asyncio
import os
import sys
from pathlib import Path

# Добавляем путь к backend модулям
sys.path.insert(0, str(Path(__file__).parent))

from backend.integrations.bybit_client import BybitClient
from backend.utils.config import settings

async def test_demo_connection():
    """Тестирование подключения к demo аккаунту"""
    print("=== ТЕСТ ПОДКЛЮЧЕНИЯ К DEMO АККАУНТУ BYBIT ===\n")
    
    print(f"📋 Параметры подключения:")
    print(f"  API Key: {settings.bybit_api_key[:10] if settings.bybit_api_key else 'НЕ ЗАДАН'}...")
    print(f"  Testnet: {settings.bybit_testnet}")
    print(f"  Demo: {settings.bybit_demo}")
    print()
    
    try:
        # Создаем клиент с demo параметрами
        client = BybitClient(
            api_key=settings.bybit_api_key,
            api_secret=settings.bybit_api_secret,
            testnet=settings.bybit_testnet,
            demo=settings.bybit_demo,
            ignore_ssl=settings.bybit_ignore_ssl
        )
        
        print("🔗 Инициализация клиента...")
        success = await client.initialize()
        
        if success:
            print("✅ Подключение к demo аккаунту успешно!")
            
            # Тестируем получение времени сервера
            print("\n⏰ Тест получения времени сервера...")
            server_time = await client.get_server_time()
            print(f"Время сервера: {server_time}")
            
            # Тестируем получение баланса
            print("\n💰 Тест получения баланса...")
            balance = client.get_wallet_balance()
            if balance:
                print("Баланс demo аккаунта:")
                for coin, info in balance.items():
                    if info['total'] > 0:
                        print(f"  {coin}: {info['total']:.2f} (доступно: {info['available']:.2f})")
            else:
                print("Баланс не получен")
                
            # Тестируем получение позиций
            print("\n📈 Тест получения позиций...")
            positions = client.get_positions()
            if positions:
                print(f"Найдено позиций: {len(positions)}")
                for pos in positions:
                    print(f"  {pos['symbol']}: {pos['side']} {pos['size']} (PnL: {pos['unrealized_pnl']:.2f})")
            else:
                print("Активных позиций нет")
                
            # Тестируем получение рыночных данных
            print("\n📊 Тест получения рыночных данных...")
            klines = client.get_kline("BTCUSDT", "5", limit=5)
            if klines is not None and not klines.empty:
                print(f"Получено свечей: {len(klines)}")
                print(f"Последняя цена BTC: ${klines['close'].iloc[-1]:.2f}")
            else:
                print("Рыночные данные не получены")
                
        else:
            print("❌ Не удалось подключиться к demo аккаунту")
            
    except Exception as e:
        print(f"❌ Ошибка при тестировании: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_demo_connection()) 