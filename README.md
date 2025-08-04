# 🚀 Bybit Trading Bot v3.0

**Профессиональный торговый бот для Bybit с современным веб-интерфейсом**

Полностью переработанная система с 3 торговыми режимами, 7 торговыми парами и новыми техническими индикаторами.

## ⚡ Быстрый запуск

### 1. Настройка API ключей
```bash
copy config.example config.env
# Отредактируйте config.env - укажите ваши API ключи Bybit
```

### 2. Запуск веб-сервера
```bash
# Windows
start_web.bat

# Linux/macOS
python cli.py web
```

### 🐧 Установка на Ubuntu 22.04 LTS
```bash
sudo apt update && sudo apt install -y git python3 python3-venv python3-pip
git clone <repo_url> bybitbotgpt
cd bybitbotgpt
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp config.example config.env
# отредактируйте config.env и внесите свои ключи

# запуск веб-интерфейса
python cli.py web

# или запуск торговли в консоли без веба
python cli.py console

```

### ⏲️ Запуск как сервис (systemd)
Чтобы бот продолжал работать после закрытия SSH-сессии, можно запустить его через `systemd`.

```bash
# скопируйте bybitbot.service и отредактируйте пути
sudo cp bybitbot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now bybitbot.service
```
После запуска сервиса торговля стартует автоматически, поэтому кнопку **Start** в веб-интерфейсе нажимать не нужно.

### 3. Откройте браузер
- 🌐 **Веб-интерфейс**: http://localhost:5000
- 📚 **API документация**: http://localhost:5000/docs
- 🔧 **ReDoc**: http://localhost:5000/redoc

## 🎯 Новые торговые режимы

### 🔥 Агрессивный режим
- **Стратегия**: Скальпинг + Event-driven
- **Таймфреймы**: 1m-5m
- **Плечо**: 10-20x
- **TP/SL**: 0.5-1% / 0.3-0.7%
- **Пары**: BTC, ETH, SOL, DOGE, XRP
- **Индикаторы**: RSI, EMA, MACD, Volume, ATR

### ⚖️ Средний режим
- **Стратегия**: Moving Average Crossover + Trend Following
- **Таймфреймы**: 5m-1h
- **Плечо**: 3-5x  
- **TP/SL**: 2-4% / 1-2%
- **Пары**: BTC, ETH, BNB, SOL, ADA
- **Индикаторы**: EMA, Bollinger Bands, Stochastic, MACD, Volume

### 🛡️ Консервативный режим
- **Стратегия**: DCA + Long-term Trend
- **Таймфреймы**: 4h-1d
- **Плечо**: 1x
- **TP/SL**: 5-10% / 3-5%  
- **Пары**: BTC, ETH, SOL
- **Индикаторы**: SMA, Support/Resistance, Volume, RSI

## ✨ Возможности

### 🌐 Веб-интерфейс
- ✅ Управление торговыми режимами
- ✅ Мониторинг позиций в реальном времени
- ✅ Графики и аналитика
- ✅ Логи и уведомления
- ✅ Адаптивный дизайн

### 🔧 API
- ✅ RESTful API с полной документацией
- ✅ WebSocket для real-time данных
- ✅ 6 новых endpoints для управления режимами

### 🛡️ Безопасность
- ✅ Поддержка Bybit Testnet
- ✅ Управление рисками
- ✅ Автоматические TP/SL
- ✅ Подробное логирование

## 🏗️ Архитектура

```
bybitbotweb/
├── backend/
│   ├── core/
│   │   ├── trading_engine.py      # Торговый движок
│   │   ├── signal_processor.py    # Обработка сигналов
│   │   ├── risk_manager.py        # Управление рисками
│   │   ├── trading_mode.py        # Торговые режимы
│   │   └── strategy_manager.py    # Менеджер стратегий
│   ├── integrations/
│   │   └── bybit_client.py        # Клиент Bybit API
│   ├── api/
│   │   ├── rest_api.py            # REST endpoints
│   │   └── websockets.py          # WebSocket менеджер
│   ├── utils/
│   │   ├── config.py              # Конфигурация
│   │   ├── logger.py              # Система логирования
│   │   └── error_handler.py       # Обработка ошибок
│   ├── static/
│   │   └── index.html             # Веб-интерфейс
│   └── main.py                    # FastAPI приложение
├── memory-bank/                   # Система документации
├── logs/                          # Логи
├── config.env                     # Конфигурация
├── requirements.txt               # Зависимости Python
├── start_web.bat                  # Запуск веб-сервера
└── README.md                      # Документация
```

## 🔍 API Endpoints

### Основные endpoints
- `GET /` - Веб-интерфейс
- `GET /health` - Проверка состояния
- `GET /api/status` - Статус системы
- `POST /api/start` - Запуск торговли
- `POST /api/stop` - Остановка торговли

### Новые endpoints для режимов
- `GET /api/trading-modes` - Список доступных режимов
- `GET /api/trading-mode` - Текущий режим
- `POST /api/trading-mode` - Смена режима
- `GET /api/mode-parameters/{mode}` - Параметры режима
- `GET /api/available-pairs/{mode}` - Торговые пары для режима
- `GET /api/signals/{symbol}/mode/{mode}` - Сигналы для режима

### Торговые endpoints
- `GET /api/balance` - Баланс аккаунта
- `GET /api/positions` - Текущие позиции
- `GET /api/signals` - Все торговые сигналы
- `GET /api/chart-data/{symbol}` - Данные графиков

## 📊 Конфигурация

### config.env файл
```env
# Bybit API
BYBIT_API_KEY=your_api_key_here
BYBIT_API_SECRET=your_api_secret_here
BYBIT_TESTNET=true

# Торговые настройки
TRADING_PAIRS=BTCUSDT,ETHUSDT,SOLUSDT,BNBUSDT,DOGEUSDT,XRPUSDT
TRAILING_STOP_ENABLED=false
DEFAULT_TRADING_MODE=medium

# Веб-сервер
HOST=localhost
PORT=5000

# Логирование
LOG_LEVEL=INFO
```
Trailing stop functionality is **disabled by default**. Set `TRAILING_STOP_ENABLED=true` to enable it.


## 🚀 Развертывание

### Локальная разработка
```bash
# Создание и активация виртуального окружения
python -m venv venv
# Windows
venv\Scripts\activate
# Linux/macOS
source venv/bin/activate

# Установка зависимостей
pip install -r requirements.txt

# Запуск веб-интерфейса
python cli.py web
```

### Продакшн
```bash
# Создание и активация виртуального окружения
python -m venv venv
# Windows
venv\Scripts\activate
# Linux/macOS
source venv/bin/activate

# Установка зависимостей
pip install -r requirements.txt

# Настройка config.env
cp config.example config.env
# Отредактируйте config.env

# Запуск сервера
python cli.py web
```

## 📋 Логирование

Система создает логи в папке `logs/`:
- `trading_bot.log` - Основные логи приложения
- `trading.log` - Торговые операции
- `errors.log` - Ошибки и исключения

## 🔧 Техническая поддержка

### Устранение неполадок
1. Проверьте config.env файл
2. Убедитесь, что API ключи корректны
3. Проверьте логи в папке logs/
4. Используйте testnet для тестирования

### Системные требования
- Python 3.8+
- Windows 10/11 или Linux (Ubuntu 22.04+)
- 2GB RAM
- Интернет соединение

## 📈 Что нового в v3.0

- ✅ 3 новых торговых режима с уникальными стратегиями
- ✅ 7 торговых пар (добавлены ADA, DOGE, XRP)
- ✅ Новая система управления стратегиями
- ✅ Улучшенный веб-интерфейс
- ✅ 6 новых API endpoints
- ✅ Оптимизированная архитектура
- ✅ Удален неиспользуемый код
- ✅ Улучшенная документация
- ✅ Pair Reversal Watcher распознает уровни поддержки/сопротивления,
  свечные модели и подтверждает сигналы на старшем таймфрейме

---

**⚠️ Дисклеймер**: Торговля криптовалютами связана с высокими рисками. Всегда используйте testnet для тестирования и торгуйте только теми средствами, которые можете позволить себе потерять. 