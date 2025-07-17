#!/usr/bin/env python3
"""
Простой тест для проверки на каком порту запускается сервер
"""

import sys
import os
sys.path.append(os.getcwd())

if __name__ == "__main__":
    print("🔍 Проверка настроек сервера...")
    
    # Импортируем main модуль
    try:
        from backend.main import app
        print("✅ Модуль backend.main успешно импортирован")
        
        # Проверяем что сервер запустится на правильном порту
        import uvicorn
        print("🚀 Запуск тестового сервера на порту 5000...")
        
        uvicorn.run(
            app,
            host="127.0.0.1", 
            port=5000,
            log_level="info"
        )
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        input("Нажмите Enter для выхода...") 