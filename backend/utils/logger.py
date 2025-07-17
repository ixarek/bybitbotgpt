"""
Logging setup for Bybit Trading Bot
"""

import logging
import logging.handlers
import os
from datetime import datetime
from typing import Optional


def setup_logging(log_level: str = "INFO", log_file: Optional[str] = None) -> None:
    """
    Setup logging configuration for the trading bot
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
        log_file: Optional log file path
    """
    
    # Create logs directory if it doesn't exist
    logs_dir = "logs"
    if not os.path.exists(logs_dir):
        os.makedirs(logs_dir)
    
    # Set default log file if not provided
    if log_file is None:
        timestamp = datetime.now().strftime("%Y%m%d")
        log_file = os.path.join(logs_dir, f"trading_bot_{timestamp}.log")
    
    # Configure logging format
    log_format = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"
    
    # Create formatter
    formatter = logging.Formatter(log_format, date_format)
    
    # Setup root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper()))
    
    # Clear existing handlers
    root_logger.handlers.clear()
    
    # Console handler with UTF-8 encoding
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    
    # Set UTF-8 encoding for console on Windows
    if hasattr(console_handler.stream, 'reconfigure'):
        try:
            console_handler.stream.reconfigure(encoding='utf-8')
        except:
            pass  # If reconfigure fails, continue with default
    
    root_logger.addHandler(console_handler)
    
    # File handler with rotation
    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(getattr(logging, log_level.upper()))
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)
    
    # Error file handler
    error_log_file = os.path.join(logs_dir, "errors.log")
    error_handler = logging.handlers.RotatingFileHandler(
        error_log_file,
        maxBytes=5 * 1024 * 1024,  # 5MB
        backupCount=3,
        encoding='utf-8'
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)
    root_logger.addHandler(error_handler)
    
    # Suppress noisy loggers
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    
    logging.info("[INIT] Logging system initialized")


class WebSocketLogHandler(logging.Handler):
    """
    Custom log handler that sends logs to WebSocket clients
    """
    
    def __init__(self):
        super().__init__()
        self.websocket_clients = []
        self.setLevel(logging.INFO)
        
        # Format for web interface
        formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
        self.setFormatter(formatter)
    
    def add_client(self, websocket):
        """Add a WebSocket client"""
        if websocket not in self.websocket_clients:
            self.websocket_clients.append(websocket)
    
    def remove_client(self, websocket):
        """Remove a WebSocket client"""
        if websocket in self.websocket_clients:
            self.websocket_clients.remove(websocket)
    
    def emit(self, record):
        """Emit log record to WebSocket clients"""
        try:
            log_entry = self.format(record)
            
            # Determine log type for color coding
            log_type = "info"
            if record.levelno >= logging.ERROR:
                log_type = "error"
            elif record.levelno >= logging.WARNING:
                log_type = "warning"
            elif "[SIGNAL]" in log_entry or "[TRADE]" in log_entry:
                log_type = "success"
            
            message = {
                "type": "log",
                "data": {
                    "message": log_entry,
                    "level": record.levelname,
                    "log_type": log_type,
                    "timestamp": datetime.now().isoformat()
                }
            }
            
            # Send to all connected clients
            import asyncio
            import json
            
            for client in self.websocket_clients[:]:  # Copy list to avoid modification during iteration
                try:
                    if hasattr(client, 'send'):
                        # Sync WebSocket
                        client.send(json.dumps(message))
                    elif hasattr(client, 'send_text'):
                        # Async WebSocket - schedule coroutine
                        asyncio.create_task(client.send_text(json.dumps(message)))
                except Exception as e:
                    # Remove failed clients
                    self.remove_client(client)
                    
        except Exception as e:
            # Don't let logging errors break the application
            pass


# Global WebSocket log handler instance
websocket_log_handler = WebSocketLogHandler()


def add_websocket_logging():
    """Add WebSocket logging to the root logger"""
    root_logger = logging.getLogger()
    if websocket_log_handler not in root_logger.handlers:
        root_logger.addHandler(websocket_log_handler)


def get_websocket_handler() -> WebSocketLogHandler:
    """Get the global WebSocket log handler"""
    return websocket_log_handler 