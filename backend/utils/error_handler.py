#!/usr/bin/env python3
"""
Централизованная система обработки ошибок для торгового бота
Основано на лучших практиках: https://dev.to/ctrlaltvictoria/backend-error-handling-practical-tips-from-a-startup-cto-h6
"""

import logging
import traceback
from typing import Dict, Any, Optional
from enum import Enum

logger = logging.getLogger(__name__)

class ErrorType(Enum):
    """Типы ошибок в системе"""
    API_ERROR = "api_error"
    VALIDATION_ERROR = "validation_error"
    DATABASE_ERROR = "database_error"
    NETWORK_ERROR = "network_error"
    CONVERSION_ERROR = "conversion_error"
    AUTHENTICATION_ERROR = "auth_error"
    RATE_LIMIT_ERROR = "rate_limit_error"
    UNKNOWN_ERROR = "unknown_error"

class TradingBotError(Exception):
    """Базовый класс для ошибок торгового бота"""
    def __init__(self, message: str, error_type: ErrorType = ErrorType.UNKNOWN_ERROR, details: Dict[str, Any] = None):
        super().__init__(message)
        self.message = message
        self.error_type = error_type
        self.details = details or {}
        self.timestamp = None

class APIError(TradingBotError):
    """Ошибки API"""
    def __init__(self, message: str, api_response: Dict = None, status_code: int = None):
        super().__init__(message, ErrorType.API_ERROR)
        self.details.update({
            'api_response': api_response,
            'status_code': status_code
        })

class ValidationError(TradingBotError):
    """Ошибки валидации данных"""
    def __init__(self, message: str, field: str = None, value: Any = None):
        super().__init__(message, ErrorType.VALIDATION_ERROR)
        self.details.update({
            'field': field,
            'value': value
        })

class ConversionError(TradingBotError):
    """Ошибки конвертации данных"""
    def __init__(self, message: str, original_value: Any = None, target_type: str = None):
        super().__init__(message, ErrorType.CONVERSION_ERROR)
        self.details.update({
            'original_value': original_value,
            'target_type': target_type
        })

class NetworkError(TradingBotError):
    """Ошибки сети"""
    def __init__(self, message: str, url: str = None, timeout: float = None):
        super().__init__(message, ErrorType.NETWORK_ERROR)
        self.details.update({
            'url': url,
            'timeout': timeout
        })

class ErrorHandler:
    """Централизованный обработчик ошибок"""
    
    @staticmethod
    def safe_float_conversion(value: Any, default: float = 0.0, field_name: str = "unknown") -> float:
        """Безопасная конвертация в float с детальным логированием"""
        try:
            if value is None or value == '':
                logger.debug(f"🔄 {field_name}: пустое значение, используем default={default}")
                return default
            
            result = float(value)
            logger.debug(f"✅ {field_name}: {value} → {result}")
            return result
            
        except (ValueError, TypeError) as e:
            logger.warning(f"⚠️ Ошибка конвертации {field_name}: '{value}' → float. Используем default={default}")
            raise ConversionError(
                f"Не удалось конвертировать '{value}' в float для поля '{field_name}'",
                original_value=value,
                target_type="float"
            )
    
    @staticmethod
    def safe_int_conversion(value: Any, default: int = 0, field_name: str = "unknown") -> int:
        """Безопасная конвертация в int"""
        try:
            if value is None or value == '':
                return default
            return int(float(value))  # Через float для обработки "123.0"
        except (ValueError, TypeError):
            logger.warning(f"⚠️ Ошибка конвертации {field_name}: '{value}' → int. Используем default={default}")
            raise ConversionError(
                f"Не удалось конвертировать '{value}' в int для поля '{field_name}'",
                original_value=value,
                target_type="int"
            )
    
    @staticmethod
    def handle_api_response(response: Dict, operation: str = "API call") -> Dict:
        """Обработка ответов API с централизованной обработкой ошибок"""
        try:
            # Обработка tuple ответов
            if isinstance(response, tuple):
                response = response[0]
            
            # Проверка кода ответа
            ret_code = response.get('retCode', -1)
            if ret_code != 0:
                error_msg = response.get('retMsg', 'Unknown API error')
                logger.error(f"❌ {operation} failed: {error_msg} (Code: {ret_code})")
                
                # Определяем тип ошибки по коду
                if ret_code == 401:
                    error_type = ErrorType.AUTHENTICATION_ERROR
                elif ret_code == 10001:
                    error_type = ErrorType.VALIDATION_ERROR
                elif ret_code in [10002, 10003]:
                    error_type = ErrorType.RATE_LIMIT_ERROR
                else:
                    error_type = ErrorType.API_ERROR
                
                raise APIError(
                    f"{operation} failed: {error_msg}",
                    api_response=response,
                    status_code=ret_code
                )
            
            logger.debug(f"✅ {operation} successful")
            return response
            
        except APIError:
            raise  # Перебрасываем наши ошибки
        except Exception as e:
            logger.error(f"❌ Unexpected error in {operation}: {e}")
            raise TradingBotError(f"Unexpected error in {operation}: {str(e)}")
    
    @staticmethod
    def log_error(error: Exception, context: Dict[str, Any] = None):
        """Централизованное логирование ошибок"""
        context = context or {}
        
        if isinstance(error, TradingBotError):
            logger.error(f"🚨 {error.error_type.value.upper()}: {error.message}")
            if error.details:
                logger.error(f"📋 Details: {error.details}")
        else:
            logger.error(f"💥 UNEXPECTED ERROR: {str(error)}")
            logger.error(f"📋 Context: {context}")
            logger.error(f"📍 Traceback: {traceback.format_exc()}")
    
    @staticmethod
    def create_error_response(error: Exception, include_details: bool = False) -> Dict[str, Any]:
        """Создание стандартизированного ответа об ошибке"""
        if isinstance(error, TradingBotError):
            response = {
                'success': False,
                'error': error.message,
                'error_type': error.error_type.value
            }
            
            if include_details and error.details:
                response['details'] = error.details
                
            return response
        else:
            return {
                'success': False,
                'error': 'Internal server error',
                'error_type': ErrorType.UNKNOWN_ERROR.value
            }

# Декоратор для автоматической обработки ошибок
def handle_errors(operation_name: str = "Operation"):
    """Декоратор для автоматической обработки ошибок в методах"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except TradingBotError as e:
                ErrorHandler.log_error(e, {'operation': operation_name, 'args': args, 'kwargs': kwargs})
                return ErrorHandler.create_error_response(e)
            except Exception as e:
                ErrorHandler.log_error(e, {'operation': operation_name, 'args': args, 'kwargs': kwargs})
                return ErrorHandler.create_error_response(e)
        return wrapper
    return decorator

# Async версия декоратора
def handle_errors_async(operation_name: str = "Async Operation"):
    """Декоратор для автоматической обработки ошибок в async методах"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except TradingBotError as e:
                ErrorHandler.log_error(e, {'operation': operation_name, 'args': args, 'kwargs': kwargs})
                return ErrorHandler.create_error_response(e)
            except Exception as e:
                ErrorHandler.log_error(e, {'operation': operation_name, 'args': args, 'kwargs': kwargs})
                return ErrorHandler.create_error_response(e)
        return wrapper
    return decorator 