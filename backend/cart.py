"""SQLite demo-cart adapter. Transactions serialize concurrent confirmations across workers."""
import hashlib
import json
import secrets
import sqlite3
import time
from contextlib import contextmanager


class CartError(Exception):
    pass


def fingerprint(p):
    material = {k:p[k] for k in ['id','name','price','currency','stock','quantity','stores','specs','conflicts']}
    return hashlib.sha256(json.dumps(material, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


class DemoCart:
    def __init__(self, path, catalog):
        self.path, self.catalog = str(path), catalog
        with self.connection() as db:
            db.executescript('''
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS sessions(id TEXT PRIMARY KEY, csrf TEXT, selected TEXT, history TEXT DEFAULT '[]', expires REAL);
            CREATE TABLE IF NOT EXISTS proposals(id TEXT PRIMARY KEY, session TEXT, product TEXT, qty INTEGER, fingerprint TEXT, snapshot TEXT, expires REAL, status TEXT);
            CREATE TABLE IF NOT EXISTS cart(session TEXT, product TEXT, qty INTEGER, snapshot TEXT, PRIMARY KEY(session,product));
            CREATE TABLE IF NOT EXISTS requests(session TEXT, id TEXT, reply TEXT, PRIMARY KEY(session,id));
            ''')

    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.path, timeout=35)
        db.row_factory = sqlite3.Row
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback(); raise
        finally: db.close()

    def session(self, sid=None):
        with self.connection() as db:
            row = db.execute('SELECT * FROM sessions WHERE id=? AND expires>?',(sid,time.time())).fetchone() if sid else None
            if not row:
                sid, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
                db.execute('INSERT INTO sessions(id,csrf,expires) VALUES(?,?,?)',(sid,csrf,time.time()+86400))
                row = db.execute('SELECT * FROM sessions WHERE id=?',(sid,)).fetchone()
            return dict(row)

    def state(self,sid):
        with self.connection() as db: return dict(db.execute('SELECT * FROM sessions WHERE id=?',(sid,)).fetchone())

    def save_state(self,sid,selected,history):
        with self.connection() as db: db.execute('UPDATE sessions SET selected=?,history=? WHERE id=?',(selected,json.dumps(history[-10:],ensure_ascii=False),sid))

    def cached_reply(self,sid,rid):
        with self.connection() as db:
            row=db.execute('SELECT reply FROM requests WHERE session=? AND id=?',(sid,rid)).fetchone()
            return json.loads(row[0]) if row else None

    def cache_reply(self,sid,rid,reply):
        with self.connection() as db: db.execute('INSERT OR IGNORE INTO requests VALUES(?,?,?)',(sid,rid,json.dumps(reply,ensure_ascii=False)))

    def active(self,sid):
        with self.connection() as db:
            r=db.execute("SELECT * FROM proposals WHERE session=? AND status='pending' ORDER BY expires DESC LIMIT 1",(sid,)).fetchone()
            return self.view(r) if r else None

    def view(self,row):
        return dict(id=row['id'],quantity=row['qty'],product=json.loads(row['snapshot']),expires_at=row['expires'],status=row['status'])

    def propose(self,sid,pid,qty):
        if type(qty) is not int or not 1<=qty<=10000: raise CartError('Количество должно быть целым числом от 1 до 10 000.')
        p=self.catalog.get(pid,fresh=True)
        if not p: raise CartError('Товар не найден.')
        if p['source']['kind']!='synthetic' and not self.catalog.live:
            raise CartError('Это сохранённая карточка. Для добавления реального товара включите live API и подтвердите список торговых складов. Для проверки корзины доступен DEMO-B16.')
        if p['stock'] is None: raise CartError('Доступный для продажи остаток неизвестен: требуется подтверждённый список складов.')
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT qty FROM cart WHERE session=? AND product=?',(sid,pid)).fetchone()
            if (row['qty'] if row else 0)+qty>p['stock']: raise CartError('Доступного остатка недостаточно с учётом корзины.')
            db.execute("UPDATE proposals SET status='superseded' WHERE session=? AND status='pending'",(sid,))
            proposal=secrets.token_urlsafe(24)
            db.execute('INSERT INTO proposals VALUES(?,?,?,?,?,?,?,?)',(proposal,sid,pid,qty,fingerprint(p),json.dumps(p,ensure_ascii=False),time.time()+300,'pending'))
            return self.view(db.execute('SELECT * FROM proposals WHERE id=?',(proposal,)).fetchone())

    def cancel(self,sid,pid):
        with self.connection() as db:
            db.execute("UPDATE proposals SET status='cancelled' WHERE id=? AND session=? AND status='pending'",(pid,sid))
        return {'answer':'Предложение отменено. Корзина не изменена.'}

    def confirm(self,sid,proposal_id):
        # BEGIN IMMEDIATE + one-time state + cart upsert is the mutation boundary.
        # Remote GET happens within the transaction, so concurrent cart changes cannot race.
        error=None
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT * FROM proposals WHERE id=? AND session=?',(proposal_id,sid)).fetchone()
            if not row: raise CartError('Предложение не найдено в вашей сессии.')
            if row['status']=='confirmed': return {'answer':'Это добавление уже выполнено.', 'cart_url':'/cart','already_confirmed':True}
            if row['status']!='pending': raise CartError('Предложение отменено или заменено. Создайте новое.')
            if row['expires']<time.time():
                error='Время подтверждения истекло. Создайте новое предложение.'
            else:
                p=self.catalog.get(row['product'],fresh=True)
                previous=db.execute('SELECT qty FROM cart WHERE session=? AND product=?',(sid,row['product'])).fetchone()
                total=(previous['qty'] if previous else 0)+row['qty']
                if not p or p['stock'] is None or total>p['stock']: error='Остаток изменился или недоступен. Создайте новое предложение.'
                elif fingerprint(p)!=row['fingerprint']: error='Цена, характеристики или остатки изменились. Проверьте товар и подтвердите новое предложение.'
                elif p['source']['kind']!='synthetic' and not self.catalog.live: error='Для реального товара необходима повторная проверка через live API.'
                else:
                    db.execute('INSERT INTO cart VALUES(?,?,?,?) ON CONFLICT(session,product) DO UPDATE SET qty=excluded.qty,snapshot=excluded.snapshot',(sid,row['product'],total,json.dumps(p,ensure_ascii=False)))
            db.execute('UPDATE proposals SET status=? WHERE id=?',('invalid' if error else 'confirmed',proposal_id))
        if error: raise CartError(error)
        return {'answer':f"Добавлено {row['qty']} шт. в демонстрационную корзину. Товар не зарезервирован на ekt.kz.",'cart_url':'/cart','already_confirmed':False}

    def get_cart(self,sid):
        with self.connection() as db:
            rows=db.execute('SELECT * FROM cart WHERE session=?',(sid,)).fetchall()
        items=[{'product':json.loads(r['snapshot']),'quantity':r['qty']} for r in rows]
        currencies={x['product']['currency'] for x in items}
        total=sum(x['product']['price']*x['quantity'] for x in items) if items and len(currencies)==1 and None not in currencies and all(x['product']['price'] is not None for x in items) else None
        return {'items':items,'total':total,'currency':next(iter(currencies)) if len(currencies)==1 else None,'demo':True,'cart_url':'/cart'}
