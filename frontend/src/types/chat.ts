export interface Product {
  id: number;
  name: string;
  article: string;
  price: number;
  currency?: string | null;
  backendId?: string;
  stock?: number | null;
  sourceKind?: string;
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
  proposal?: Proposal;
  review?: ReviewItem[];
  cartUrl?: string;
}
export interface Proposal { id: string; product: Product; quantity: number; expires_at: number; status: string }
export interface ReviewItem { query: string; quantity: number | null; confidence: string }
export interface ChatResponse { content: string; productIds?: number[]; proposal?: Proposal; review?: ReviewItem[]; cartUrl?: string }
export interface StockQuote { quoteId: string; productId: number; stock: number; price: number }
