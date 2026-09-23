import page1 from '../data/catalog-page-1.json';
import page2 from '../data/catalog-page-2.json';
import detailedProduct from '../data/product-515291.json';
import type { Product } from '../types/chat';

export const products: Product[] = [...page1.items, ...page2.items].map((product) => product.id === detailedProduct.id ? {
  ...product, ...detailedProduct, currency: 'KZT',
  dataWarning: 'Номинальный ток требует уточнения: в названии и описании — 160 А, в поле NOMINALNYY_TOK — 250 А. Не используйте эти данные для подбора защиты без проверки у поставщика.',
} : {...product, currency: 'KZT'});

export function specifications(product: Product): [string, string][] {
  const fields = [
    ['TORGOVAYA_MARKA', 'Производитель'], ['ARTIKULPOSTAVSHCHIKA', 'Артикул производителя'],
    ['KOLICHESTVO_POLYUSOV', 'Количество полюсов'], ['NOMINALNOE_NAPRYAZHENIE', 'Напряжение'],
    ['NOMINALNAYA_OTKLYUCHAYUSHCHAYA_SPOSOBNOST', 'Отключающая способность'],
    ['TIP_USTANOVKI', 'Монтаж'],
  ];
  return fields.flatMap(([key, label]) => typeof product.properties?.[key] === 'string' ? [[label, product.properties[key] as string] as [string, string]] : []);
}
export const money = (value: number, currency?: string | null) => Number.isFinite(value) ? `${new Intl.NumberFormat('ru-RU').format(value)} ${!currency || currency === 'KZT' ? '₸' : currency}` : 'Цена неизвестна';
export const normalize = (text: string) => text.toLowerCase().replace(/ё/g, 'е');
export function category(product: Product) {
  if (/реле/i.test(product.name)) return 'Реле контроля';
  if (/DRX|Диф\.авт/i.test(product.name)) return 'Автоматические выключатели';
  if (/коробка|УПрк|УПп/i.test(product.name)) return 'Монтажные коробки';
  return 'Освещение';
}
export function searchProducts(query: string): Product[] {
  const value = normalize(query).trim();
  if (!value) return products;
  const exact = mentionedProducts(query);
  if (exact.length) return exact;
  const words = value.split(/[^\p{L}\p{N}_.-]+/u).filter((w) => w.length > 1);
  const stopWords = new Set(['мне', 'нужен', 'нужна', 'найди', 'есть', 'ли', 'товар', 'про', 'расскажи', 'покажи', 'для', 'что', 'по', 'на', 'это', 'цену', 'наличие']);
  const tokens = words.filter((w) => !stopWords.has(w));
  return products.map((p) => ({ product: p, score: tokens.filter((word) => normalize(`${p.name} ${p.article} ${category(p)}`).includes(word)).length }))
    .filter((p) => p.score > 0).sort((a, b) => b.score - a.score).map((p) => p.product);
}

export function mentionedProducts(query: string): Product[] {
  const tokens = new Set(normalize(query).split(/[^\p{L}\p{N}_-]+/u));
  return products.filter((p) => [p.article, p.article.replace(/_$/, ''), String(p.id), p.name.match(/^\d{6}(?=\s)/)?.[0]]
    .some((id) => id && tokens.has(normalize(id))));
}
