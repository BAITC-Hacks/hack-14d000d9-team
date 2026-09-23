import { ExternalLink, MessageCircle, Package, ShoppingCart } from 'lucide-react';
import { useState } from 'react';
import { money, specifications } from '../services/catalog';
import type { Product } from '../types/chat';

interface Props { product: Product; compact?: boolean; onAsk?: (product: Product) => void; onBuy: (product: Product) => void }
export function ProductCard({ product, compact, onAsk, onBuy }: Props) {
  const [failed, setFailed] = useState(false);
  return <article className={`product-card ${compact ? 'product-card--compact' : ''}`}>
    <div className="product-image">{product.image && !failed ? <img src={product.image} alt={product.name} loading="lazy" onError={() => setFailed(true)} /> : <Package size={36} aria-label="Фото отсутствует" />}</div>
    <div className="product-info"><span className="article">Арт. {product.article}</span>
      <a className="product-name" href={product.url || undefined} target="_blank" rel="noreferrer">{product.name.replace(/^\*+/, '')}<ExternalLink size={12} /></a>
      <span className={`stock ${product.quantity ? 'stock--available' : ''}`}><span />{product.quantity === undefined ? 'Наличие уточняется' : `${product.quantity} шт. по выгрузке`}</span>
      <strong className="price">{money(product.price, product.currency)}</strong><small>{product.sourceKind === 'synthetic' ? 'Синтетический товар для демо' : 'Цена из снимка API'}</small>
      {(product.description || product.dataWarning || product.stores?.length) && <div className="product-details">
        {product.dataWarning && <p className="data-warning">{product.dataWarning}</p>}
        <details><summary>Характеристики и описание</summary><dl>{specifications(product).map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl><p>{product.description}</p><small>Сертификат в предоставленных данных отсутствует.</small></details>
        <details><summary>Остатки по складам · {product.quantity} шт.</summary><dl>{product.stores?.map((store) => <div key={store.id}><dt>{store.name}</dt><dd>{store.quantity} шт.</dd></div>)}</dl><small>{product.stock == null ? 'Доступность для продажи не подтверждена.' : `Доступно на разрешённых складах: ${product.stock} шт.`}</small></details>
      </div>}
      <div className="product-actions"><button className="buy-button" onClick={() => onBuy(product)}><ShoppingCart size={16} />В корзину</button>
        {onAsk && <button className="icon-button" title="Обсудить товар" aria-label={`Обсудить ${product.article}`} onClick={() => onAsk(product)}><MessageCircle size={18} /></button>}</div>
    </div>
  </article>;
}
