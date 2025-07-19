# -*- coding: utf-8 -*-
"""
Простой тест demo аккаунта Bybit
"""
import asyncio
from pybit.unified_trading import HTTP

def test_demo():
    print("=== ТЕСТ DEMO АККАУНТА BYBIT ===")
    
    # Настоящие API ключи от demo аккаунта
    api_key = "2rLTI1pEuKBhPH4zH0"
    api_secret = "0X3kdD5KvmZ0ItpOI2ktqGgX5kACJO5jCwPo"
    
    print(f"API Key: {api_key[:10]}...")
    print("Создаем demo сессию...")
    
    try:
        # Создаем pybit сессию для demo
        session = HTTP(
            api_key=api_key,
            api_secret=api_secret,
            testnet=False,  # ВАЖНО: для demo testnet=False
            demo=True       # Включаем demo режим
        )
        
        print("Подключение создано!")
        
        # Тест рыночных данных BTC
        print("\nТестируем рыночные данные...")
        try:
            klines_response = session.get_kline(
                category="linear",
                symbol="BTCUSDT", 
                interval="5",
                limit=1
            )
            
            # Обрабатываем tuple ответ от pybit
            if isinstance(klines_response, tuple):
                klines = klines_response[0]
            else:
                klines = klines_response
            
            if klines.get('retCode') == 0:
                price = float(klines['result']['list'][0][4])
                print(f"BTC цена: ${price:,.2f}")
                
                if price > 100000:
                    print("✅ ОТЛИЧНО! Реальные цены 2025!")
                else:
                    print("❌ Старые цены - все еще testnet")
            else:
                print(f"Ошибка получения цены: {klines}")
                
        except Exception as e:
            print(f"Ошибка рыночных данных: {e}")
            
        # Тест баланса
        print("\nТестируем баланс...")
        try:
            balance_response = session.get_wallet_balance(accountType="UNIFIED")
            
            # Обрабатываем tuple ответ от pybit  
            if isinstance(balance_response, tuple):
                balance = balance_response[0]
            else:
                balance = balance_response
            
            if balance.get('retCode') == 0:
                coins = balance['result']['list'][0]['coin']
                for coin in coins:
                    if coin['coin'] == 'USDT':
                        bal = float(coin['walletBalance'])
                        print(f"USDT баланс: ${bal:,.2f}")
                        
                        if bal >= 10000:
                            print("✅ DEMO баланс правильный!")
                        else:
                            print(f"⚠️ Баланс: ${bal:,.2f}")
                        break
            else:
                print(f"Ошибка баланса: {balance}")
                
        except Exception as e:
            print(f"Ошибка баланса: {e}")
            
    except Exception as e:
        print(f"Общая ошибка: {e}")

if __name__ == "__main__":
    test_demo() 