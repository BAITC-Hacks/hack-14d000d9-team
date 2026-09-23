import { useEffect, useRef, useState } from 'react';
import { sendChatMessage } from '../services/chatApi';
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
        id: crypto.randomUUID(), role: 'assistant', content: response.content, productIds: response.productIds,
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

  function reset() {
    pending.current?.abort();
    pending.current = null;
    setMessages([]);
    setError(null);
    setIsLoading(false);
  }

  return { messages, isLoading, error, send, reset };
}
