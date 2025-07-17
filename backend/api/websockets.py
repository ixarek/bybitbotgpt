"""
WebSocket Manager for real-time communication with frontend
Handles client connections and broadcasts trading data
"""

import asyncio
import json
from typing import Dict, List, Set
from datetime import datetime
from fastapi import WebSocket, WebSocketDisconnect


class WebSocketManager:
    """
    Manages WebSocket connections for real-time trading data
    """
    
    def __init__(self):
        # Active WebSocket connections
        self.active_connections: Set[WebSocket] = set()
        
        # Connection metadata
        self.connection_data: Dict[WebSocket, Dict] = {}
        
    async def connect(self, websocket: WebSocket, client_id: str = None):
        """Accept a new WebSocket connection"""
        try:
            await websocket.accept()
            self.active_connections.add(websocket)
            
            # Store connection metadata
            self.connection_data[websocket] = {
                "client_id": client_id or f"client_{len(self.active_connections)}",
                "connected_at": datetime.now(),
                "subscriptions": set()
            }
            
            print(f"🔗 New WebSocket connection: {self.connection_data[websocket]['client_id']}")
            
            # Send welcome message
            await self.send_personal_message({
                "type": "connection",
                "status": "connected",
                "client_id": self.connection_data[websocket]["client_id"],
                "timestamp": datetime.now().isoformat()
            }, websocket)
            
        except Exception as e:
            print(f"❌ Error connecting WebSocket: {e}")
    
    async def disconnect(self, websocket: WebSocket):
        """Remove a WebSocket connection"""
        try:
            if websocket in self.active_connections:
                client_id = self.connection_data.get(websocket, {}).get("client_id", "unknown")
                
                self.active_connections.remove(websocket)
                del self.connection_data[websocket]
                
                print(f"🔌 WebSocket disconnected: {client_id}")
                
        except Exception as e:
            print(f"❌ Error disconnecting WebSocket: {e}")
    
    async def send_personal_message(self, message: Dict, websocket: WebSocket):
        """Send a message to a specific WebSocket connection"""
        try:
            await websocket.send_text(json.dumps(message))
        except Exception as e:
            print(f"❌ Error sending personal message: {e}")
    
    async def broadcast(self, message: Dict):
        """Broadcast a message to all connected clients"""
        if not self.active_connections:
            return
            
        # Prepare message with timestamp
        message["timestamp"] = datetime.now().isoformat()
        message_text = json.dumps(message)
        
        # Send to all active connections
        disconnected = set()
        for websocket in self.active_connections:
            try:
                await websocket.send_text(message_text)
            except Exception as e:
                print(f"❌ Error broadcasting to client: {e}")
                disconnected.add(websocket)
        
        # Remove disconnected clients
        for websocket in disconnected:
            await self.disconnect(websocket)
    
    async def broadcast_trading_signal(self, signal_data: Dict):
        """Broadcast trading signal to all clients"""
        message = {
            "type": "trading_signal",
            "data": signal_data
        }
        await self.broadcast(message)
    
    async def broadcast_market_data(self, market_data: Dict):
        """Broadcast market data to all clients"""
        message = {
            "type": "market_data",
            "data": market_data
        }
        await self.broadcast(message)
    
    async def broadcast_order_update(self, order_data: Dict):
        """Broadcast order update to all clients"""
        message = {
            "type": "order_update",
            "data": order_data
        }
        await self.broadcast(message)
    
    async def broadcast_balance_update(self, balance_data: Dict):
        """Broadcast balance update to all clients"""
        message = {
            "type": "balance_update",
            "data": balance_data
        }
        await self.broadcast(message)
    
    async def broadcast_log_message(self, log_data: Dict):
        """Broadcast log message to all clients"""
        message = {
            "type": "log_message",
            "data": log_data
        }
        await self.broadcast(message)
    
    async def handle_message(self, websocket: WebSocket, message: str):
        """Handle incoming messages from clients"""
        try:
            data = json.loads(message)
            message_type = data.get("type")
            
            if message_type == "subscribe":
                await self._handle_subscription(websocket, data)
            elif message_type == "unsubscribe":
                await self._handle_unsubscription(websocket, data)
            elif message_type == "ping":
                await self._handle_ping(websocket)
            else:
                print(f"⚠️ Unknown message type: {message_type}")
                
        except json.JSONDecodeError:
            await self.send_personal_message({
                "type": "error",
                "message": "Invalid JSON format"
            }, websocket)
        except Exception as e:
            print(f"❌ Error handling message: {e}")
    
    async def _handle_subscription(self, websocket: WebSocket, data: Dict):
        """Handle subscription requests"""
        try:
            channel = data.get("channel")
            if channel and websocket in self.connection_data:
                self.connection_data[websocket]["subscriptions"].add(channel)
                
                await self.send_personal_message({
                    "type": "subscription_confirmed",
                    "channel": channel,
                    "status": "subscribed"
                }, websocket)
                
                print(f"📡 Client subscribed to {channel}")
        except Exception as e:
            print(f"❌ Error handling subscription: {e}")
    
    async def _handle_unsubscription(self, websocket: WebSocket, data: Dict):
        """Handle unsubscription requests"""
        try:
            channel = data.get("channel")
            if channel and websocket in self.connection_data:
                self.connection_data[websocket]["subscriptions"].discard(channel)
                
                await self.send_personal_message({
                    "type": "unsubscription_confirmed",
                    "channel": channel,
                    "status": "unsubscribed"
                }, websocket)
                
                print(f"📡 Client unsubscribed from {channel}")
        except Exception as e:
            print(f"❌ Error handling unsubscription: {e}")
    
    async def _handle_ping(self, websocket: WebSocket):
        """Handle ping messages"""
        await self.send_personal_message({
            "type": "pong",
            "timestamp": datetime.now().isoformat()
        }, websocket)
    
    def get_connection_count(self) -> int:
        """Get number of active connections"""
        return len(self.active_connections)
    
    def get_connection_info(self) -> List[Dict]:
        """Get information about all connections"""
        info = []
        for websocket, data in self.connection_data.items():
            info.append({
                "client_id": data["client_id"],
                "connected_at": data["connected_at"].isoformat(),
                "subscriptions": list(data["subscriptions"])
            })
        return info


# Global WebSocket manager instance
websocket_manager = WebSocketManager() 