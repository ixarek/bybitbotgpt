        // Глобальные переменные
        let ws = null;
        let chart = null;
        let isTrading = false;
        let connectionRetries = 0;
        const maxRetries = 5;
        let currentSymbol = 'BTCUSDT';
        let allSignalsData = {};
        let signalCache = {};

        // WebSocket подключение
        function connectWebSocket() {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const wsUrl = `${protocol}//${window.location.host}/ws`;
            
            ws = new WebSocket(wsUrl);
            
            ws.onopen = function() {
                console.log('WebSocket подключен');
                updateConnectionStatus(true);
                connectionRetries = 0;
            };
            
            ws.onmessage = function(event) {
                const data = JSON.parse(event.data);
                handleWebSocketMessage(data);
            };
            
            ws.onclose = function() {
                console.log('WebSocket отключен');
                updateConnectionStatus(false);
                
                // Переподключение
                if (connectionRetries < maxRetries) {
                    connectionRetries++;
                    setTimeout(connectWebSocket, 2000 * connectionRetries);
                }
            };
            
            ws.onerror = function(error) {
                console.error('WebSocket ошибка:', error);
                updateConnectionStatus(false);
            };
        }

        // Обработка WebSocket сообщений
        function handleWebSocketMessage(data) {
            console.log('WebSocket message:', data);
            
            switch(data.type) {
                case 'status':
                    updateSystemStatus(data.data);
                    break;
                case 'balance':
                    updateBalance(data.data);
                    break;
                case 'positions':
                    updatePositions(data.data);
                    break;
                case 'signals':
                    // Реактивное обновление сигналов при смене режима
                    if (data.data.signals) {
                        updateAllSignals(data.data.signals, data.data.timeframe, data.data.mode);
                        addLogEntry('info', `🔄 Indicators updated via WebSocket (${data.data.mode}, ${data.data.timeframe})`);
                    } else {
                        updateSignals(data.data);
                    }
                    break;
                case 'log':
                    // Обработка логов от сервера
                    if (data.data.type && data.data.message) {
                        addLogEntry(data.data.type, data.data.message);
                    } else {
                        addLogEntry('info', data.data);
                    }
                    break;
                case 'price':
                    updateChart(data.data);
                    break;
                case 'mode_changed':
                    // Специальная обработка смены режима
                    handleModeChange(data.data);
                    break;
            }
        }
        
        // Обработка смены режима через WebSocket
        function handleModeChange(modeData) {
            if (modeData.mode && modeData.timeframe) {
                // Обновляем селектор режима
                const modeSelect = document.getElementById('tradingMode');
                modeSelect.value = modeData.mode;
                
                // Обновляем статус
                updateSystemStatus({
                    mode: modeData.mode,
                    timeframe: modeData.timeframe
                });
                
                // Обновляем индикаторы, если они есть
                if (modeData.signals) {
                    updateAllSignals(modeData.signals, modeData.timeframe, modeData.mode);
                }
                
                addLogEntry('success', `🔄 Режим автоматически обновлен на: ${modeData.mode} (${modeData.timeframe})`);
            }
        }

        // Обновление статуса подключения
        function updateConnectionStatus(connected) {
            const statusEl = document.getElementById('connectionStatus');
            const textEl = document.getElementById('connectionText');
            
            if (connected) {
                statusEl.className = 'status-indicator status-online pulse';
                textEl.textContent = 'Подключено';
            } else {
                statusEl.className = 'status-indicator status-offline';
                textEl.textContent = 'Нет подключения';
            }
        }

        // Обновление статуса системы
        function updateSystemStatus(status) {
            const engineStatus = document.getElementById('engineStatus');
            const engineText = document.getElementById('engineText');
            const apiStatus = document.getElementById('apiStatus');
            const apiText = document.getElementById('apiText');
            
            // Trading Engine status
            if (status.trading_engine === 'active') {
                engineStatus.className = 'status-indicator status-online';
                engineText.textContent = 'Активен';
            } else {
                engineStatus.className = 'status-indicator status-offline';
                engineText.textContent = 'Неактивен';
            }
            
            // API status
            if (status.bybit_api === 'connected') {
                apiStatus.className = 'status-indicator status-online';
                apiText.textContent = 'Подключен';
            } else {
                apiStatus.className = 'status-indicator status-offline';
                apiText.textContent = 'Отключен';
            }
            
            // Обновляем режим торговли в селекторе, если он изменился
            if (status.mode) {
                const modeSelect = document.getElementById('tradingMode');
                if (modeSelect.value !== status.mode) {
                    modeSelect.value = status.mode;
                }
            }
        }
        
        // Универсальная функция обновления статуса
        function updateStatus(statusData) {
            if (statusData.mode) {
                const modeSelect = document.getElementById('tradingMode');
                modeSelect.value = statusData.mode;
            }
            
            // Можно добавить обновление других элементов статуса
            if (statusData.timeframe) {
                // Обновляем отображение таймфрейма где-то в интерфейсе
                console.log(`Timeframe updated to: ${statusData.timeframe}`);
            }
        }

        // Управление ботом
        async function startBot() {
            try {
                addLogEntry('info', '⏳ Запуск торговли...');
                console.log('Starting bot...');
                
                const response = await fetch('/api/start', { 
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    }
                });
                
                console.log('Response status:', response.status);
                const result = await response.json();
                console.log('Response:', result);
                
                if (result.success) {
                    isTrading = true;
                    document.getElementById('startBtn').disabled = true;
                    document.getElementById('stopBtn').disabled = false;
                    addLogEntry('success', '🚀 Торговля запущена');
                } else {
                    addLogEntry('error', `❌ Ошибка: ${result.message}`);
                }
            } catch (error) {
                console.error('Ошибка запуска:', error);
                addLogEntry('error', `❌ Ошибка запуска торговли: ${error.message}`);
            }
        }

        async function stopBot() {
            try {
                addLogEntry('info', '⏳ Остановка торговли...');
                console.log('Stopping bot...');
                
                const response = await fetch('/api/stop', { 
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    }
                });
                
                console.log('Response status:', response.status);
                const result = await response.json();
                console.log('Response:', result);
                
                if (result.success) {
                    isTrading = false;
                    document.getElementById('startBtn').disabled = false;
                    document.getElementById('stopBtn').disabled = true;
                    addLogEntry('warning', '⏸️ Торговля остановлена');
                } else {
                    addLogEntry('error', `❌ Ошибка: ${result.message}`);
                }
            } catch (error) {
                console.error('Ошибка остановки:', error);
                addLogEntry('error', `❌ Ошибка остановки торговли: ${error.message}`);
            }
        }

        // Смена режима торговли с обновлением всех параметров
        async function changeTradingMode() {
            const mode = document.getElementById('tradingMode').value;
            const modeSelect = document.getElementById('tradingMode');
            const modeDescription = document.getElementById('modeDescription');
            
            // Показываем индикатор загрузки
            modeSelect.disabled = true;
            addLogEntry('info', `🔄 Переключение торгового режима на: ${mode}...`);
            
            // Обновляем описание режима
            const descriptions = {
                'conservative': 'Консервативный режим: Торговля на 15-минутных свечах с 6 индикаторами'
            };
            modeDescription.textContent = descriptions[mode] || '';
            
            try {
                const response = await fetch('/api/mode', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ mode: mode })
                });
                
                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                }
                
                const result = await response.json();
                
                if (result.status === 'success' && result.data) {
                    const modeData = result.data;
                    addLogEntry('success', `✅ Режим изменен: ${modeData.old_mode} → ${modeData.new_mode}`);
                    
                    // Обновляем торговые пары для нового режима
                    await updateTradingPairsForMode(mode);
                    
                    // Загружаем параметры режима
                    await loadModeParameters(mode);
                    
                    // Обновляем сигналы для текущей пары в новом режиме
                    await loadCurrentSymbolSignals();
                    
                    addLogEntry('info', `📊 Интерфейс обновлен для режима ${mode}`);
                } else {
                    addLogEntry('warning', result.message || 'Режим обновлен, но StrategyManager недоступен');
                }
                
            } catch (error) {
                console.error('Ошибка смены режима:', error);
                addLogEntry('error', `❌ Ошибка смены режима: ${error.message}`);
            } finally {
                // Возвращаем доступность селектора
                modeSelect.disabled = false;
            }
        }
        
        // Обновление торговых пар для режима
        async function updateTradingPairsForMode(mode) {
            try {
                const response = await fetch(`/api/available-pairs/${mode}`);
                if (response.ok) {
                    const result = await response.json();
                    if (result.status === 'success' && result.data.pairs) {
                        updateSymbolTabs(result.data.pairs);
                        addLogEntry('info', `📈 Обновлены торговые пары для режима ${mode}: ${result.data.pairs.join(', ')}`);
                    }
                }
            } catch (error) {
                console.error('Ошибка обновления торговых пар:', error);
            }
        }
        
        // Обновление кнопок валютных пар
        function updateSymbolTabs(pairs) {
            const symbolTabs = document.getElementById('symbolTabs');
            symbolTabs.innerHTML = pairs.map((pair, index) => {
                const symbol = pair.replace('/', '');
                const isActive = index === 0 ? 'active' : '';
                return `<button type="button" class="btn btn-outline-primary ${isActive}" data-symbol="${symbol}">${pair}</button>`;
            }).join('');
            
            // Обновляем текущий символ на первую пару
            if (pairs.length > 0) {
                currentSymbol = pairs[0].replace('/', '');
                updateCurrentSymbolDisplay();
            }
            
            // Переустанавливаем обработчики событий
            setupSymbolTabs();
        }
        
        // Загрузка параметров режима
        async function loadModeParameters(mode) {
            try {
                const response = await fetch(`/api/mode-parameters/${mode}`);
                if (response.ok) {
                    const result = await response.json();
                    if (result.status === 'success' && result.data) {
                        const params = result.data;
                        addLogEntry('info', `⚙️ Параметры режима ${params.name}:`);
                        addLogEntry('info', `   📊 Индикаторы: ${Object.keys(params.indicators).join(', ')}`);
                        addLogEntry('info', `   ⏱️ Таймфреймы: ${params.timeframes.join(', ')}`);
                        addLogEntry('info', `   📈 Плечо: ${params.leverage_range.min}x-${params.leverage_range.max}x`);
                        addLogEntry('info', `   🎯 TP: ${params.tp_range.min}%-${params.tp_range.max}%, SL: ${params.sl_range.min}%-${params.sl_range.max}%`);
                    }
                }
            } catch (error) {
                console.error('Ошибка загрузки параметров режима:', error);
            }
        }
        
        // Загрузка сигналов для текущего режима
        async function loadCurrentSymbolSignals() {
            if (!currentSymbol) return;
            
            try {
                // Получаем текущий режим
                const mode = document.getElementById('tradingMode').value;
                
                // Получаем все сигналы через работающий эндпоинт
                const response = await fetch('/api/signals');
                if (response.ok) {
                    const result = await response.json();
                    if (result.signals && result.signals[currentSymbol]) {
                        updateSignals(result.signals[currentSymbol]);
                        addLogEntry('info', `🔄 Indicators updated for ${currentSymbol} in ${mode} mode`);
                    }
                } else {
                    addLogEntry('error', `❌ Failed to fetch signals for ${currentSymbol}`);
                }
            } catch (error) {
                console.error('Ошибка загрузки сигналов:', error);
                addLogEntry('error', `❌ Ошибка загрузки сигналов: ${error.message}`);
            }
        }
        
        // Обновление сигналов из данных режима
        function updateSignalsFromModeData(modeData) {
            if (modeData.signals) {
                const signalsArray = Object.keys(modeData.signals).map(indicator => ({
                    name: indicator,
                    signal: modeData.signals[indicator],
                    value: 'N/A'
                }));
                
                updateSignals({
                    signals: signalsArray,
                    active_count: signalsArray.filter(s => s.signal !== 'HOLD').length,
                    total_count: signalsArray.length
                });
                
                addLogEntry('info', `📊 Загружены сигналы для ${modeData.symbol} в режиме ${modeData.mode_name}`);
                addLogEntry('info', `   ⏱️ Таймфрейм: ${modeData.timeframe} (API: ${modeData.api_timeframe || 'N/A'})`);
                addLogEntry('info', `   🎯 Рекомендуемое плечо: ${modeData.recommended_leverage}x`);
                addLogEntry('info', `   📈 TP: ${modeData.recommended_tp_sl.take_profit}%, SL: ${modeData.recommended_tp_sl.stop_loss}%`);
            }
        }
        
        // Обновление всех сигналов для всех пар
        async function refreshAllSignals() {
            try {
                const response = await fetch('/api/signals');
                if (response.ok) {
                    const data = await response.json();
                    if (data.signals) {
                        updateAllSignals(data.signals, data.timeframe, data.mode);
                    }
                }
            } catch (error) {
                console.error('Ошибка обновления сигналов:', error);
            }
        }
        
        // Обновление всех сигналов для всех валютных пар
        function updateAllSignals(allSignals, timeframe, mode) {
            if (!allSignals) return;

            signalCache = allSignals;
            
            // Получаем текущую выбранную пару
            const currentPair = getCurrentSelectedPair();
            let totalActive = 0;
            let totalIndicators = 0;
            if (currentPair && allSignals[currentPair]) {
                const signals = allSignals[currentPair];
                Object.values(signals).forEach(signal => {
                    totalIndicators++;
                    if (signal !== 'HOLD') {
                        totalActive++;
                    }
                });
            }
            // Обновляем счетчики в интерфейсе только для выбранной пары
            document.getElementById('activeSignals').textContent = `${totalActive}/${totalIndicators}`;
            // Обновляем индикаторы для текущей выбранной пары
            if (currentPair && allSignals[currentPair]) {
                updateSignalsForPair(currentPair, allSignals[currentPair], timeframe);
            }
            // Обновляем силу сигнала
            updateSignalStrength(totalActive);
            addLogEntry('info', `📈 Updated ${totalIndicators} indicators for ${currentPair} (${totalActive} active)`);
        }
        
        // Получение текущей выбранной валютной пары
        function getCurrentSelectedPair() {
            const pairButtons = document.querySelectorAll('.pair-btn');
            for (let btn of pairButtons) {
                if (btn.classList.contains('active')) {
                    return btn.textContent.trim();
                }
            }
            return 'BTC/USDT'; // По умолчанию
        }
        
        // Обновление сигналов для конкретной пары
        function updateSignalsForPair(symbol, signals, timeframe) {
            const indicatorsArray = Object.keys(signals).map(indicator => ({
                name: indicator,
                signal: signals[indicator],
                value: 'N/A' // Значение будет получено отдельно
            }));
            
            updateSignals({
                signals: indicatorsArray,
                active_count: indicatorsArray.filter(s => s.signal !== 'HOLD').length,
                total_count: indicatorsArray.length,
                timeframe: timeframe
            });
        }

        // Обновление баланса
        function updateBalance(balance) {
            // ✅ ИСПРАВЛЕНИЕ: Безопасная проверка значений перед toFixed()
            const total = (balance && typeof balance.total === 'number') ? balance.total : 0;
            const dailyPnl = (balance && typeof balance.daily_pnl === 'number') ? balance.daily_pnl : 0;
            const totalPnl = (balance && typeof balance.total_pnl === 'number') ? balance.total_pnl : 0;
            
            document.getElementById('totalBalance').textContent = `$${total.toFixed(2)}`;
            
            const dailyPnlElement = document.getElementById('dailyPnl');
            const totalPnlElement = document.getElementById('totalPnl');
            
            // Обновляем дневной P&L
            dailyPnlElement.textContent = `$${dailyPnl.toFixed(2)}`;
            dailyPnlElement.className = dailyPnl >= 0 ? 'text-success' : 'text-danger';
            
            // Обновляем общий P&L
            totalPnlElement.textContent = `$${totalPnl.toFixed(2)}`;
            totalPnlElement.className = totalPnl >= 0 ? 'text-success' : 'text-danger';
        }

        // Обновление позиций
        function updatePositions(positions) {
            const tbody = document.getElementById('positionsTable');
            
            // ✅ ИСПРАВЛЕНИЕ: Проверяем что positions является массивом
            if (!positions || !Array.isArray(positions) || positions.length === 0) {
                tbody.innerHTML = '<tr><td colspan="3" class="text-center text-muted">Нет активных позиций</td></tr>';
                return;
            }
            
            tbody.innerHTML = positions.map(pos => {
                // ✅ ИСПРАВЛЕНИЕ: Безопасная проверка значений
                const pnl = (pos && typeof pos.pnl === 'number') ? pos.pnl : 0;
                const symbol = pos?.symbol || 'N/A';
                const size = pos?.size || 'N/A';
                
                return `
                    <tr>
                        <td>${symbol}</td>
                        <td>${size}</td>
                        <td class="${pnl >= 0 ? 'text-success' : 'text-danger'}">
                            $${pnl.toFixed(2)}
                        </td>
                    </tr>
                `;
            }).join('');
        }

        // Обновление торговых сигналов
        function updateSignals(signalsData) {
            if (!signalsData || !signalsData.signals) return;
            
            // Обновляем счетчики
            document.getElementById('activeSignals').textContent = 
                `${signalsData.active_count}/${signalsData.total_count}`;
            
            // Обновляем индикаторы сигналов
            const grid = document.getElementById('indicatorsGrid');
            grid.innerHTML = signalsData.signals.map(signal => {
                const signalClass = signal.signal === 'BUY' ? 'indicator-buy' : 
                                   signal.signal === 'SELL' ? 'indicator-sell' : 'indicator-hold';
                const icon = signal.signal === 'BUY' ? '↗️' : 
                            signal.signal === 'SELL' ? '↘️' : '➡️';
                
                return `
                    <div class="indicator-item ${signalClass}">
                        <div class="indicator-name">${signal.name}</div>
                        <div class="indicator-value">${signal.value}</div>
                        <div class="indicator-signal">${icon} ${signal.signal}</div>
                    </div>
                `;
            }).join('');
            
            // Обновляем силу сигнала
            updateSignalStrength(signalsData.active_count);
        }

        // Обновление силы сигнала
        function updateSignalStrength(activeCount) {
            const signalBars = ['signal1', 'signal2', 'signal3', 'signal4', 'signal5'];
            const strength = Math.min(Math.floor(activeCount / 2) + 1, 5);
            
            signalBars.forEach((id, index) => {
                const bar = document.getElementById(id);
                if (index < strength) {
                    bar.classList.add('active');
                    bar.classList.remove('inactive');
                } else {
                    bar.classList.add('inactive');
                    bar.classList.remove('active');
                }
            });
        }

        // Добавление лога
        function addLogEntry(type, message) {
            const container = document.getElementById('logContainer');
            const time = new Date().toLocaleTimeString();
            
            const logClass = type === 'success' ? 'log-success' : 
                            type === 'error' ? 'log-error' : 
                            type === 'warning' ? 'log-warning' : 'log-info';
            
            const logEntry = document.createElement('div');
            logEntry.className = `log-entry ${logClass}`;
            logEntry.innerHTML = `
                <span class="text-muted">[${time}]</span> 
                ${message}
            `;
            
            container.insertBefore(logEntry, container.firstChild);
            
            // Ограничиваем количество логов
            while (container.children.length > 50) {
                container.removeChild(container.lastChild);
            }
            
            // Автопрокрутка вниз
            container.scrollTop = 0;
        }

        // Переключение темы
        function toggleTheme() {
            document.body.classList.toggle('dark-theme');
            const icon = document.getElementById('themeIcon');
            icon.className = document.body.classList.contains('dark-theme') 
                ? 'fas fa-sun' : 'fas fa-moon';
        }

        // Инициализация графика
        function initChart() {
            const ctx = document.getElementById('priceChart').getContext('2d');
            chart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: [],
                    datasets: [{
                        label: 'BTC/USDT',
                        data: [],
                        borderColor: '#007bff',
                        backgroundColor: 'rgba(0, 123, 255, 0.1)',
                        borderWidth: 2,
                        fill: true,
                        tension: 0.4
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            display: true,
                            position: 'top'
                        }
                    },
                    scales: {
                        x: {
                            display: true,
                            title: {
                                display: true,
                                text: 'Время'
                            }
                        },
                        y: {
                            display: true,
                            title: {
                                display: true,
                                text: 'Цена ($)'
                            }
                        }
                    },
                    elements: {
                        point: {
                            radius: 1
                        }
                    }
                }
            });
        }

        // Обновление графика
        function updateChart(data) {
            if (!chart) {
                initChart(); 
            }
            
            if (data && data.price) {
                const time = new Date().toLocaleTimeString();
                
                // Добавляем новую точку данных
                chart.data.labels.push(time);
                chart.data.datasets[0].data.push(data.price);
                
                // Ограничиваем количество точек
                if (chart.data.labels.length > 50) {
                    chart.data.labels.shift();
                    chart.data.datasets[0].data.shift();
                }
                
                chart.update('none'); // Обновляем без анимации для производительности
            }
        }

        // Загрузка начальных данных
        async function loadInitialData() {
            try {
                // ✅ ИСПРАВЛЕНИЕ: Безопасная загрузка статуса
                try {
                    const statusResponse = await fetch('/api/status');
                    if (statusResponse.ok) {
                        const status = await statusResponse.json();
                        updateSystemStatus(status);
                    }
                } catch (statusError) {
                    console.log('Status API not available:', statusError);
                    addLogEntry('warning', '⚠️ Статус API недоступен');
                }
                
                // ✅ ИСПРАВЛЕНИЕ: Безопасная загрузка баланса
                try {
                    const balanceResponse = await fetch('/api/balance');
                    if (balanceResponse.ok) {
                        const balance = await balanceResponse.json();
                        updateBalance(balance);
                    }
                } catch (balanceError) {
                    console.log('Balance API not available:', balanceError);
                    addLogEntry('warning', '⚠️ Баланс API недоступен');
                    // Устанавливаем значения по умолчанию
                    updateBalance({ total: 0, daily_pnl: 0, total_pnl: 0 });
                }
                
                // ✅ ИСПРАВЛЕНИЕ: Безопасная загрузка позиций
                try {
                    const positionsResponse = await fetch('/api/positions');
                    if (positionsResponse.ok) {
                        const positions = await positionsResponse.json();
                        console.log('Positions API response:', positions, 'Type:', typeof positions, 'IsArray:', Array.isArray(positions));
                        updatePositions(positions);
                    }
                } catch (positionsError) {
                    console.log('Positions API not available:', positionsError);
                    addLogEntry('warning', '⚠️ Позиции API недоступен');
                    updatePositions([]);
                }
                
                // ✅ ИСПРАВЛЕНИЕ: Безопасная загрузка сигналов
                try {
                                    const signalsResponse = await fetch('/api/signals');
                if (signalsResponse.ok) {
                        const result = await signalsResponse.json();
                        let signalsData = null;
                        if (result.status === 'success' && result.data) {
                            signalsData = result.data;
                        } else {
                            signalsData = result;
                        }
                        if (signalsData && signalsData.signals) {
                            updateSignalsForSymbol(signalsData);
                        }
                    }
                } catch (signalsError) {
                    console.log('Signals API not available:', signalsError);
                    addLogEntry('warning', '⚠️ Сигналы API недоступен');
                }
                
                // ✅ ИСПРАВЛЕНИЕ: Безопасная загрузка графика
                try {
                    const chartResponse = await fetch(`/api/chart-data/${currentSymbol}`);
                    if (chartResponse.ok) {
                        const chartData = await chartResponse.json();
                        if (chartData && chartData.data && chartData.data.length > 0) {
                            updateChartForSymbol(chartData);
                        }
                    }
                } catch (chartError) {
                    console.log('Chart API not available:', chartError);
                    addLogEntry('warning', '⚠️ График API недоступен');
                }
                
                addLogEntry('success', '✅ Данные загружены');
                
            } catch (error) {
                console.error('Ошибка загрузки данных:', error);
                addLogEntry('error', `❌ Ошибка загрузки: ${error.message}`);
            }
        }

        // Тест соединения с API
        async function testConnection() {
            try {
                addLogEntry('info', '🔍 Тестирование соединения...');
                console.log('Testing connection...');
                
                const response = await fetch('/api/status');
                console.log('Status response:', response.status);
                
                if (response.ok) {
                    const status = await response.json();
                    console.log('Status data:', status);
                    addLogEntry('success', '✅ Соединение с API работает');
                    addLogEntry('info', `📊 Статус: ${JSON.stringify(status)}`);
                } else {
                    addLogEntry('error', `❌ HTTP Error: ${response.status}`);
                }
            } catch (error) {
                console.error('Connection test failed:', error);
                addLogEntry('error', `❌ Ошибка соединения: ${error.message}`);
            }
        }

        // Инициализация при загрузке страницы
        document.addEventListener('DOMContentLoaded', function() {
            console.log('🚀 Инициализация веб-интерфейса...');
            
            // Подключаем WebSocket
            connectWebSocket();
            
            // Инициализируем график
            initChart();
            
            // Настраиваем переключение валютных пар
            setupSymbolTabs();
            
            // Загружаем начальные данные
            loadInitialData();
            
            // Добавляем начальные логи
            addLogEntry('success', '🌐 Веб-интерфейс загружен');
            addLogEntry('info', '🔗 Подключение к серверу...');
        });

        // Настройка переключения валютных пар
        function setupSymbolTabs() {
            const tabs = document.querySelectorAll('#symbolTabs button');
            tabs.forEach(tab => {
                tab.addEventListener('click', function() {
                    // Убираем активный класс со всех кнопок
                    tabs.forEach(t => t.classList.remove('active'));
                    
                    // Добавляем активный класс к текущей кнопке
                    this.classList.add('active');
                    
                    // Обновляем текущий символ
                    currentSymbol = this.getAttribute('data-symbol');
                    
                    // Обновляем отображение
                    updateCurrentSymbolDisplay();
                    
                    // Загружаем данные для новой пары
                    loadDataForSymbol(currentSymbol);
                });
            });
        }

        // Обновление отображения текущего символа
        function updateCurrentSymbolDisplay() {
            const displayName = currentSymbol.replace('USDT', '/USDT');
            document.getElementById('currentSymbol').textContent = displayName;
            document.getElementById('chartSymbol').textContent = displayName;
        }

        // Загрузка данных для конкретной валютной пары
        async function loadDataForSymbol(symbol) {
            try {
                if (signalCache[symbol]) {
                    updateSignalsForSymbol({ signals: signalCache });
                } else {
                    const signalsResponse = await fetch('/api/signals');
                    if (signalsResponse.ok) {
                        const result = await signalsResponse.json();
                        if (result && result.signals) {
                            signalCache = result.signals;
                            updateSignalsForSymbol(result);
                            addLogEntry('info', `📊 Загружены сигналы для ${symbol}`);
                        } else {
                            addLogEntry('warning', `⚠️ Нет данных сигналов для ${symbol}`);
                        }
                    } else {
                        addLogEntry('error', `❌ Ошибка API: ${signalsResponse.status}`);
                    }
                }
                
                // Загружаем данные графика для символа
                const chartResponse = await fetch(`/api/chart-data/${symbol}`);
                if (chartResponse.ok) {
                    const chartData = await chartResponse.json();
                    updateChartForSymbol(chartData);
                }
            } catch (error) {
                console.error(`Ошибка загрузки данных для ${symbol}:`, error);
                addLogEntry('error', `❌ Ошибка загрузки данных для ${symbol}: ${error.message}`);
            }
        }

        // Обновление сигналов для конкретного символа
        function updateSignalsForSymbol(signalsData) {
            console.log('updateSignalsForSymbol called with:', signalsData);
            console.log('currentSymbol:', currentSymbol);
            
            // ✅ ИСПРАВЛЕНИЕ: Обработка данных от API
            if (!signalsData || !signalsData.signals) {
                console.log('No signals data available');
                document.getElementById('activeSignals').textContent = '0/0';
                document.getElementById('indicatorsGrid').innerHTML = 
                    '<div class="text-center text-muted">Нет данных сигналов</div>';
                updateSignalStrength(0);
                return;
            }
            
            // Получаем сигналы для текущего символа
            const symbolSignals = signalsData.signals[currentSymbol];
            console.log('Symbol signals for', currentSymbol, ':', symbolSignals);
            
            if (!symbolSignals) {
                console.log('No signals for current symbol');
                document.getElementById('activeSignals').textContent = '0/0';
                document.getElementById('indicatorsGrid').innerHTML = 
                    '<div class="text-center text-muted">Нет данных для выбранного символа</div>';
                updateSignalStrength(0);
                return;
            }
            
            // ✅ ИСПРАВЛЕНИЕ: Обработка новой структуры данных API
            let signalsArray = [];
            
            // Проверяем структуру данных
            if (symbolSignals.enhanced_signals) {
                // Используем enhanced_signals
                signalsArray = Object.entries(symbolSignals.enhanced_signals).map(([name, signal]) => ({
                    name: name,
                    signal: signal,
                    value: signal // Для enhanced_signals значение = сигнал
                }));
            } else if (symbolSignals.base_signals) {
                // Используем base_signals
                signalsArray = Object.entries(symbolSignals.base_signals).map(([name, signal]) => ({
                    name: name,
                    signal: signal,
                    value: signal // Для base_signals значение = сигнал
                }));
            } else {
                // ✅ НОВАЯ СТРУКТУРА: Детальные сигналы с value и signal
                signalsArray = Object.entries(symbolSignals).map(([name, data]) => {
                    if (data && typeof data === 'object' && data.value && data.signal) {
                        // Новая структура: {value: "36.38", signal: "HOLD"}
                        return {
                            name: name,
                            signal: data.signal,
                            value: data.value
                        };
                    } else {
                        // Старая структура: "BUY" или {signal: "BUY"}
                        return {
                            name: name,
                            signal: data.signal || data,
                            value: data.value || data
                        };
                    }
                });
            }
            
            const totalCount = signalsArray.length;
            const activeCount = signalsArray.filter(s => s.signal === 'BUY' || s.signal === 'SELL').length;
            
            console.log('Signals array:', signalsArray);
            console.log('Total count:', totalCount);
            console.log('Active count:', activeCount);
            
            // Обновляем счетчики
            console.log('Updating counter to:', `${activeCount}/${totalCount}`);
            const counterElement = document.getElementById('activeSignals');
            if (counterElement) {
                counterElement.textContent = `${activeCount}/${totalCount}`;
                console.log('Counter updated successfully');
            } else {
                console.error('Counter element not found!');
            }
            
            // Обновляем индикаторы сигналов
            const grid = document.getElementById('indicatorsGrid');
            if (signalsArray.length > 0) {
                grid.innerHTML = signalsArray.map(signal => {
                    const signalValue = signal.signal || 'HOLD';
                    const signalName = signal.name || 'Unknown';
                    const signalPrice = signal.value || 'N/A';
                    
                    // Если это числовое значение, показываем его с единицей измерения
                    let displayValue = signalPrice;
                    if (typeof signal.value === 'string' && signal.value !== 'N/A' && signal.value !== signalValue) {
                        const num = parseFloat(signal.value);
                        displayValue = isNaN(num) ? signal.value : num.toFixed(4);
                    }
                    
                    const signalClass = signalValue === 'BUY' ? 'indicator-buy' : 
                                       signalValue === 'SELL' ? 'indicator-sell' : 'indicator-hold';
                    const icon = signalValue === 'BUY' ? '↗️' : 
                                signalValue === 'SELL' ? '↘️' : '➡️';
                    
                    return `
                        <div class="indicator-item ${signalClass}">
                            <div class="indicator-name">${signalName}</div>
                            <div class="indicator-value">${displayValue}</div>
                            <div class="indicator-signal">${icon} ${signalValue}</div>
                        </div>
                    `;
                }).join('');
            } else {
                grid.innerHTML = '<div class="text-center text-muted">Нет активных индикаторов</div>';
            }
            
            // Обновляем силу сигнала
            updateSignalStrength(activeCount);
        }

        // Обновление графика для конкретного символа
        function updateChartForSymbol(chartData) {
            if (!chart || !chartData.data || chartData.data.length === 0) return;
            
            // Очищаем текущие данные
            chart.data.labels = [];
            chart.data.datasets[0].data = [];
            
            // Добавляем новые данные
            chartData.data.forEach(point => {
                const time = new Date(point.timestamp * 1000).toLocaleTimeString();
                chart.data.labels.push(time);
                chart.data.datasets[0].data.push(point.price);
            });
            
            // Обновляем название графика
            chart.data.datasets[0].label = chartData.symbol.replace('USDT', '/USDT');
            
            chart.update();
        }

        // Обновление торговых сигналов (для всех пар)
        function updateSignals(allSignalsData) {
            // Сохраняем данные для всех пар
            this.allSignalsData = allSignalsData;
            
            // Отображаем данные для текущей выбранной пары
            if (allSignalsData[currentSymbol]) {
                updateSignalsForSymbol(allSignalsData[currentSymbol]);
            }
        }
