export interface Product {
  id: number;
  name: string;
  article: string;
  price: number;
  image: string | null;
  url: string;
  url_api_detail: string;
  description?: string;
  quantity?: number;
  stores?: { id: number; name: string; quantity: number }[];
  properties?: Record<string, string | string[]>;
  dataWarning?: string;
}
export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  attachments?: { name: string; size: number }[];
  productIds?: number[];
}
export interface ChatResponse { content: string; productIds?: number[] }
export interface StockQuote { quoteId: string; productId: number; stock: number; price: number }
