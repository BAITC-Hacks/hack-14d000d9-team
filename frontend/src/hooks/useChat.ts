import { resetChat } from '../services/backendApi';
import { useEffect, useRef, useState } from 'react';
import { apiEnabled, sendChatMessage } from '../services/chatApi';
import type { Message } from '../types/chat';

export function useChat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const pending = useRef<AbortController | null>(null);

  useEffect(() => () => pending.current?.abort(), []);

  async function send(content: string, files: File[] = [], contextProductId?: number): Promise<boolean> {
    const text = content.trim();
    if ((!text && !files.length) || pending.current) return false;

    const controller = new AbortController();
    pending.current = controller;
    const next: Message[] = [...messages, {
      id: crypto.randomUUID(), role: 'user', content: text,
      attachments: files.map(({ name, size }) => ({ name, size })),
    }];
    setMessages(next);
    setError(null);
    setIsLoading(true);

    try {
      const response = await sendChatMessage(next, controller.signal, files, contextProductId);
      if (controller.signal.aborted) return false;
      setMessages([...next, {
        id: crypto.randomUUID(), role: 'assistant', content: response.content, productIds: response.productIds, proposal: response.proposal, review: response.review, cartUrl: response.cartUrl,
      }]);
      return true;
    } catch (cause) {
      if (!controller.signal.aborted) {
        setMessages(messages);
        setError(cause instanceof Error ? cause.message : 'Не удалось отправить сообщение.');
      }
      return false;
    } finally {
      if (pending.current === controller) {
        pending.current = null;
        setIsLoading(false);
      }
    }
  }

  async function reset() {
    if (pending.current) return;
    setIsLoading(true);
    try { if(apiEnabled) await resetChat(); }
    catch(cause) { setError(cause instanceof Error ? cause.message : 'Не удалось сбросить диалог.'); setIsLoading(false); return; }
    pending.current = null;
    setMessages([]);
    setError(null);
    setIsLoading(false);
  }

  return { messages, isLoading, error, send, reset };
}
