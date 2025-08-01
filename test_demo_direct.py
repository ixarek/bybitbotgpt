"""
Прямой тест demo аккаунта Bybit с реальными ценами
"""
import asyncio
import sys
from pathlib import Path

# Добавляем путь к backend модулям
sys.path.insert(0, str(Path(__file__).parent))

from backend.integrations.bybit_client import BybitClient

async def test_demo_direct():
    """Прямое тестирование demo аккаунта с реальными ценами"""
    print("=== ПРЯМОЙ ТЕСТ DEMO АККАУНТА BYBIT ===\n")
    
    # Прямые параметры для demo режима
    api_key = "17OnwXNKgOcgnfbB4e"
    api_secret = "5ra0Ec0UIldYid2mOVz1APW0uTMJwZqglB1o"
    
    print(f"📋 Параметры подключения:")
    print(f"  API Key: {api_key[:10]}...")
    print(f"  Testnet: False (demo режим)")
    print(f"  Demo: True (реальные цены)")
    print()
    
    try:
        # Создаем клиент с demo параметрами (testnet=False, demo=True)
        client = BybitClient(
            api_key=api_key,
            api_secret=api_secret,
            testnet=False,  # ВАЖНО: для demo режима testnet=False
            demo=True,      # Включаем demo режим
            ignore_ssl=True
        )
        
        print("🔗 Инициализация demo клиента...")
        success = await client.initialize()
        
        if success:
            print("✅ Подключение к demo аккаунту с реальными ценами успешно!")
            
            # Тестируем получение времени сервера
            print("\n⏰ Тест получения времени сервера...")
            server_time = await client.get_server_time()
            print(f"Время сервера: {server_time}")
            
            # Тестируем получение рыночных данных с реальными ценами
            print("\n📊 Тест получения реальных рыночных данных...")
            klines = client.get_kline("BTCUSDT", "5", limit=5)
            if klines is not None and not klines.empty:
                last_price = klines['close'].iloc[-1]
                print(f"✅ Получено свечей: {len(klines)}")
                print(f"🎯 Текущая цена BTC: ${last_price:,.2f}")
                
                # Проверяем что цена реалистичная для 2025 года
                if last_price > 100000:
                    print("✅ Цена соответствует реальному рынку 2025 года!")
                else:
                    print("⚠️ Цена кажется устаревшей, возможно подключение к testnet")
            else:
                print("❌ Рыночные данные не получены")
                
            # Тестируем получение баланса demo аккаунта
            print("\n💰 Тест получения баланса demo аккаунта...")
            balance = client.get_wallet_balance()
            if balance:
                print("💰 Баланс demo аккаунта:")
                for coin, info in balance.items():
                    if info['total'] > 0:
                        print(f"  {coin}: {info['total']:,.2f} (доступно: {info['available']:,.2f})")
            else:
                print("ℹ️ Баланс demo аккаунта пустой или недоступен")
                
            # Тестируем получение позиций
            print("\n📈 Тест получения позиций demo аккаунта...")
            positions = client.get_positions()
            if positions:
                print(f"📊 Найдено позиций: {len(positions)}")
                for pos in positions:
                    print(f"  {pos['symbol']}: {pos['side']} {pos['size']} (PnL: {pos['unrealized_pnl']:.2f})")
            else:
                print("ℹ️ Активных позиций в demo аккаунте нет")
                
        else:
            print("❌ Не удалось подключиться к demo аккаунту")
            
    except Exception as e:
        print(f"❌ Ошибка при тестировании: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_demo_direct()) 