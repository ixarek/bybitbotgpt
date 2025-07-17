@echo off
chcp 65001 >nul
title Bybit Trading Bot - Launcher v3.0

echo.
echo ╔══════════════════════════════════════════════════════╗
echo ║             BYBIT TRADING BOT v3.0                  ║
echo ║        🚀 ЗАПУСК ТОРГОВОГО БОТА                      ║
echo ║                                                      ║
echo ║  ✅ Все проблемы исправлены                          ║
echo ║  🎯 Режимы торговли работают корректно               ║
echo ║  📊 Индикаторы адаптируются к таймфреймам            ║
echo ║  🌐 Веб-интерфейс: http://localhost:5000             ║
echo ║                                                      ║
echo ║  🆕 PHASE 1 УЛУЧШЕНИЯ АКТИВНЫ:                      ║
echo ║  🧠 Умная фильтрация сигналов                       ║
echo ║  📈 Анализ рыночных условий                         ║
echo ║  🎯 Адаптивные веса индикаторов                     ║
echo ║  🛡️ Трейлинг-стопы                                  ║
echo ╚══════════════════════════════════════════════════════╝
echo.

:: Проверяем Python
echo 🔍 Проверка Python...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ ОШИБКА: Python не найден!
    echo 📥 Установите Python 3.8+ с https://python.org
    pause
    exit /b 1
)

:: Активируем виртуальное окружение если есть
if exist "venv\Scripts\activate.bat" (
    echo 📦 Активация виртуального окружения...
    call venv\Scripts\activate.bat
) else (
    echo ⚠️  Используется системный Python
)

:: Проверяем config.env
if not exist "config.env" (
    echo ❌ ОШИБКА: Файл config.env не найден!
    echo 📝 Создайте его из config.example
    echo 🔑 Укажите ваши API ключи Bybit
    pause
    exit /b 1
)

:: Создаем папку для логов
if not exist "logs" mkdir logs

:: Проверяем зависимости
echo 📦 Проверка зависимостей...
python -c "import fastapi, uvicorn, pandas" >nul 2>&1
if %errorlevel% neq 0 (
    echo 📦 Установка зависимостей...
    pip install fastapi uvicorn pandas websockets python-dotenv
)

:: Освобождаем порт 5000 если занят
echo 🔄 Проверка порта 5000...
netstat -an | findstr :5000 >nul 2>&1
if %errorlevel% equ 0 (
    echo 🔄 Освобождение порта 5000...
    taskkill /f /im python.exe >nul 2>&1
    timeout /t 2 /nobreak >nul
)

:: Устанавливаем PYTHONPATH для правильной работы импортов
set PYTHONPATH=%CD%

echo.
echo ✅ Все проверки пройдены!
echo 🚀 Запуск веб-сервера торгового бота...
echo.
echo ╔══════════════════════════════════════════════════════╗
echo ║                   ДОСТУП К БОТУ                      ║
echo ║                                                      ║
echo ║  🌐 Веб-интерфейс: http://localhost:5000             ║
echo ║  📚 API документация: http://localhost:5000/docs     ║
echo ║  🔧 ReDoc: http://localhost:5000/redoc               ║
echo ║                                                      ║
echo ║  🆕 PHASE 1 API ENDPOINTS:                          ║
echo ║  📊 /market-analysis/{symbol}                        ║
echo ║  🎯 /enhanced-signals/{symbol}                       ║
echo ║  🛡️ /trailing-stops                                  ║
echo ║                                                      ║
echo ║  🛑 Для остановки: Ctrl+C                           ║
echo ╚══════════════════════════════════════════════════════╝
echo.

:: Запуск веб-сервера
python -m backend.main

echo.
if %errorlevel% neq 0 (
    echo ❌ Веб-сервер завершился с ошибкой (код: %errorlevel%)
    echo 📋 Проверьте логи в папке logs/
    echo 🔍 Проверьте config.env файл
) else (
    echo ✅ Веб-сервер остановлен корректно
)

echo.
echo 👋 Нажмите любую клавишу для выхода...
pause >nul 