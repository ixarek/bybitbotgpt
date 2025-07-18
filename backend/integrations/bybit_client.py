"""
Bybit API Client for Trading Bot
Handles REST API and WebSocket connections for trading operations
"""

import asyncio
import pandas as pd
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import time
import json
import numpy as np
from pybit.unified_trading import HTTP
import logging

logger = logging.getLogger(__name__)


class BybitClient:
    """
    Bybit API client for trading operations
    Supports both REST API and WebSocket connections
    """
    
    def __init__(self, api_key: Optional[str] = None, api_secret: Optional[str] = None, testnet: bool = True):
        self.api_key = api_key
        self.api_secret = api_secret
        self.testnet = testnet
        
        # Initialize pybit HTTP client
        self.session = HTTP(
            api_key=api_key or "",
            api_secret=api_secret or "",
            testnet=testnet
        )
        
        # Market data cache
        self.market_data = {}
        self.positions = {}
        self.account_info = {}
        
    async def initialize(self) -> bool:
        """Initialize the client and test connection"""
        try:
            logger.info("🔗 Initializing Bybit client...")
            
            # Test REST API connection
            server_time = await self.get_server_time()
            if server_time:
                logger.info(f"✅ Connected to Bybit {'testnet' if self.testnet else 'mainnet'}")
                return True
            else:
                logger.error("❌ Failed to connect to Bybit")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error initializing Bybit client: {e}")
            return False
    
    async def get_server_time(self) -> Optional[int]:
        """Get server time for testing connection"""
        try:
            response = self.session.get_server_time()
            if isinstance(response, tuple):
                response = response[0]
            if response.get('retCode') == 0:
                return int(response.get('result', {}).get('timeSecond', 0))
            return None
        except Exception as e:
            logger.error(f"Error getting server time: {e}")
            return None
    
    def get_kline(self, symbol: str, interval: str, limit: int = 200) -> Optional[pd.DataFrame]:
        """
        Get kline/candlestick data for technical analysis
        """
        try:
            logger.info(f"📊 Fetching real kline data for {symbol} {interval}")
            
            # Конвертируем интервал в формат Bybit API
            # Bybit поддерживает: 1, 3, 5, 15, 30, 60, 120, 240, 360, 720, D, W, M
            interval_map = {
                '1m': '1',
                '3m': '3', 
                '5m': '5',
                '15m': '15',
                '30m': '30',
                '1h': '60',
                '2h': '120',
                '4h': '240',
                '6h': '360',
                '12h': '720',
                '1d': 'D',
                '1w': 'W',
                '1M': 'M'
            }
            
            # Используем маппинг или оставляем как есть
            bybit_interval = interval_map.get(interval, interval)
            logger.info(f"🔄 Converted interval {interval} → {bybit_interval}")
            
            # Get real kline data from Bybit
            response = self.session.get_kline(
                category="linear",
                symbol=symbol,
                interval=bybit_interval,
                limit=limit
            )
            
            if isinstance(response, tuple):
                response = response[0]
            if response.get('retCode') != 0:
                logger.error(f"Bybit API error: {response.get('retMsg')}")
                return None
            
            # Convert to DataFrame
            klines = response.get('result', {}).get('list', [])
            if not klines:
                logger.warning(f"No kline data received for {symbol}")
                return None
            
            # Create DataFrame from kline data
            data = []
            for kline in reversed(klines):  # Bybit returns newest first
                data.append({
                    'timestamp': pd.to_datetime(int(kline[0]), unit='ms'),
                    'open': float(kline[1]),
                    'high': float(kline[2]),
                    'low': float(kline[3]),
                    'close': float(kline[4]),
                    'volume': float(kline[5])
                })
            
            df = pd.DataFrame(data)
            df.set_index('timestamp', inplace=True)
            
            logger.info(f"✅ Retrieved {len(df)} real candles for {symbol}")
            return df
            
        except Exception as e:
            logger.error(f"❌ Error fetching kline data for {symbol}: {e}")
            return None
    
    def safe_float(self, value, default=0.0):
        """Безопасное преобразование в float с обработкой пустых строк и None"""
        if value is None or value == '' or value == 'None':
            return default
        try:
            return float(value)
        except (ValueError, TypeError):
            return default
    
    def get_wallet_balance(self) -> Optional[Dict]:
        """Get real account balance information"""
        try:
            logger.info("💰 Fetching real wallet balance...")
            try:
                response = self.session.get_wallet_balance(accountType="UNIFIED")
            except TypeError:
                response = self.session.get_wallet_balance(account_type="UNIFIED")
            except Exception:
                response = self.session.get_wallet_balance()
            if isinstance(response, tuple):
                response = response[0]
            if response.get('retCode') != 0:
                logger.error(f"Balance API error: {response.get('retMsg')}")
                logger.error(f"Full response: {response}")
                return None
            balance_info = {}
            result_list = response.get('result', {}).get('list', [])
            if result_list:
                coins = result_list[0].get('coin', [])
                for coin in coins:
                    if self.safe_float(coin.get('walletBalance', 0)) > 0:
                        balance_info[coin.get('coin', '')] = {
                            "available": self.safe_float(coin.get('availableToWithdraw', 0)),
                            "locked": self.safe_float(coin.get('locked', 0)),
                            "total": self.safe_float(coin.get('walletBalance', 0))
                        }
            logger.info(f"✅ Retrieved real balance: {balance_info}")
            return balance_info
        except Exception as e:
            logger.error(f"❌ Error getting wallet balance: {e}")
            return None
    
    def get_positions(self, symbol: str = "") -> Optional[List[Dict]]:
        """Get real position information"""
        try:
            logger.info("📈 Fetching real positions...")
            params = {"category": "linear"}
            if symbol:
                params["symbol"] = symbol
            else:
                params["settleCoin"] = "USDT"  # По умолчанию USDT, если не указан symbol
            response = self.session.get_positions(**params)
            if isinstance(response, tuple):
                response = response[0]
            if response.get('retCode') != 0:
                logger.error(f"Positions API error: {response.get('retMsg')}")
                logger.error(f"Full response: {response}")
                return []
            positions = []
            position_list = response.get('result', {}).get('list', [])
            for position in position_list:
                try:
                    position_size = self.safe_float(position.get('size', 0))
                    position_value = self.safe_float(position.get('positionValue', 0))
                    unrealized_pnl = self.safe_float(position.get('unrealisedPnl', 0))
                    avg_price = self.safe_float(position.get('avgPrice', 0))
                    position_info = {
                        'symbol': position.get('symbol', ''),
                        'side': position.get('side', ''),
                        'size': position_size,
                        'entry_price': avg_price,
                        'unrealized_pnl': unrealized_pnl,
                        'percentage': unrealized_pnl / position_value * 100 if position_value > 0 else 0
                    }
                except Exception as e:
                    logger.warning(f"⚠️ Ошибка парсинга позиции {position.get('symbol', 'unknown')}: {e}")
                    continue
                if position_size > 0:
                    positions.append(position_info)
            logger.info(f"✅ Retrieved {len(positions)} active positions")
            return positions
        except Exception as e:
            logger.error(f"❌ Error getting positions: {e}")
            return []
    
    def get_ticker_price(self, symbol: str) -> Optional[float]:
        """Get current ticker price"""
        try:
            response = self.session.get_tickers(
                category="spot",
                symbol=symbol
            )
            
            if isinstance(response, tuple):
                response = response[0]
            if response.get('retCode') != 0:
                return None
            
            ticker_list = response.get('result', {}).get('list', [])
            if ticker_list:
                return float(ticker_list[0].get('lastPrice', 0))
            return None
            
        except Exception as e:
            logger.error(f"Error getting ticker for {symbol}: {e}")
            return None
    
    def get_current_price(self, symbol: str) -> Optional[float]:
        """Get current price for symbol (alias for get_ticker_price)"""
        try:
            # Определяем категорию
            category = "linear" if symbol.endswith("USDT") else "spot"
            
            response = self.session.get_tickers(
                category=category,
                symbol=symbol
            )
            
            if isinstance(response, tuple):
                response = response[0]
            if response.get('retCode') != 0:
                return None
            
            ticker_list = response.get('result', {}).get('list', [])
            if ticker_list:
                return float(ticker_list[0].get('lastPrice', 0))
            return None
            
        except Exception as e:
            logger.error(f"Error getting current price for {symbol}: {e}")
            return None
    
    async def place_order(
        self, 
        symbol: str, 
        side: str, 
        order_type: str, 
        qty: float,
        price: Optional[float] = None,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None
    ) -> Optional[Dict]:
        """Place a real trading order with TP/SL support"""
        try:
            logger.info(f"📋 Placing real {side} {order_type} order for {qty} {symbol}")
            
            # Определяем категорию
            category = "linear" if symbol and symbol.endswith("USDT") else "spot"
            
            # Базовые параметры ордера
            params = {
                "category": category,
                "symbol": symbol,
                "side": side,
                "orderType": order_type,
                "qty": str(qty),
                "timeInForce": "GTC"  # Good Till Cancelled
            }
            
            # Добавляем цену для лимитных ордеров
            if price is not None:
                params["price"] = str(price)
            
            # ✅ ИСПРАВЛЕНИЕ: Правильно добавляем TP/SL согласно документации Bybit API v5
            if take_profit is not None or stop_loss is not None:
                # Обязательный параметр tpslMode для linear категории
                if category == "linear":
                    params["tpslMode"] = "Full"  # Полная позиция TP/SL
                
                if take_profit is not None:
                    params["takeProfit"] = str(take_profit)
                    # Для Full mode только Market тип ордера
                    if category == "linear":
                        params["tpOrderType"] = "Market"
                    logger.info(f"   ✅ Take Profit: ${take_profit:.4f}")
                
                if stop_loss is not None:
                    params["stopLoss"] = str(stop_loss)
                    # Для Full mode только Market тип ордера
                    if category == "linear":
                        params["slOrderType"] = "Market"
                    logger.info(f"   ✅ Stop Loss: ${stop_loss:.4f}")
            
            # Для Linear позиций устанавливаем positionIdx
            if category == "linear":
                params["positionIdx"] = "0"  # One-way mode (строка, не число)
            
            logger.info(f"📋 Параметры ордера: {params}")
            
            # Отправляем ордер
            response = self.session.place_order(**params)
            
            if isinstance(response, tuple):
                response = response[0]
            
            # ✅ ИСПРАВЛЕНИЕ: Улучшенная обработка ошибок
            if response.get('retCode') != 0:
                error_code = response.get('retCode')
                error_msg = response.get('retMsg', 'Unknown error')
                
                logger.error(f"❌ Error placing real order: {error_msg} (ErrCode: {error_code}) (ErrTime: {datetime.now().strftime('%H:%M:%S')}).")
                logger.error(f"Request → POST https://api{'testnet' if self.testnet else ''}.bybit.com/v5/order/create: {json.dumps(params, indent=2)}")
                
                # Возвращаем структурированный ответ об ошибке
                return {
                    'retCode': error_code,
                    'retMsg': error_msg,
                    'success': False,
                    'error': error_msg
                }
                
            order_id = response.get('result', {}).get('orderId')
            if not order_id:
                logger.error(f"❌ orderId отсутствует в ответе Bybit! Response: {response}")
                return {
                    'retCode': -1,
                    'retMsg': 'No order ID in response',
                    'success': False,
                    'error': 'No order ID in response'
                }
                
            logger.info(f"✅ Real order placed successfully: {order_id}")
            
            # Если TP/SL не установились при создании ордера, попробуем установить отдельно (резервный механизм)
            if (take_profit is not None or stop_loss is not None) and category == "linear":
                await asyncio.sleep(1)  # Небольшая задержка
                # Проверяем, есть ли открытая позиция по символу
                positions = self.get_positions(symbol)
                has_position = False
                if positions:
                    for pos in positions:
                        if pos.get('symbol') == symbol and float(pos.get('size', 0)) != 0:
                            has_position = True
                            break
                
                if has_position:
                    logger.info(f"🔧 Попытка установить TP/SL отдельно для позиции {symbol}")
                    # Здесь можно добавить логику установки TP/SL отдельным запросом
            
            # ✅ ИСПРАВЛЕНИЕ: Возвращаем правильный формат ответа
            return {
                'retCode': 0,
                'retMsg': 'OK',
                'success': True,
                'result': response.get('result', {}),
                'orderId': order_id
            }
            
        except Exception as e:
            logger.error(f"❌ Exception in place_order: {str(e)}")
            return {
                'retCode': -1,
                'retMsg': str(e),
                'success': False,
                'error': str(e)
            }
    
    def get_order_status(self, order_id: str = "", symbol: str = "") -> Optional[Dict]:
        """Get order status by order ID"""
        try:
            logger.info(f"🔍 Checking order status for {order_id}")
            category = "linear" if symbol and symbol.endswith("USDT") else "spot"
            params = {"category": category}
            if symbol:
                params["symbol"] = symbol
            if order_id:
                params["orderId"] = order_id
            response = self.session.get_open_orders(**params)
            if isinstance(response, tuple):
                response = response[0]
            if response.get('retCode') != 0:
                logger.error(f"Order status API error: {response.get('retMsg')}")
                return None
            orders = response.get('result', {}).get('list', [])
            if orders:
                order = orders[0]
                return {
                    'orderId': order.get('orderId'),
                    'symbol': order.get('symbol'),
                    'orderStatus': order.get('orderStatus'),
                    'side': order.get('side'),
                    'qty': order.get('qty'),
                    'cumExecQty': order.get('cumExecQty', 0),
                    'avgPrice': order.get('avgPrice', 0),
                    'orderType': order.get('orderType'),
                    'createdTime': order.get('createdTime')
                }
            else:
                logger.warning(f"Order {order_id} not found in open orders")
                return None
        except Exception as e:
            logger.error(f"❌ Error getting order status: {e}")
            return None
    
    def set_trading_stop(
        self, 
        symbol: str = "", 
        take_profit: Optional[float] = None, 
        stop_loss: Optional[float] = None,
        tpsl_mode: str = "Full",
        position_idx: int = 0
    ) -> Optional[Dict]:
        """
        Установка TP/SL для позиции согласно официальной документации Bybit
        https://bybit-exchange.github.io/docs/v5/position/trading-stop
        """
        try:
            logger.info(f"🛡️ Установка TP/SL для {symbol}")
            category = "linear" if symbol and symbol.endswith("USDT") else "spot"
            params = {
                "category": category,
                "tpslMode": tpsl_mode,
                "positionIdx": position_idx
            }
            if symbol:
                params["symbol"] = symbol
            if take_profit is not None:
                params["takeProfit"] = str(take_profit)
                logger.info(f"   Take Profit: ${take_profit:.2f}")
            if stop_loss is not None:
                params["stopLoss"] = str(stop_loss)
                logger.info(f"   Stop Loss: ${stop_loss:.2f}")
            response = self.session.set_trading_stop(**params)
            if isinstance(response, tuple):
                response = response[0]
            if response.get('retCode') == 0:
                logger.info("✅ TP/SL успешно установлены")
                return response
            else:
                # Фильтруем ошибку "not modified" (ErrCode: 34040) — это не критично
                if response.get('retCode') == 34040 or 'not modified' in str(response.get('retMsg', '')).lower():
                    logger.info(f"ℹ️ TP/SL уже были установлены, повторная установка не требуется ({response.get('retMsg')})")
                else:
                    error_msg = response.get('retMsg', 'Unknown error')
                    logger.error(f"❌ Ошибка установки TP/SL: {error_msg}")
                return response
        except Exception as e:
            logger.error(f"❌ Исключение при установке TP/SL: {e}")
            return None
    
    def get_open_orders(self, symbol: str = "", order_id: str = "") -> Optional[Dict]:
        """
        Получение открытых и недавно закрытых ордеров
        https://bybit-exchange.github.io/docs/v5/order/open-order
        """
        try:
            logger.info(f"📋 Получение ордеров{' для ' + symbol if symbol else ''}")
            params = {
                "category": "linear",
                "openOnly": 0,
                "limit": 50
            }
            if symbol:
                params["symbol"] = symbol
            if order_id:
                params["orderId"] = order_id
            response = self.session.get_open_orders(**params)
            if isinstance(response, tuple):
                response = response[0]
            if response.get('retCode') == 0:
                orders_count = len(response.get('result', {}).get('list', []))
                logger.info(f"✅ Получено ордеров: {orders_count}")
                return response
            else:
                error_msg = response.get('retMsg', 'Unknown error')
                logger.error(f"❌ Ошибка получения ордеров: {error_msg}")
                return response
        except Exception as e:
            logger.error(f"❌ Исключение при получении ордеров: {e}")
            return None
    
    def get_balance(self) -> float:
        """Получение баланса USDT"""
        try:
            logger.info("💰 Получение баланса...")
            
            response = self.session.get_wallet_balance(
                accountType="UNIFIED"
            )
            
            if isinstance(response, tuple):
                response = response[0]
            
            if response.get('retCode') != 0:
                logger.error(f"Balance API error: {response.get('retMsg')}")
                return 0.0
            
            # Извлекаем баланс USDT
            account_list = response.get('result', {}).get('list', [])
            if account_list:
                coins = account_list[0].get('coin', [])
                for coin in coins:
                    if coin.get('coin') == 'USDT':
                        balance = float(coin.get('walletBalance', 0))
                        logger.info(f"✅ Баланс USDT: ${balance:.2f}")
                        return balance
            
            logger.warning("⚠️ USDT баланс не найден")
            return 0.0
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения баланса: {e}")
            return 0.0


# Global client instance
bybit_client = None


async def get_bybit_client(api_key: Optional[str] = None, api_secret: Optional[str] = None, testnet: bool = True) -> BybitClient:
    """Get or create Bybit client instance"""
    global bybit_client
    
    if bybit_client is None:
        bybit_client = BybitClient(api_key, api_secret, testnet)
        await bybit_client.initialize()
    
    return bybit_client 