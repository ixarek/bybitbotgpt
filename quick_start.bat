@echo off
title Bybit Trading Bot - Quick Start

echo 🚀 Быстрый запуск Bybit Trading Bot...

:: Активируем виртуальное окружение если есть
if exist "venv\Scripts\activate.bat" call venv\Scripts\activate.bat

:: Устанавливаем PYTHONPATH
set PYTHONPATH=%CD%

:: Запускаем бот
echo 🌐 Запуск на http://localhost:5000
python backend/main.py

pause 