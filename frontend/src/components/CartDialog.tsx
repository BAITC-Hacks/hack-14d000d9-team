import { useEffect, useRef, useState } from 'react';
import { ShoppingCart, X } from 'lucide-react';
import { propose } from '../services/backendApi';
import { apiEnabled } from '../services/chatApi';
import type { Product, Proposal } from '../types/chat';
import { ProposalPanel } from './ProposalPanel';
export function CartDialog({product,onClose}:{product:Product;onClose:()=>void}) {
  const dialog=useRef<HTMLDialogElement>(null),pending=useRef(false);
  const [quantity,setQuantity]=useState(1),[proposal,setProposal]=useState<Proposal|null>(null),[busy,setBusy]=useState(false),[error,setError]=useState('');
  useEffect(()=>{dialog.current?.showModal();},[]);
  async function prepare(){
    if(pending.current)return;
    if(!apiEnabled){setError('Для корзины нужен подключённый сервер.');return;}
    pending.current=true;setBusy(true);setError('');
    try{setProposal(await propose(product.id,quantity));}
    catch(e){setError(e instanceof Error?e.message:'Не удалось проверить товар.');}
    finally{pending.current=false;setBusy(false);}
  }
  return <dialog className="cart-dialog" ref={dialog} aria-labelledby="cart-title" onCancel={e=>{if(busy)e.preventDefault();else onClose();}}>
    <header><ShoppingCart size={22}/><h2 id="cart-title">Демонстрационная корзина</h2><button className="icon-button" aria-label="Закрыть" disabled={busy} onClick={onClose}><X size={20}/></button></header>
    {!proposal&&<><p>{product.name}</p><small>Артикул: {product.article}</small><label className="quantity">Количество<input type="number" min={1} max={10000} step={1} value={quantity} disabled={busy} onChange={e=>setQuantity(Number(e.target.value))}/></label><p>Сначала проверим цену и доступность. Добавление потребует отдельного подтверждения.</p><button className="primary-button" disabled={busy||!Number.isInteger(quantity)||quantity<1||quantity>10000} onClick={()=>void prepare()}>{busy?'Проверяем…':'Проверить товар и количество'}</button></>}
    {error&&<p className="error" role="alert">{error}</p>}{proposal&&<ProposalPanel proposal={proposal}/>}
  </dialog>;
}
