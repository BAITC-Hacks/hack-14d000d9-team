import assert from 'node:assert/strict';
import { createServer } from 'vite';

const originalFetch = globalThis.fetch;
const servers = [];
async function load(mode) {
  const server = await createServer({ configFile: false, server: { middlewareMode: true, hmr: { port: 0 } }, appType: 'custom', optimizeDeps: {noDiscovery: true, include: []}, configLoader: 'runner', define: { 'import.meta.env.VITE_CHAT_MODE': JSON.stringify(mode) } });
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
  assert.match(compare.content, /1.?000/);
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
  assert.match(budget.content, /Бюджет: до 30.?000/);
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

  console.log('PASS: catalogue lookup, text attachment, unsupported-format disclosure, unknown stock');
  await servers.pop().close();

  const api = await load('api');
  const bridge = await servers.at(-1).ssrLoadModule('/src/services/backendApi.ts');
  const item = {id:'demo-2',name:'DEMO-B16',article:'DEMO-B16',price:1700,currency:'DEMO',quantity:5,stock:5,image:null,url:null,description:'Synthetic',stores:[],source:{kind:'synthetic'},conflicts:[],raw:{}};
  const proposal={id:'bound-id',product:item,quantity:2,expires_at:Date.now()/1000+300,status:'pending'};
  const requests=[];
  globalThis.fetch = async (url, options={}) => {
    requests.push({url,options});
    if(url==='/api/session')return Response.json({csrf:'test-csrf',proposal:null});
    if(options.method==='POST')assert.equal(options.headers['X-CSRF-Token'],'test-csrf');
    if(url==='/api/products')return Response.json({items:[item]});
    if(url==='/api/status')return Response.json({mode:'ai',real_products:0,demo_products:1,catalog_mode:'snapshot'});
    if(url==='/api/chat'){
      const body=JSON.parse(options.body);assert.equal(body.message,'RM17UAS16');assert.equal(body.request_id,'test');
      return Response.json({answer:'Found',products:[item],analogs:[],proposal});
    }
    if(url==='/api/upload'){
      assert.ok(options.body instanceof FormData);
      return Response.json({items:[{query:'DEMO-B16',quantity:2,confidence:'review'}],warning:'Review required'});
    }
    if(url==='/api/proposals')return Response.json(proposal);
    if(url==='/api/proposals/bound-id/confirm'){
      assert.deepEqual(JSON.parse(options.body),{confirm:true});return Response.json({cart_url:'/cart'});
    }
    if(url==='/api/proposals/bound-id/cancel'||url==='/api/session/reset')return Response.json({ok:true});
    throw new Error('Unexpected route '+url);
  };
  await bridge.loadCatalog();
  const reply=await api.sendChatMessage(messages,signal);
  assert.deepEqual(reply.productIds,[-2]);assert.equal(reply.proposal.quantity,2);
  assert.equal(requests.filter(r=>r.url.endsWith('/confirm')).length,0);
  const before=requests.filter(r=>r.url==='/api/chat').length;
  const upload=await api.sendChatMessage(messages,signal,[new File(['x'],'list.xlsx')]);
  assert.equal(upload.review[0].quantity,2);
  assert.equal(requests.filter(r=>r.url==='/api/chat').length,before,'Upload cannot execute simultaneous cart text');
  const p=await bridge.propose(-2,2,signal);assert.equal(p.id,'bound-id');
  assert.equal(requests.filter(r=>r.url.endsWith('/confirm')).length,0);
  assert.equal(await bridge.confirmProposal(p.id),'/cart');
  await bridge.cancelProposal(p.id);await bridge.resetChat();
  globalThis.fetch=async()=>Response.json({cart_url:'javascript:alert(1)'});
  await assert.rejects(bridge.confirmProposal(p.id),/Некорректная ссылка/);
  console.log('PASS: session/CSRF, normalized products, JSON chat, draft upload, separate proposal and confirmation, cancellation, reset, unsafe URL rejection');
} finally {
  globalThis.fetch = originalFetch;
  for (const server of servers) await server.close();
}
