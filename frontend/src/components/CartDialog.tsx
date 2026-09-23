import { useEffect, useRef, useState } from 'react';
import { Check, LoaderCircle, ShoppingCart, X } from 'lucide-react';
import { confirmCart, getStockQuote } from '../services/chatApi';
import { money } from '../services/catalog';
import type { Product, StockQuote } from '../types/chat';

export function CartDialog({ product, onClose }: { product: Product; onClose: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const controller = useRef(new AbortController());
  const requestId = useRef(crypto.randomUUID());
  const [quote, setQuote] = useState<StockQuote | null>(null);
  const [quantity, setQuantity] = useState(1);
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState('');
  const [cartUrl, setCartUrl] = useState('');
  const submitting = useRef(false);
  useEffect(() => {
    dialog.current?.showModal();
    const abort = new AbortController(); controller.current = abort;
    getStockQuote(product.id, abort.signal).then((value) => { if (!abort.signal.aborted) setQuote(value); }).catch((cause) => { if (!abort.signal.aborted) setError(cause instanceof Error ? cause.message : 'Не удалось проверить наличие.'); }).finally(() => { if (!abort.signal.aborted) setBusy(false); });
    return () => { abort.abort(); };
  }, [product.id]);
  async function confirm() {
    if (!quote || busy || submitting.current) return;
    submitting.current = true; setBusy(true); setError('');
    try { setCartUrl(await confirmCart(quote, quantity, requestId.current, controller.current.signal)); }
    catch (cause) { if (!controller.current.signal.aborted) setError(cause instanceof Error ? cause.message : 'Не удалось добавить товар.'); }
    finally { submitting.current = false; setBusy(false); }
  }
  return <dialog className="cart-dialog" ref={dialog} aria-labelledby="cart-title" onCancel={(e) => { if (busy) e.preventDefault(); else onClose(); }}>
    <header><ShoppingCart size={22} /><h2 id="cart-title">{cartUrl ? 'Товар добавлен' : 'Добавление в корзину'}</h2><button className="icon-button" title="Закрыть" aria-label="Закрыть" onClick={onClose} disabled={busy}><X size={20} /></button></header>
    <p>{product.name}</p><small>Артикул: {product.article}</small>
    {busy && <p className="status"><LoaderCircle className="spinner" size={16} /> Проверяем данные…</p>}
    {error && <p className="error" role="alert">{error}</p>}
    {quote && !cartUrl && <><p>Доступно: {quote.stock} шт. · {money(quote.price)} / шт.</p><label className="quantity">Количество<input type="number" min={1} max={quote.stock} step={1} value={quantity} disabled={busy} onChange={(e) => { setQuantity(Number(e.target.value)); requestId.current = crypto.randomUUID(); }} /></label><p>Итого: <strong>{Number.isFinite(quantity) ? money(quantity * quote.price) : '—'}</strong></p><button className="primary-button" onClick={confirm} disabled={busy || !Number.isInteger(quantity) || quantity < 1 || quantity > quote.stock}><Check size={18} />Да, добавить {quantity > 0 ? quantity : ''} шт.</button></>}
    {cartUrl && <a className="primary-button" href={cartUrl} target="_blank" rel="noreferrer">Перейти в корзину</a>}
    {!quote && !busy && <a href={product.url} target="_blank" rel="noreferrer">Открыть товар на ekt.kz →</a>}
  </dialog>;
}
