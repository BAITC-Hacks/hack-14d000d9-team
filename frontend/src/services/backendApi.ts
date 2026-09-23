import type { Product, Proposal, ReviewItem } from '../types/chat';
import { products } from './catalog';
const base = (import.meta.env.VITE_API_BASE_URL || '/api').replace(/\/$/, '');
let csrf = '';
let sessionRequest: Promise<void> | null = null;
let activeProposal: string | null = null;
export type BackendProduct = {
  id: string; name: string; article: string; price: number | null; currency: string | null;
  quantity: number | null; stock: number | null; image: string | null; url: string | null;
  description: string; stores: {id: number; name: string; quantity: number}[];
  source: {kind: string}; conflicts: {field: string; values: number[]; message: string}[];
  raw: {properties?: Product['properties']};
};
async function checked(response: Response) {
  const data = await response.json();
  if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : `Ошибка сервера (${response.status}).`);
  return data;
}
export function fromBackend(p: BackendProduct): Product {
  const id = p.id.startsWith('demo-') ? -Number(p.id.slice(5)) : Number(p.id);
  if (!Number.isFinite(id)) throw new Error('Некорректный ID товара.');
  return { id, backendId: p.id, name: p.name, article: p.article, price: p.price ?? NaN,
    currency: p.currency, quantity: p.quantity ?? undefined, stock: p.stock,
    image: p.image, url: p.url || '', url_api_detail: '', description: p.description,
    stores: p.stores, properties: p.raw.properties, sourceKind: p.source.kind,
    dataWarning: p.conflicts.map(c => `${c.field === 'current' ? 'Ток, А' : c.field}: ${c.values.join(' / ')}. ${c.message}`).join('\n') || undefined };
}
export function mergeProducts(incoming: Product[]) {
  for (const item of incoming) {
    const index = products.findIndex(p => p.id === item.id);
    if (index < 0) products.push(item); else products[index] = item;
  }
}
export async function ensureSession() {
  if (csrf) return;
  if (!sessionRequest) sessionRequest = (async () => {
    const data = await checked(await fetch(`${base}/session`, {credentials:'same-origin'}));
    csrf = data.csrf; activeProposal = data.proposal?.id ?? null;
  })().finally(() => { sessionRequest = null; });
  await sessionRequest;
}
export async function request(path: string, body?: object | FormData, signal?: AbortSignal) {
  await ensureSession();
  const form = body instanceof FormData;
  return checked(await fetch(base + path, { method: body === undefined ? 'GET' : 'POST', signal,
    credentials: 'same-origin', headers: body === undefined ? {} : { 'X-CSRF-Token': csrf, ...(form ? {} : {'Content-Type':'application/json'}) },
    body: body === undefined ? undefined : form ? body : JSON.stringify(body) }));
}
export async function loadCatalog() {
  const [data, status] = await Promise.all([request('/products'), request('/status')]);
  products.splice(0, products.length, ...(data.items as BackendProduct[]).map(fromBackend));
  return status as {mode:string; real_products:number; demo_products:number; catalog_mode:string};
}
export function backendId(id: number) { return products.find(p => p.id === id)?.backendId || String(id); }
export function parseProposal(p: {id:string; product:BackendProduct; quantity:number; expires_at:number; status:string}): Proposal {
  activeProposal = p.id; return {...p, product: fromBackend(p.product)};
}
export async function propose(productId: number, quantity: number, signal?: AbortSignal) {
  return parseProposal(await request('/proposals', {product_id:backendId(productId), quantity}, signal));
}
export async function confirmProposal(id: string, signal?: AbortSignal): Promise<string> {
  const result = await request(`/proposals/${encodeURIComponent(id)}/confirm`, {confirm:true}, signal);
  activeProposal = null;
  if (result.cart_url !== '/cart') throw new Error('Некорректная ссылка на корзину.');
  return '/cart';
}
export async function cancelProposal(id: string) {
  await request(`/proposals/${encodeURIComponent(id)}/cancel`, {});
  if (activeProposal === id) activeProposal = null;
}
export async function resetChat() { await request('/session/reset', {}); activeProposal = null; }
export async function remoteReply(content: string, requestId: string, signal: AbortSignal, contextId?: number) {
  const data = await request('/chat', {message:content,request_id:requestId,proposal_id:activeProposal,
    context_product_id:contextId === undefined ? null : backendId(contextId)}, signal);
  const found = ((data.products || []) as BackendProduct[]).map(fromBackend);
  const analogProducts = (data.analogs || []).map((a: {product:BackendProduct}) => fromBackend(a.product));
  mergeProducts([...found, ...analogProducts]);
  const comparisons = (data.analogs || []).map((a:{product:BackendProduct;matches:string[];differences:string[];unknown:string[];note:string}) =>
    `\n\nКандидат ${a.product.article}\nСовпадения: ${a.matches.join('; ')}\nРазличия: ${a.differences.join('; ') || 'не обнаружены в проверенных полях'}\nНеизвестно: ${a.unknown.join('; ')}\n${a.note}`).join('');
  if (data.cart_url) activeProposal = null;
  return {content: String(data.answer) + comparisons, productIds:[...new Set<number>([...found,...analogProducts].map((p:Product)=>p.id))],
    proposal:data.proposal ? parseProposal(data.proposal) : undefined, cartUrl:data.cart_url === '/cart' ? '/cart' : undefined};
}
export async function uploadFiles(files: File[], signal: AbortSignal) {
  const review: ReviewItem[] = []; const notes: string[] = [];
  for (const file of files) {
    const body = new FormData(); body.append('file',file,file.name);
    const result = await request('/upload',body,signal);
    review.push(...result.items); notes.push(`${file.name}: ${result.warning}`);
  }
  return {content: notes.join('\n'),review};
}
export async function readCart() {
  const result = await request('/cart');
  return {items:result.items.map((i:{product:BackendProduct;quantity:number})=>({product:fromBackend(i.product),quantity:i.quantity})) as {product:Product;quantity:number}[],
    total:result.total as number|null,currency:result.currency as string|null};
}
