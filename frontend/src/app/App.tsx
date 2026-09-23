import { ChatPage } from '../pages/ChatPage';
import { CartPage } from '../pages/CartPage';
export function App() { return window.location.pathname === '/cart' ? <CartPage /> : <ChatPage />; }
