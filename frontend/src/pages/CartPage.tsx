import { useEffect,useState } from 'react';
import { readCart } from '../services/backendApi';
import { money } from '../services/catalog';
export function CartPage(){
  const [cart,setCart]=useState<Awaited<ReturnType<typeof readCart>>|null>(null),[error,setError]=useState('');
  useEffect(()=>{readCart().then(setCart).catch(e=>setError(e.message));},[]);
  return <main className="catalog-main integrated-cart"><a href="/">← Вернуться к каталогу</a><h1>Демонстрационная корзина</h1><p>Товары не зарезервированы на ekt.kz. Заказ и оплата не выполняются.</p>
    {error&&<p className="error">{error}</p>}{!cart&&!error&&<p>Загружаем корзину…</p>}{cart?.items.length===0&&<p>Корзина пуста. Найдите товар и подтвердите добавление.</p>}
    {cart?.items.map(({product,quantity})=><article className="cart-item" key={product.id}><h2>{product.name}</h2><p>Артикул: {product.article}</p><p>{quantity} шт. × {money(product.price,product.currency)}</p>{product.dataWarning&&<p className="data-warning">{product.dataWarning}</p>}</article>)}
    {cart&&cart.items.length>0&&<strong>{cart.total===null?'Итог неизвестен: цена или валюта не подтверждена.':`Итого: ${money(cart.total,cart.currency)}`}</strong>}
  </main>;
}
