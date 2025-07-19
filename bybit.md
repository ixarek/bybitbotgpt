Ниже — пошаговая инструкция, как действительно торговать ботом в режиме Demo на основном домене **bybit.com** через API v5.
Кратко: переключитесь в Demo Trading на главном сайте, создайте там отдельный ключ, подключайтесь к домену `api-demo.bybit.com` (REST) или `wss://stream‑demo.bybit.com` (WebSocket‑private), и в классе‑клиенте укажите `demo=True`. Ниже детали с тонкостями, ограничениями и примером кода.

---

## 1. Почему **Demo** вместо **Testnet**

* Demo‑счёт формируется прямо на production‑платформе и повторяет реальный стакан цен, тогда как Testnet живёт в отдельном order‑book‑мире с искусственной ликвидностью — отсюда «нереалистичные» свечи, которые вы наблюдаете ([bybit.com][1]).
* API для Demo доступен сразу после включения режима; функционал почти как у боевого, но без ввода/вывода средств и c сокращённым списком эндпойнтов ([bybit-exchange.github.io][2]).

---

## 2. Включаем Demo‑режим и создаём ключ

1. Войдите на **bybit.com**, кликните по аватару и выберите **Demo Trading** — это создаст отдельный demo‑UID, изолированный от вашего боевого счёта ([bybit-exchange.github.io][2]).
2. Уже находясь внутри Demo‑режима, вновь зайдите в **API**‑менеджер и нажмите **Create New Key**. Ключи, созданные здесь, помечаются системой именно как demo и будут работать только на `api-demo.bybit.com` ([bybit-exchange.github.io][2], [bybit.com][3]).
3. *Важно:* если создать ключ в Demo, а стучаться на основной `api.bybit.com`, получите «10003 Invalid API key»; аналогично наоборот — проверка идёт по соответствию домен ↔ тип ключа ([bybit-exchange.github.io][4], [bybit-exchange.github.io][4]).

---

## 3. Правильные домены и параметры подключения

| Среда       | REST‑домен                      | WebSocket(private)               | Параметры в PyBit           |
| ----------- | ------------------------------- | -------------------------------- | --------------------------- |
| **Live**    | `https://api.bybit.com`         | `wss://stream.bybit.com`         | `testnet=False, demo=False` |
| **Demo**    | `https://api‑demo.bybit.com`    | `wss://stream‑demo.bybit.com`    | `testnet=False, demo=True`  |
| **Testnet** | `https://api‑testnet.bybit.com` | `wss://stream‑testnet.bybit.com` | `testnet=True, demo=False`  |

Два критичных момента:

* Никогда не пытайтесь «Demo Trading» на субдомене testnet — Bybit прямо предупреждает, что такое сочетание «бессмысленно» и гарантированно приведёт к ошибкам ([bybit-exchange.github.io][2], [bybit-exchange.github.io][4]).
* В официальном SDK **pybit** ключевой аргумент — `demo=True`; без него будет та же ошибка 10003 ([GitHub][5]).

---

## 4. Пример минимальной инициализации (Python + pybit v5)

```python
from pybit.unified_trading import HTTP

session = HTTP(
    api_key="DEMO_API_KEY",
    api_secret="DEMO_SECRET",
    testnet=False,   # мы не на testnet
    demo=True        # мы в Demo Trading
)

# Пинг‑проверка баланса
print(session.get_wallet_balance(accountType="UNIFIED"))
```

*Если работает — в ответе retCode = 0; иначе смотрите текст ошибки 10003 и ещё раз проверьте домен/ключ.*

---

## 5. Доступные эндпойнты и ограничения

* Полный перечень разрешённых запросов приведён в документации Demo Service: торговые (`/v5/order/*`), позиции, баланс, а также выдача тестовых средств (`/v5/account/demo-apply-money`) ([bybit-exchange.github.io][2]).
* При необходимости бот может сам запросить пополнение USDT/USDC/BTC/ETH (лимит — 1 запрос в минуту) тем же REST‑вызовом, пример тела запроса приведён в оригинале документации ([bybit-exchange.github.io][2]).
* Все демо‑ордера хранятся только 7 дней; rate‑limit повышать нельзя — по умолчанию 10 rps для приватных вызовов ([bybit-exchange.github.io][2]).

---

## 6. Создание Demo‑аккаунта и ключей через API (если нужно автоматизировать)

* Главным (боевым) ключом можно вызвать `POST /v5/user/create-demo-member` на **api.bybit.com** — это создаст подчинённый demo‑UID и вернёт его ID ([bybit-exchange.github.io][2]).
* Далее через `Create Demo Account API Key` генерите ключ уже для этого UID, а работать им будете на `api-demo.bybit.com`. Эта цепочка удобна для массового развёртывания ботов под разные субаккаунты.

---

## 7. Интеграция с внешними библиотеками/ботами

* **Hummingbot**: вместо `connect bybit` запустите `connect bybit_paper_trade` — он автоматически использует demo‑домен и не трогает ваши боевые средства ([hummingbot.org][6]).
* **CCXT** или любая другая библиотека: достаточно задать `endpoint='https://api-demo.bybit.com'` и использовать обычный механизм подписи (Bybit HMAC‑SHA256).

---

## 8. Частые ошибки и лайфхаки

| Ошибка                                    | Причина                                         | Как чинить                                                                                                                 |
| ----------------------------------------- | ----------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------- |
| `10003 Invalid API key`                   | Неправильное сочетание «ключ ↔ домен»           | Сверьте таблицу из §3 и выставьте `demo=True` или правильный endpoint ([bybit-exchange.github.io][4], [Stack Overflow][7]) |
| Ордеры «не видно» в GUI                   | Фронтэнд отображает максимум 50 ордеров         | Ориентируйтесь на `/order/realtime` или WebSocket‑topic `order`                                                            |
| «Пустой» баланс после долгого бездействия | Demo‑аккаунт очищается через 30 дней без захода | Просто снова зайдите в Demo, баланс выдастся автоматически ([bybit.com][1])                                                |

---

## 9. Итого

* Demo‑режим на **bybit.com** полностью поддерживается в API v5.
* Используйте **только** `api-demo.bybit.com` и ключ, созданный внутри Demo‑Trading.
* В SDK добавляйте `demo=True`; в низкоуровневых библиотеках задавайте полный URL.
* Пополнять виртуальные средства и даже создавать demo‑субаккаунты можно программно.
  Следуя этим шагам, вы получите те же свечи и ликвидность, что в live‑торговле, но без риска потерять реальные деньги.

[1]: https://www.bybit.com/en/help-center/article/FAQ-Demo-Trading "FAQ — Demo Trading"
[2]: https://bybit-exchange.github.io/docs/v5/demo "Demo Trading Service | Bybit API Documentation"
[3]: https://www.bybit.com/en/help-center/article/How-to-create-your-API-key "How to Create Your API Key?"
[4]: https://bybit-exchange.github.io/docs/faq "Frequently Asked Questions | Bybit API Documentation"
[5]: https://github.com/bybit-exchange/pybit/issues/203?utm_source=chatgpt.com "Demo API is not working · Issue #203 · bybit-exchange/pybit - GitHub"
[6]: https://hummingbot.org/exchanges/bybit/ "Bybit - Hummingbot"
[7]: https://stackoverflow.com/questions/71451240/bybit-api-python-invalid-api-key "pycrypto - Bybit API Python Invalid API key - Stack Overflow"
