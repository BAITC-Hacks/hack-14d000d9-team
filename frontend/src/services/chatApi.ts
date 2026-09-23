import type { ChatResponse, Message, StockQuote } from '../types/chat';
import { products, searchProducts, money, specifications } from './catalog';
import { comparisonReply } from './comparison';

export const apiEnabled = import.meta.env.VITE_CHAT_MODE === 'api';
const baseUrl = (import.meta.env.VITE_API_BASE_URL || '/api').replace(/\/$/, '');
async function checkedJson(response: Response): Promise<unknown> {
  if (!response.ok) throw new Error(`Сервис недоступен (${response.status}). Повторите попытку позже.`);
  return response.json();
}
export async function sendChatMessage(messages: Message[], signal: AbortSignal, files: File[] = [], contextProductId?: number): Promise<ChatResponse> {
  if (!apiEnabled) return localReply(messages, files, contextProductId);
  const body = new FormData();
  body.append('messages', JSON.stringify(messages));
  if (contextProductId) body.append('productId', String(contextProductId));
  files.forEach((file) => body.append('files', file, file.name));
  const data = await checkedJson(await fetch(`${baseUrl}/chat`, { method: 'POST', body, signal }));
  if (typeof data !== 'object' || !data || !('content' in data) || typeof data.content !== 'string') throw new Error('Сервис вернул некорректный ответ.');
  const ids = 'productIds' in data && Array.isArray(data.productIds) ? data.productIds.filter((id): id is number => typeof id === 'number' && products.some((p) => p.id === id)) : [];
  return { content: data.content, productIds: ids };
}
async function localReply(messages: Message[], files: File[], contextProductId?: number): Promise<ChatResponse> {
  const query = messages.at(-1)?.content || '';
  const textFiles = files.filter((f) => /\.(txt|csv|tsv|json|md|xml|log)$/i.test(f.name) && f.size <= 2 * 1024 * 1024);
  const texts = await Promise.all(textFiles.map((f) => f.text()));
  const attachedMatches = texts.flatMap((text) => products.filter((p) => text.toLowerCase().includes(p.article.toLowerCase())));
  const fileNote = files.length ? `Прикреплено файлов: ${files.length}. ` + (textFiles.length ? `Проверены артикулы в текстовых файлах: ${textFiles.length}. ` : '') + (files.length > textFiles.length ? 'Для анализа остальных вложений нужен подключённый сервис распознавания; их содержимое пока не анализировалось. ' : '') : '';
  const comparison = comparisonReply(query, messages, [...new Map(attachedMatches.map((p) => [p.id, p])).values()]);
  if (comparison) return { ...comparison, content: fileNote + comparison.content };
  if (/^(привет|здравствуй(?:те)?|добрый (?:день|вечер|утро))[!.\s]*$/i.test(query.trim())) return { content: 'Здравствуйте! Какой товар или задачу обсудим? Можно указать артикулы для сравнения, бюджет или приложить список товаров.' };
  if (/достав|оплат/i.test(query)) return { content: fileNote + 'В предоставленной выгрузке нет условий оплаты и доставки. Уточните их у менеджера на ekt.kz; я не могу подтвердить сроки или стоимость доставки.' };
  const context = products.find((p) => p.id === contextProductId);
  const previousIds = [...messages].reverse().find((m) => m.role === 'assistant' && m.productIds?.length)?.productIds;
  const followup = /характерист|сертификат|наличи|аналог|подробнее|склад|остат|сколько|описан|ток|напряж|миним|парт|алмат|шымкент|астан|нур-султан/i.test(query);
  let found = attachedMatches.length ? [...new Map(attachedMatches.map((p) => [p.id, p])).values()] : query.trim() ? searchProducts(query) : [];
  if (!found.length && followup) found = context ? [context] : products.filter((p) => previousIds?.includes(p.id));
  if (/аналог/i.test(query)) return { content: fileNote + 'Для подбора безопасного аналога нужны полные характеристики и подтверждённые остатки. В этой выгрузке их нет. Укажите артикул и параметры: номинальный ток, число полюсов, напряжение и отключающую способность. Похожие названия не подтверждают взаимозаменяемость.' };
  if (/добав|корзин/i.test(query)) return { content: fileNote + 'Откройте «В корзину» на карточке товара. Сначала проверяются остатки и цена, затем вы подтверждаете количество. Сейчас сервис корзины не подключён, поэтому состав корзины не изменён.' };
  if (!found.length) return { content: fileNote + (files.length ? '\nСовпадений по артикулам в доступных текстовых вложениях не найдено. Можно указать артикул в сообщении.' : 'Не удалось связать вопрос с товарами в выборке. Опишите, что нужно сделать, и укажите тип товара или артикул. Сейчас работает демо-поиск по 40 товарам, поэтому он понимает не все формулировки; это не означает, что товара нет на сайте.') };
  if (found.length === 1 && found[0].description) {
    const product = found[0];
    const stores = product.stores?.filter((store) => store.quantity > 0).map((store) => `${store.name}: ${store.quantity} шт.`).join('\n');
    return { content: fileNote + `${product.name}\n\nПо предоставленной выгрузке: ${money(product.price)}, общий остаток ${product.quantity} шт.\n\n${specifications(product).map(([label, value]) => `${label}: ${value}`).join('\n')}\n\n${product.dataWarning}\n\nОстатки по складам:\n${stores}\n\nСертификат не предоставлен. Цена и наличие относятся к снимку данных; перед покупкой нужна актуализация.`, productIds: [product.id] };
  }
  return { content: fileNote + (followup ? 'В выгрузке есть название, артикул и цена. Полные характеристики, сертификаты и остатки не переданы. ' : `Найдено в выгрузке: ${found.length}. `) + 'Цены ниже взяты из предоставленных данных и требуют актуализации. Наличие нужно уточнить. Полная карточка доступна по ссылке на ekt.kz.', productIds: found.slice(0, 4).map((p) => p.id) };
}
export async function getStockQuote(productId: number, signal: AbortSignal): Promise<StockQuote> {
  if (!apiEnabled) {
    const product = products.find((item) => item.id === productId);
    throw new Error((product?.quantity !== undefined ? `По выгрузке: ${product.quantity} шт. Для покупки нужно подтвердить актуальные остатки. ` : 'Остатки не переданы. ') + 'Подключение к корзине ekt.kz пока не настроено; товар не добавлен.');
  }
  const quote = await checkedJson(await fetch(`${baseUrl}/products/${productId}/quote`, { signal })) as StockQuote;
  if (!quote || typeof quote.quoteId !== 'string' || !quote.quoteId || quote.productId !== productId || !Number.isInteger(quote.stock) || quote.stock < 0 || !Number.isFinite(quote.price) || quote.price < 0) throw new Error('Не удалось подтвердить цену и наличие.');
  return quote;
}
export async function confirmCart(quote: StockQuote, quantity: number, requestId: string, signal: AbortSignal): Promise<string> {
  if (!Number.isInteger(quantity) || quantity < 1 || quantity > quote.stock) throw new Error('Количество превышает доступный остаток.');
  const data = await checkedJson(await fetch(`${baseUrl}/cart/items`, { method: 'POST', signal, headers: { 'Content-Type': 'application/json', 'Idempotency-Key': requestId }, body: JSON.stringify({ productId: quote.productId, quoteId: quote.quoteId, quantity, confirmed: true }) }));
  if (!data || typeof data !== 'object' || !('cartUrl' in data) || typeof data.cartUrl !== 'string') throw new Error('Сервис не вернул ссылку на корзину.');
  const url = new URL(data.cartUrl, window.location.origin);
  if (!['http:', 'https:'].includes(url.protocol) || (url.origin !== window.location.origin && url.hostname !== 'ekt.kz' && url.hostname !== 'www.ekt.kz')) throw new Error('Некорректная ссылка на корзину.');
  return url.href;
}
