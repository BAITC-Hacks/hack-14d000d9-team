import { useState } from 'react';
import { ArrowUpRight, Search, Zap } from 'lucide-react';
import { ChatWidget } from '../components/chat/ChatWidget';
import { CartDialog } from '../components/CartDialog';
import { ProductCard } from '../components/ProductCard';
import { searchProducts } from '../services/catalog';
import type { Product } from '../types/chat';

export function ChatPage() {
  const [purchase, setPurchase] = useState<Product | null>(null);
  const [context, setContext] = useState<Product | null>(null);
  const [query, setQuery] = useState('');
  const embedded = new URLSearchParams(window.location.search).get('widget') === '1';
  const found = searchProducts(query);
  return <div className={embedded ? 'embedded' : 'storefront'}>
    {!embedded && <>
      <div className="utility-bar"><div><span>Электротехника для дома и бизнеса</span><a href="https://ekt.kz/" target="_blank" rel="noreferrer">ekt.kz <ArrowUpRight size={14} /></a></div></div>
      <header className="store-header"><a className="brand" href="/"><Zap size={32} fill="currentColor" /><span>EKT<small>ekt.kz</small></span></a><label className="catalog-search"><Search size={20} /><input aria-label="Поиск по каталогу" placeholder="Название или артикул товара" value={query} onChange={(event) => setQuery(event.target.value)} /></label></header>
      <main className="catalog-main"><div className="catalog-heading"><div><span className="eyebrow">EKT.KZ</span><h1>Электротехническая продукция</h1></div></div>
        <div className="results-toolbar"><span>Найдено: {found.length}</span><span>Цены и остатки из выгрузки</span></div>
        <div className="product-grid">{found.map((product) => <ProductCard key={product.id} product={product} onAsk={setContext} onBuy={setPurchase} />)}</div>
        {!found.length && <div className="no-results">По этому запросу товары не найдены.</div>}
      </main>
      <footer className="store-footer">HACKALEM AI<span>Демонстрационная страница · Не официальный сайт ekt.kz</span></footer>
    </>}
    <ChatWidget context={context} onClearContext={() => setContext(null)} onBuy={setPurchase} embedded={embedded} />
    {purchase && <CartDialog key={purchase.id} product={purchase} onClose={() => setPurchase(null)} />}
  </div>;
}
