import { useEffect, useRef } from 'react';
import { ArrowRight, FileText, Sparkles } from 'lucide-react';
import type { Message, Product } from '../../types/chat';
import { products } from '../../services/catalog';
import { ProductCard } from '../ProductCard';

interface Props { messages: Message[]; isLoading: boolean; onBuy: (product: Product) => void; onPrompt: (text: string) => void }
export function MessageList({ messages, isLoading, onBuy, onPrompt }: Props) {
  const end = useRef<HTMLDivElement>(null);
  useEffect(() => { end.current?.scrollIntoView({ block: 'nearest' }); }, [messages, isLoading]);
  return <section className="messages" role="log" aria-label="Сообщения" aria-live="polite">
    {messages.length === 0 && <div className="chat-welcome"><div className="welcome-icon"><Sparkles size={30} /></div><span className="welcome-eyebrow">EKT AI</span><h2>Что подберём сегодня?</h2><p>Задайте вопрос о товаре или прикрепите спецификацию.</p><div className="prompts">{['Характеристики 027228', 'Остатки 027228 по складам', 'Найти реле RM17UAS16', 'Оплата и доставка'].map((text) => <button key={text} disabled={isLoading} onClick={() => onPrompt(text)}>{text}<ArrowRight size={15} /></button>)}</div><span className="welcome-note">Цены и остатки из предоставленной выгрузки</span></div>}
    {messages.map((message) => <div key={message.id} className={`message message--${message.role}`}><strong>{message.role === 'user' ? 'Вы' : 'EKT Assistant'}</strong>{message.content && <p>{message.content}</p>}{message.attachments?.map((file, i) => <div className="message-file" key={i}><FileText size={16} /><span>{file.name}</span></div>)}{message.productIds?.map((id) => { const product = products.find((p) => p.id === id); return product ? <ProductCard key={id} product={product} compact onBuy={onBuy} /> : null; })}</div>)}
    {isLoading && <p className="status" role="status">Ищу информацию…</p>}<div ref={end} />
  </section>;
}
