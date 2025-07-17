@echo off
echo 🚀 Запуск Bybit Trading Bot Web Interface...

REM Активируем виртуальное окружение если существует
if exist "venv\Scripts\activate.bat" (
    echo 📦 Активация виртуального окружения...
    call venv\Scripts\activate.bat
)

REM Устанавливаем PYTHONPATH для правильной работы импортов
set PYTHONPATH=%CD%

REM Запускаем веб-сервер
echo 🌐 Запуск веб-сервера на http://localhost:5000
python backend/main.py

pause 