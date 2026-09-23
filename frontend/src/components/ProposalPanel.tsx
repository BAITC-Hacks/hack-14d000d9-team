import { useState } from 'react';
import type { Proposal } from '../types/chat';
import { cancelProposal, confirmProposal } from '../services/backendApi';
import { money } from '../services/catalog';
export function ProposalPanel({proposal}:{proposal:Proposal}) {
  const [busy,setBusy]=useState(false),[done,setDone]=useState(''),[error,setError]=useState('');
  async function act(confirm:boolean) {
    if(busy||done)return; setBusy(true);setError('');
    try { if(confirm){await confirmProposal(proposal.id);setDone('added');}
      else {await cancelProposal(proposal.id);setDone('cancelled');}
    } catch(e){setError(e instanceof Error?e.message:'Ошибка подтверждения.');}
    finally{setBusy(false);}
  }
  return <section className="proposal-panel"><strong>Подтвердите точный товар и количество</strong>
    <p>{proposal.product.name}<br/>Артикул: {proposal.product.article}<br/>{proposal.quantity} шт. × {money(proposal.product.price,proposal.product.currency)}</p>
    {proposal.product.dataWarning&&<p className="data-warning">{proposal.product.dataWarning}</p>}
    <small>Действует до {new Date(proposal.expires_at*1000).toLocaleTimeString('ru-RU')}. Демонстрационная корзина, без резервирования.</small>
    {error&&<p className="error" role="alert">{error}</p>}
    {!done&&<div className="proposal-actions"><button className="primary-button" disabled={busy} onClick={()=>void act(true)}>Да, добавить {proposal.quantity} шт.</button><button disabled={busy} onClick={()=>void act(false)}>Отменить</button></div>}
    {done==='added'&&<a className="primary-button" href="/cart">Открыть актуальную корзину →</a>}
    {done==='cancelled'&&<p>Отменено. Корзина не изменена.</p>}
  </section>;
}
