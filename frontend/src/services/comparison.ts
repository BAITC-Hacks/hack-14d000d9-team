import { category, mentionedProducts, money, normalize, products, searchProducts, specifications } from './catalog';
import type { ChatResponse, Message, Product } from '../types/chat';

const intent = /сравн|отлич|разниц|лучш|хуж|выбрат|выбер|посовет|порекоменд|подбери|подобрат|подойд|дешев|дешёв|недорог|бюджет|дороже|дорогой|выгод|стоит брать/i;

function categoryRequest(query: string): string | undefined {
  if (/автомат|выключател|drx/i.test(query)) return 'Автоматические выключатели';
  if (/реле/i.test(query)) return 'Реле контроля';
  if (/короб|подрозет/i.test(query)) return 'Монтажные коробки';
  if (/ламп|светиль|освещ/i.test(query)) return 'Освещение';
}

export function comparisonReply(query: string, messages: Message[], attachmentProducts: Product[] = []): ChatResponse | undefined {
  if (!intent.test(query)) return;
  const explicit = mentionedProducts(query);
  const previous = [...messages].reverse().find((m) => m.role === 'assistant' && m.productIds?.length)?.productIds || [];
  const group = categoryRequest(query);
  let candidates = explicit.length ? explicit : attachmentProducts.length ? attachmentProducts : group ? products.filter((p) => category(p) === group) : products.filter((p) => previous.includes(p.id));
  if (!candidates.length && !group) candidates = searchProducts(query);
  const priceIntent = /дешев|дешёв|недорог|бюджет|дороже|дорогой|выгод|по цене/i.test(query);
  const budgetMatch = normalize(query).match(/(?:до|бюджет(?:ом)?(?:\s+до)?)\s*(\d+(?:[ \u00a0]\d{3})*(?:[.,]\d+)?)\s*(тыс(?:яч)?|к(?=\s|$))?/u);
  const budget = budgetMatch ? Number(budgetMatch[1].replace(/[ \u00a0]/g, '').replace(',', '.')) * (budgetMatch[2] ? 1000 : 1) : undefined;
  if (budget !== undefined) candidates = candidates.filter((p) => p.price <= budget);
  if (!candidates.length) return { content: budget !== undefined ? `В выбранной группе нет товаров с ценой до ${money(budget)} в этой выборке. Уточните категорию или бюджет.` : 'Что сравнить? Напишите два артикула или тип товара и задачу. Например: «Сравни 027228 и 027230 по цене». Что важнее: стоимость, наличие или конкретные характеристики?' };
  const groups = new Set(candidates.map(category));
  if (groups.size > 1 && !priceIntent) return { content: 'Это товары разных категорий. Общая оценка «лучше» или «хуже» здесь не подходит. Для какой задачи выбираете и какие параметры обязательны? По запросу могу отдельно сравнить их цены.', productIds: candidates.slice(0, 4).map((p) => p.id) };
  const ranked = [...candidates].sort((a, b) => a.price - b.price);
  const chosen = priceIntent ? (/дороже|дорогой/i.test(query) ? [...ranked].reverse() : ranked).slice(0, 3) : candidates.slice(0, 3);
  const rows = chosen.map((p) => {
    const stock = p.quantity === undefined ? 'остаток неизвестен' : `остаток по выгрузке ${p.quantity} шт.`;
    const specs = specifications(p).map(([label, value]) => `${label}: ${value}`).join('; ');
    return `${p.name}\nАртикул ${p.article}: ${money(p.price)}, ${stock}.${specs ? `\n${specs}.` : '\nПолные характеристики не предоставлены.'}${p.dataWarning ? `\nВнимание: ${p.dataWarning}` : ''}`;
  });
  let conclusion = '';
  if (priceIntent && ranked.length > 1) {
    const difference = ranked.at(-1)!.price - ranked[0].price;
    conclusion = difference === 0 ? 'У найденных позиций одинаковая цена.' : `По цене среди ${candidates.length} найденных позиций дешевле ${ranked[0].article}: ${money(ranked[0].price)}. Разница с самой дорогой позицией — ${money(difference)}.`;
  } else if (chosen.length === 1) conclusion = 'Есть одна подходящая позиция в выборке. Для сравнения укажите второй артикул.';
  else conclusion = 'Сравнение доступных данных приведено выше. Назвать один товар лучше другого по качеству или надёжности на основе этих данных нельзя.';
  return { content: `${budget !== undefined ? `Бюджет: до ${money(budget)}.\n\n` : ''}${rows.join('\n\n')}\n\n${conclusion}\n\nЦена не определяет техническую пригодность. Для какой задачи выбираете и какие характеристики обязательны? Для электрической защиты нужны подтверждённые параметры; больший ток сам по себе не означает «лучше». Цены и остатки относятся к предоставленному снимку данных.`, productIds: chosen.map((p) => p.id) };
}
