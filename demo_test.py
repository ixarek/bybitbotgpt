import asyncio
from pybit.unified_trading import HTTP

async def test():
    session = HTTP(api_key="2rLTI1pEuKBhPH4zH0", api_secret="0X3kdD5KvmZ0ItpOI2ktqGgX5kACJO5jCwPo", testnet=False, demo=True)
    
    print("Тестируем demo аккаунт...")
    
    # Тест рыночных данных
    klines = session.get_kline(category="linear", symbol="BTCUSDT", interval="5", limit=1)
    if isinstance(klines, tuple): klines = klines[0]
    
    if klines.get("retCode") == 0:
        price = float(klines["result"]["list"][0][4])
        print(f"BTC цена: ${price:,.2f}")
        if price > 100000:
            print(" РЕАЛЬНЫЕ ЦЕНЫ!")
        else:
            print(" Старые цены")
    
    # Тест баланса
    balance = session.get_wallet_balance(accountType="UNIFIED")
    if isinstance(balance, tuple): balance = balance[0]
    
    if balance.get("retCode") == 0:
        coins = balance["result"]["list"][0]["coin"]
        for coin in coins:
            if coin["coin"] == "USDT":
                bal = float(coin["walletBalance"])
                print(f"USDT баланс: ${bal:,.2f}")
                break

asyncio.run(test())
