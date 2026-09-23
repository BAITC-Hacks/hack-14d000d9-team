import { request } from '../../services/backendApi';
import { useEffect, useRef, useState } from 'react';
import { MessageCircle, Plus, ShieldCheck, Sparkles, X } from 'lucide-react';
import { useChat } from '../../hooks/useChat';
import { apiEnabled } from '../../services/chatApi';
import type { Product } from '../../types/chat';
import { MessageComposer } from './MessageComposer';
import { MessageList } from './MessageList';

interface Props { context: Product | null; onClearContext: () => void; onBuy: (product: Product) => void; embedded?: boolean; standalone?: boolean }
export function ChatWidget({ context, onClearContext, onBuy, embedded, standalone }: Props) {
  const [open, setOpen] = useState(Boolean(standalone));
  const [session, setSession] = useState(0);
  const [mode,setMode] = useState(apiEnabled ? 'Подключение к серверу…' : 'Демо · локальные ответы');
  useEffect(()=>{if(apiEnabled) request('/status').then(s=>setMode(s.mode==='ai'?'ИИ · подключён':'Демо · без модели')).catch(()=>setMode('Сервер недоступен'));},[]);
  const { messages, isLoading, error, send, reset } = useChat();
  const panel = useRef<HTMLElement>(null);
  const launcher = useRef<HTMLButtonElement>(null);
  useEffect(() => { if (context) setOpen(true); }, [context]);
  useEffect(() => {
    if (open) panel.current?.querySelector<HTMLTextAreaElement>('textarea')?.focus();
    if (embedded) window.parent.postMessage({ type: 'ekt-widget-size', open }, '*');
  }, [open, embedded]);
  function close() { setOpen(false); launcher.current?.focus(); }
  const submit = (text: string, files: File[] = []) => send(text, files, context?.id);
  return <>
    <section ref={panel} id="ekt-chat" hidden={!open} className={standalone ? 'assistant-panel' : 'chat-widget'} role={standalone ? 'region' : 'dialog'} aria-label="EKT Assistant" onKeyDown={(e) => { if (e.key === 'Escape' && !standalone) close(); }}>
      <header className="chat-header"><span className="assistant-mark"><Sparkles size={21} /></span><div><h2>EKT Assistant</h2><span>{mode}</span></div><button className="icon-button" disabled={isLoading} title="Новый диалог" aria-label="Новый диалог" onClick={async () => { await reset(); onClearContext(); setSession((s) => s + 1); }}><Plus size={20} /></button>{!standalone && <button className="icon-button" onClick={close} title="Свернуть чат" aria-label="Свернуть чат"><X size={20} /></button>}</header>
      {context && <div className="product-context"><span>Обсуждаем товар<strong>{context.name}</strong></span><button className="icon-button" title="Убрать товар из контекста" aria-label="Убрать товар из контекста" onClick={onClearContext}><X size={16} /></button></div>}
      <MessageList messages={messages} isLoading={isLoading} onBuy={onBuy} onPrompt={(text) => { void submit(text); }} />
      <footer className="chat-footer">{error && <p className="error" role="alert">{error}</p>}<MessageComposer key={session} isLoading={isLoading} onSend={submit} /><div className="privacy-note"><ShieldCheck size={12} />Не отправляйте платёжные данные</div></footer>
    </section>
    {!standalone && <button ref={launcher} className={`chat-launcher ${open ? 'chat-launcher--open' : ''}`} title={open ? 'Свернуть чат' : 'Открыть чат с консультантом'} aria-label={open ? 'Свернуть чат' : 'Открыть чат с консультантом'} aria-expanded={open} aria-controls="ekt-chat" onClick={() => setOpen(!open)}>{open ? <X size={25} /> : <MessageCircle size={27} />}<span className="launcher-badge" aria-hidden="true">AI</span></button>}
  </>;
}
