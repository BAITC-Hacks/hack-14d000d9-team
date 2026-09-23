import assert from 'node:assert/strict';
import { createServer } from 'vite';

const originalFetch = globalThis.fetch;
const servers = [];
async function load(mode) {
  const server = await createServer({ server: { middlewareMode: true, hmr: { port: 0 } }, appType: 'custom', define: { 'import.meta.env.VITE_CHAT_MODE': JSON.stringify(mode) } });
  servers.push(server);
  return server.ssrLoadModule('/src/services/chatApi.ts');
}
const signal = new AbortController().signal;
const messages = [{ id: 'test', role: 'user', content: 'RM17UAS16' }];
try {
  const demo = await load('demo');
  const answer = await demo.sendChatMessage(messages, signal);
  assert.deepEqual(answer.productIds, [35819]);
  const compare = await demo.sendChatMessage([{ ...messages[0], content: 'Что дешевле, 027228 или 027230?' }], signal);
  assert.deepEqual(compare.productIds, [515291, 515288]);
  assert.match(compare.content, /1.?000 ₸/);
  assert.match(compare.content, /160 А/);
  assert.match(compare.content, /250 А/);
  const choose = await demo.sendChatMessage([
    { ...messages[0], content: '027228 или 027230' },
    { id: 'comparison', role: 'assistant', ...compare },
    { id: 'choice', role: 'user', content: 'А какой из них лучше?' },
  ], signal);
  assert.deepEqual(choose.productIds, [515291, 515288]);
  assert.match(choose.content, /Для какой задачи/);
  const budget = await demo.sendChatMessage([{ ...messages[0], content: 'Посоветуй недорогой автомат до 30 тысяч' }], signal);
  assert.ok(budget.productIds.length > 0);
  assert.match(budget.content, /Бюджет: до 30.?000 ₸/);
  const clarify = await demo.sendChatMessage([{ ...messages[0], content: 'Какой лучше?' }], signal);
  assert.match(clarify.content, /Что сравнить/);
  assert.equal(clarify.productIds, undefined);
  const unknown = await demo.sendChatMessage([{ ...messages[0], content: 'Сравни товары 999999 и 888888' }], signal);
  assert.equal(unknown.productIds, undefined);
  console.log('PASS: natural comparison prompts, manufacturer identifiers, contextual follow-up, budget, clarification');
  const detailed = await demo.sendChatMessage([{ ...messages[0], content: 'Характеристики 027228' }], signal);
  assert.deepEqual(detailed.productIds, [515291]);
  assert.match(detailed.content, /общий остаток 23 шт/);
  assert.match(detailed.content, /Алматы: 5 шт/);
  assert.match(detailed.content, /Нур-Султан: 8 шт/);
  assert.match(detailed.content, /160 А/);
  assert.match(detailed.content, /250 А/);
  assert.match(detailed.content, /Сертификат не предоставлен/);
  const followup = await demo.sendChatMessage([
    { ...messages[0], content: '027228' },
    { id: 'reply', role: 'assistant', ...detailed },
    { id: 'followup', role: 'user', content: 'Сколько на складе в Алматы?' },
  ], signal);
  assert.deepEqual(followup.productIds, [515291]);
  const { products } = await servers[0].ssrLoadModule('/src/services/catalog.ts');
  const product = products.find((item) => item.id === 515291);
  assert.equal(product.stores.reduce((sum, store) => sum + store.quantity, 0), product.quantity);
  console.log('PASS: detailed product, warehouse totals, conflicting current ratings, follow-up context');
  const fileAnswer = await demo.sendChatMessage([{ ...messages[0], content: '' }], signal, [new File(['RM17UAS16'], 'spec.csv')]);
  assert.deepEqual(fileAnswer.productIds, [35819]);
  const unsupported = await demo.sendChatMessage([{ ...messages[0], content: '' }], signal, [new File(['binary'], 'spec.pdf')]);
  assert.match(unsupported.content, /не анализировалось/);
  await assert.rejects(demo.getStockQuote(35819, signal), /Остатки не переданы/);
  console.log('PASS: catalogue lookup, text attachment, unsupported-format disclosure, unknown stock');
  await servers.pop().close();

  const api = await load('api');
  let calls = 0;
  globalThis.fetch = async (url, options) => {
    calls++;
    assert.equal(url, '/api/chat');
    assert.ok(options.body instanceof FormData);
    assert.equal(await options.body.get('files').text(), 'RM17UAS16');
    assert.equal(JSON.parse(options.body.get('messages'))[0].content, 'RM17UAS16');
    return Response.json({ content: 'Found', productIds: [35819, 999999] });
  };
  const remote = await api.sendChatMessage(messages, signal, [new File(['RM17UAS16'], 'spec.anything')]);
  assert.deepEqual(remote.productIds, [35819]);
  assert.equal(calls, 1);
  const quote = { quoteId: 'test-quote', productId: 35819, stock: 3, price: 49490 };
  globalThis.fetch = async () => { calls++; return Response.json(quote); };
  assert.deepEqual(await api.getStockQuote(35819, signal), quote);
  const before = calls;
  for (const quantity of [0, -1, 1.5, 4, NaN]) await assert.rejects(api.confirmCart(quote, quantity, 'test-key', signal));
  assert.equal(calls, before, 'Invalid quantities must not issue cart requests');
  globalThis.window = { location: { origin: 'http://localhost:5173' } };
  globalThis.fetch = async (url, options) => {
    assert.equal(url, '/api/cart/items');
    assert.equal(options.headers['Idempotency-Key'], 'test-key');
    assert.deepEqual(JSON.parse(options.body), { productId: 35819, quoteId: 'test-quote', quantity: 2, confirmed: true });
    return Response.json({ cartUrl: 'https://ekt.kz/cart/' });
  };
  assert.equal(await api.confirmCart(quote, 2, 'test-key', signal), 'https://ekt.kz/cart/');
  globalThis.fetch = async () => Response.json({ cartUrl: 'javascript:alert(1)' });
  await assert.rejects(api.confirmCart(quote, 2, 'test-key', signal), /Некорректная ссылка/);
  globalThis.fetch = async () => Response.json({ ...quote, stock: -1 });
  await assert.rejects(api.getStockQuote(35819, signal), /подтвердить/);
  console.log('PASS: multipart upload, response filtering, stock validation, quantity limits, explicit cart payload, unsafe URL rejection');
} finally {
  globalThis.fetch = originalFetch;
  delete globalThis.window;
  for (const server of servers) await server.close();
}
