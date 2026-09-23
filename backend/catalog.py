import hashlib
import json
import os
import re
import threading
import time
from pathlib import Path
import httpx
from .normalize import normalize, timestamp

ROOT = Path(__file__).resolve().parents[1]


class CatalogError(Exception):
    pass


class Catalog:
    def __init__(self, data_dir=None, client=None):
        self.data_dir = Path(data_dir or ROOT / 'data')
        self.allowed = [x.strip() for x in os.getenv('EKT_SELLABLE_STORE_IDS', '').split(',') if x.strip()]
        self.currency = os.getenv('EKT_CURRENCY', 'KZT').strip().upper() or 'KZT'
        self.live = os.getenv('CATALOG_MODE', 'snapshot') == 'live'
        self.client = client
        self.lock = threading.RLock()
        self.products = {}
        self.coverage = {'complete': False, 'pages': 2, 'stop_reason': 'предоставлены первые две страницы', 'fetched_at': None}
        cache = self.data_dir / 'catalog-cache.json'
        if cache.exists():
            doc = json.loads(cache.read_text(encoding='utf-8'))
            self.coverage = doc['coverage']
            for raw in doc['items']:
                self.put(raw, {'kind': 'api_snapshot', 'fetched_at': self.coverage['fetched_at']})
        else:
            for path in sorted(self.data_dir.glob('page[12].json')):
                for raw in json.loads(path.read_text(encoding='utf-8'))['items']:
                    self.put(raw, {'kind': 'user_sample', 'fetched_at': None})
            detail = self.data_dir / 'live-detail.json'
            if detail.exists():
                self.put(json.loads(detail.read_text(encoding='utf-8')), {'kind': 'api_snapshot', 'fetched_at': None})
        demo = self.data_dir / 'demo.json'
        if demo.exists():
            for raw in json.loads(demo.read_text(encoding='utf-8')):
                self.put(raw, {'kind': 'synthetic', 'fetched_at': None})

    def put(self, raw, source):
        p = normalize(raw, source, ['demo-store'] if source['kind'] == 'synthetic' else self.allowed, default_currency=self.currency)
        with self.lock:
            self.products[p['id']] = p
        return p

    def request(self, path, params):
        if self.client:
            client = self.client
        else:
            user, password = os.getenv('EKT_API_USER'), os.getenv('EKT_API_PASSWORD')
            if not user or not password:
                raise CatalogError('Не настроен серверный доступ к API каталога.')
            client = httpx.Client(base_url='https://ekt.kz', auth=(user, password), timeout=12, follow_redirects=False)
        try:
            for attempt in range(2):
                try:
                    response = client.get(path, params=params)
                    response.raise_for_status()
                    return response.json()
                except (httpx.HTTPError, ValueError):
                    if attempt: raise CatalogError('API каталога недоступен. Остаток не подтверждён.') from None
                    time.sleep(.15)
        finally:
            if not self.client: client.close()

    def get(self, product_id, fresh=False):
        with self.lock:
            product = self.products.get(str(product_id))
        if not product:
            return None
        if fresh and self.live and product['source']['kind'] != 'synthetic':
            raw = self.request('/api/products/detail', {'id': product_id})
            if not isinstance(raw, dict) or str(raw.get('id')) != str(product_id):
                raise CatalogError('API вернул некорректную карточку.')
            return self.put(raw, {'kind': 'live_api', 'fetched_at': timestamp()})
        return product

    def import_pages(self, max_pages=2, ttl=900, force=False):
        cache = self.data_dir / 'catalog-cache.json'
        if not force and cache.exists() and time.time() - cache.stat().st_mtime < ttl:
            return self.coverage
        items, seen, ids, pages = [], set(), set(), 0
        stop, complete = 'достигнут заданный лимит страниц', False
        errors = 0
        for page in range(1, max_pages + 1):
            d = self.request('/api/products', {'page': page})
            rows = d.get('items') if isinstance(d, dict) else None
            if not isinstance(rows, list): raise CatalogError('Неизвестный формат списка API.')
            if not rows:
                stop, complete = 'пустая страница', True
                break
            fingerprint = hashlib.sha256(json.dumps(sorted(str(x.get('id')) for x in rows)).encode()).hexdigest()
            if fingerprint in seen or not any(str(x.get('id')) not in ids for x in rows):
                stop = 'повторяющаяся страница'; break
            seen.add(fingerprint); pages += 1
            for raw in rows:
                if 'id' not in raw: continue
                pid = str(raw['id'])
                if pid in ids: continue
                ids.add(pid)
                try:
                    detail = self.request('/api/products/detail', {'id': pid})
                    if not isinstance(detail, dict) or str(detail.get('id')) != pid: raise CatalogError('Некорректная карточка')
                    raw = detail
                except CatalogError:
                    errors += 1
                items.append(raw)
            # count is page-local in supplied examples. Never use it as total.
        coverage = dict(complete=complete, pages=pages, stop_reason=stop, fetched_at=timestamp(), detail_errors=errors, real_products=len(items))
        doc = {'items': items, 'coverage': coverage}
        self.data_dir.mkdir(parents=True, exist_ok=True)
        tmp = cache.with_suffix('.tmp'); tmp.write_text(json.dumps(doc, ensure_ascii=False), encoding='utf-8'); tmp.replace(cache)
        with self.lock:
            self.products = {k:v for k,v in self.products.items() if v['source']['kind'] == 'synthetic'}
            for raw in items: self.put(raw, {'kind': 'api_snapshot', 'fetched_at': coverage['fetched_at']})
            self.coverage = coverage
        return coverage

    def search(self, query, limit=6):
        q = query.lower().strip()
        with self.lock: products = list(self.products.values())
        exact = [p for p in products if any(a and (a.lower() == q or re.search(r'(?<![\w-])'+re.escape(a.lower())+r'(?![\w-])', q)) for a in [p['id'], p['article'], p['supplier_article']])]
        if exact: return exact[:limit]
        filters = {}
        for key, pattern in [('current',r'(\d+(?:[.,]\d+)?)\s*[аa](?!\w)'),('poles',r'([1-4])\s*(?:полюс|p\b|ф\b)'),('voltage',r'(\d+)\s*[вv](?!\w)'),('breaking',r'(\d+)\s*(?:кa|ка|ka)(?!\w)')]:
            m = re.search(pattern, q)
            if m: filters[key] = float(m.group(1).replace(',','.'))
        stop = {'найди','покажи','нужен','нужны','мне','есть','товар','для','на','с','по','и','а','в','шт','штуки','автомат','автоматический','выключатель','полюса','полюсный'}
        tokens = [t for t in re.findall(r'[a-zа-яё0-9_-]+', q) if t not in stop and not t.isdigit() and not re.fullmatch(r'\d+[аaвvpф]',t)]
        scored = []
        for p in products:
            if filters and any(p['specs'].get(k) != v for k,v in filters.items()): continue
            hay = (p['name']+' '+p['article']+' '+str(p['brand'] or '')+' '+p['description']).lower()
            score = sum(1 for t in tokens if t in hay)
            if score or (filters and not tokens) or (not tokens and 'автомат' in q and p['category'] in {'mcb','mccb','rcbo'}): scored.append((score,p))
        return [p for _,p in sorted(scored,key=lambda x:(-x[0],x[1]['id']))[:limit]]

    def terms(self):
        path = self.data_dir / 'terms.json'
        if path.exists():
            d = json.loads(path.read_text(encoding='utf-8'))
            if d.get('verified') is True and d.get('source') and d.get('verified_at'): return d
        return {'error':'Подтверждённые условия оплаты, доставки и минимальной партии не предоставлены. Уточните у менеджера ekt.kz. KRATNOST_MIN не интерпретируется.'}
