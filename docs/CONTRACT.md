# Контракт v1

Все API одного origin. Cookie `ekt_session` выдаёт сервер; клиент не выбирает сессию. Мутации требуют `X-CSRF-Token` из `GET /api/session`.

Product: `id` string, `name`, `article`, `supplier_article`, `category`, `brand`, `price` number|null, `currency` string|null, `quantity` number|null (общий остаток API), `stock` number|null (только разрешённые склады), `stores` array, `specs` object (числа в А, В, кА), `evidence` object (значение и путь источника), `conflicts` array, `source` object (kind, fetched_at), `raw` object. Неизвестно = null; не 0. Конфликтный параметр = null с обеими версиями в evidence.

POST `/api/chat`: `{message, request_id}` → `{answer, products, analogs, proposal, cart_url, mode, latency_ms}`. `request_id` UUID обеспечивает повторяемость доставки в пределах сессии.

POST `/api/proposals`: `{product_id, quantity}` → `{id, product, quantity, expires_at, status}`. Новое предложение отменяет предыдущее этой сессии. Не изменяет корзину.

POST `/api/proposals/{id}/confirm`: `{confirm:true}`. Идентификатор связан с серверной сессией, количеством, отпечатком цены/характеристик/остатков и TTL. Повтор успешного подтверждения возвращает ту же операцию без добавления.

POST `/api/proposals/{id}/cancel`: `{}`. GET `/api/cart`: текущая демонстрационная корзина. `/cart` — её страница. Заказ и резерв отсутствуют.

POST `/api/upload`: multipart file, максимум 5 MiB, XLSX/DOCX/PDF/JPEG/PNG. Возвращает черновые позиции `{query, quantity, confidence}`. Проверка и исправление пользователем обязательны; количество null означает уточнение. Затем обычный поиск и отдельное предложение/подтверждение.

Ошибки: HTTP 400/409/413/422/502/503, `{detail: message}` без секретов и внутренних исключений. Поиск ограничен импортированной выборкой; источник/дата/охват показаны в `/api/status`.
