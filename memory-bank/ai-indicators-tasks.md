# AI-индикаторы для внедрения в трейдинг-бота

## Чеклист задач (task-list)

- [В работе] **SuperTrend AI (Clustering)**  
  AI-оптимизация ATR-множителя через кластеризацию (k-means) для динамического SuperTrend.  
  Источник: [LuxAlgo SuperTrend AI Clustering](https://www.luxalgo.com/library/indicator/supertrend-ai-clustering/)
  
  **Прогресс:**
  - [x] Модуль backend/core/supertrend_ai.py создан, реализован класс SuperTrendAI с динамическим подбором множителя через k-means.
  - [x] Интеграция в систему сигналов: SuperTrendAI теперь выдаёт сигнал и параметры в detailed/обычных сигналах (signal_processor.py).
  - [x] Интеграция в UI: SuperTrendAI отображается с tooltip множителя и цветовой индикацией.

- [ ] **AI Channels (Clustering)**  
  Кластеризация исторических цен для автоматического построения зон поддержки/сопротивления.  
  Источник: [LuxAlgo AI Channels](https://www.luxalgo.com/blog/ai-driven-trading-the-next-generation-of-market-indicators/)

- [ ] **AI SuperTrend Clustering Oscillator**  
  Осциллятор силы тренда на основе кластеризации отклонений от SuperTrend.  
  Источник: [LuxAlgo AI SuperTrend Clustering Oscillator](https://www.luxalgo.com/blog/ai-driven-trading-the-next-generation-of-market-indicators/)

- [ ] **AI Volume Breakout**  
  Индикатор резких всплесков объема с фильтрацией по тренду, волатильности и динамическим порогам.  
  Источник: [TradingView AI Volume Breakout](https://www.tradingview.com/script/Fk7JtbC9-AI-Volume-Breakout-for-scalping/)

- [ ] **Pro Scalper AI (BullByte)**  
  Композитный AI-индикатор для скальпинга: тренд, моментум, динамические пороги, AI-прогноз.  
  Источник: [TradingView Pro Scalper AI](https://www.tradingview.com/script/HmXeAuPG-Pro-Scalper-AI-BullByte/)

- [ ] **AI-анализ стакана (Order Book AI)**  
  Кластеризация и ML-анализ плотности заявок для поиска “стен” и аномалий.

- [ ] **AI-анализ объема (Volume Profile AI)**  
  Кластеризация по объему для поиска “горячих зон” интереса.

- [ ] **AI-анализ свечных паттернов**  
  ML-классификация сложных свечных комбинаций.

- [ ] **AI-анализ новостей и соцсетей (Sentiment AI)**  
  Индекс настроения рынка на основе новостей и соцсетей.

---

**Примечание:**
- Каждый индикатор будет реализован как отдельный модуль и интегрирован в систему сигналов бота (вариант A: отдельная “лампочка”/ячейка в UI).
- После внедрения каждого — отмечать задачу как выполненную и фиксировать в логе.
- Итоговый сигнал будет формироваться по большинству/весам, с возможностью гибкой настройки. 