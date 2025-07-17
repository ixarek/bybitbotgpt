@echo off
chcp 65001 >nul
title Установка зависимостей Bybit Trading Bot

echo.
echo ╔══════════════════════════════════════════════════════════╗
echo ║            УСТАНОВКА ЗАВИСИМОСТЕЙ v3.0                  ║
echo ║        Решение проблем с компиляцией пакетов             ║
echo ╚══════════════════════════════════════════════════════════╝
echo.

:: Активируем виртуальное окружение если есть
if exist "venv\Scripts\activate.bat" (
    echo 🔧 Активация виртуального окружения...
    call venv\Scripts\activate.bat
) else (
    echo ⚠️  Используется системный Python
)

echo 📋 Стратегия установки:
echo 1. Попытка установки предкомпилированных пакетов
echo 2. Установка основных компонентов по отдельности
echo 3. Проверка совместимости
echo.

:: Обновляем pip
echo 🔄 Обновление pip...
python -m pip install --upgrade pip

:: Устанавливаем wheel для работы с предкомпилированными пакетами
echo 🔧 Установка wheel...
pip install wheel

echo.
echo 📦 Шаг 1: Установка основных компонентов...

:: Устанавливаем основные зависимости по одной
echo 🌐 FastAPI и Uvicorn...
pip install fastapi==0.104.1
pip install "uvicorn[standard]==0.24.0"

echo 🔗 WebSockets...
pip install websockets==12.0

echo ⚙️ Конфигурация...
pip install pydantic==2.5.0
pip install pydantic-settings
pip install python-dotenv==1.0.0

echo 🌍 HTTP клиент...
pip install requests

echo.
echo 📊 Шаг 2: Установка аналитических пакетов...

:: Сначала пытаемся установить pandas с предкомпилированными пакетами
echo 🐼 Pandas (с предкомпилированными пакетами)...
pip install --only-binary=pandas pandas>=2.1.0
if %errorlevel% neq 0 (
    echo ⚠️ Попытка установки без компиляции...
    pip install --prefer-binary pandas>=2.1.0
    if %errorlevel% neq 0 (
        echo ❌ Ошибка установки pandas!
        echo 💡 Попробуйте установить Anaconda или Miniconda
        echo 💡 Или используйте: pip install pandas --no-build-isolation
    )
)

echo.
echo 🔗 Шаг 3: Bybit API клиент...
pip install pybit==5.7.0

echo.
echo ✅ Проверка установки...
python -c "
try:
    import fastapi
    import uvicorn
    import websockets
    import pydantic
    import requests
    import pandas
    import pybit
    print('✅ Все основные пакеты установлены успешно!')
except ImportError as e:
    print(f'❌ Ошибка импорта: {e}')
    print('💡 Попробуйте переустановить проблемный пакет')
"

echo.
echo 📋 Установленные пакеты:
pip list | findstr -i "fastapi uvicorn websockets pydantic requests pandas pybit"

echo.
if %errorlevel% equ 0 (
    echo ✅ Установка завершена успешно!
    echo 🚀 Теперь можете запустить: start_web.bat
) else (
    echo ⚠️ Установка завершена с предупреждениями
    echo 🔍 Проверьте логи выше для диагностики проблем
)

echo.
echo 💡 СОВЕТЫ ПО РЕШЕНИЮ ПРОБЛЕМ:
echo.
echo 🔧 Если numpy не устанавливается:
echo    pip install --only-binary=numpy numpy
echo.
echo 🔧 Если pandas не устанавливается:
echo    pip install --only-binary=pandas pandas
echo.
echo 🔧 Если все еще проблемы с компиляцией:
echo    1. Установите Microsoft C++ Build Tools
echo    2. Или используйте Anaconda/Miniconda
echo    3. Или используйте Docker
echo.
echo 👋 Нажмите любую клавишу для выхода...
pause >nul 