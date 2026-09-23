import json
import os
import secrets
import threading
import time
from pathlib import Path
from uuid import UUID
from dotenv import load_dotenv
from fastapi import FastAPI, Request, HTTPException, UploadFile, File
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, StrictBool
from .catalog import Catalog, CatalogError, ROOT
from .cart import DemoCart, CartError
from .attachments import extract, MAX_SIZE
from agent.service import Agent, Add

load_dotenv(ROOT / '.env')

class ChatInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    message: str=Field(min_length=1,max_length=2000)
    request_id: UUID
    proposal_id: str|None=None
    context_product_id: str|None=Field(default=None,max_length=100)

class Confirm(BaseModel):
    model_config=ConfigDict(extra='forbid')
    confirm: StrictBool

def create_app(catalog=None,db_path=None,client=None):
    app=FastAPI(title='EKT Assistant',version='1.0.0')
    cat=catalog or Catalog()
    db_path=Path(db_path or os.getenv('EKT_DB_PATH',str(ROOT/'var'/'demo.sqlite3')))
    db_path.parent.mkdir(parents=True,exist_ok=True)
    cart=DemoCart(db_path,cat)
    agent=Agent(cat,cart,client)
    locks=[threading.RLock() for _ in range(128)]
    app.state.catalog,app.state.cart,app.state.agent=cat,cart,agent

    @app.middleware('http')
    async def session_middleware(request,call_next):
        # Reject oversized bodies before multipart parser can spool them to disk.
        length=request.headers.get('content-length')
        if request.method=='POST' and (length is None or not length.isdigit()):
            return JSONResponse({'detail':'Требуется Content-Length.'},status_code=411)
        if length and int(length)>MAX_SIZE+65536:
            return JSONResponse({'detail':'Максимальный размер файла 5 МБ.'},status_code=413)
        received=0
        original=request._receive
        async def bounded_receive():
            nonlocal received
            msg=await original()
            received+=len(msg.get('body',b''))
            if received>MAX_SIZE+65536: raise HTTPException(413,'Максимальный размер файла 5 МБ.')
            return msg
        request._receive=bounded_receive
        session=cart.session(request.cookies.get('ekt_session'))
        request.state.session=session
        if request.method=='POST':
            token=request.headers.get('x-csrf-token','')
            origin=request.headers.get('origin')
            if not secrets.compare_digest(token,session['csrf']) or (origin and origin!=str(request.base_url).rstrip('/')):
                return JSONResponse({'detail':'Сессия устарела. Обновите страницу.'},status_code=403)
        response=await call_next(request)
        if request.cookies.get('ekt_session')!=session['id']:
            response.set_cookie('ekt_session',session['id'],httponly=True,samesite='strict',secure=os.getenv('COOKIE_SECURE')=='1',max_age=86400)
        response.headers['X-Content-Type-Options']='nosniff'
        response.headers['Referrer-Policy']='no-referrer'
        response.headers['Content-Security-Policy']="default-src 'self'; img-src 'self' https://ekt.kz https://www.ekt.kz data:; style-src 'self'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        response.headers['Cache-Control']='no-store'
        return response

    @app.exception_handler(CartError)
    async def cart_error(request,exc): return JSONResponse({'detail':str(exc)},status_code=409)
    @app.exception_handler(CatalogError)
    async def catalog_error(request,exc): return JSONResponse({'detail':str(exc)},status_code=503)

    @app.get('/api/session')
    def get_session(request:Request): return {'csrf':request.state.session['csrf'],'mode':agent.mode,'proposal':cart.active(request.state.session['id'])}

    @app.get('/api/status')
    def status():
        return {'mode':agent.mode,'catalog_mode':'live' if cat.live else 'snapshot','coverage':cat.coverage,
                'real_products':sum(p['source']['kind']!='synthetic' for p in cat.products.values()),
                'demo_products':sum(p['source']['kind']=='synthetic' for p in cat.products.values()),
                'sellable_stores_configured':bool(cat.allowed),'cart':'local_demo'}

    @app.get('/api/products')
    def products():
        with cat.lock: return {'items':list(cat.products.values()),'coverage':cat.coverage}

    @app.get('/api/products/{product_id}')
    def product(product_id:str):
        result=cat.get(product_id,fresh=True)
        if not result: raise HTTPException(404,'Товар не найден.')
        return result

    @app.post('/api/session/reset')
    def reset(request:Request):
        sid=request.state.session['id']
        with locks[hash(sid)%len(locks)]:
            pending=cart.active(sid)
            if pending: cart.cancel(sid,pending['id'])
            cart.save_state(sid,None,[])
        return {'ok':True}

    @app.post('/api/chat')
    def chat(data:ChatInput,request:Request):
        sid=request.state.session['id']
        with locks[hash(sid)%len(locks)]:
            cached=cart.cached_reply(sid,str(data.request_id))
            if cached: return cached
            if data.context_product_id:
                p=cat.get(data.context_product_id)
                if not p: raise HTTPException(404,'Выбранный товар не найден.')
                state=cart.state(sid)
                cart.save_state(sid,p['id'],json.loads(state['history']))
            start=time.perf_counter()
            try: reply=agent.chat(sid,data.message,data.proposal_id)
            except (CartError,CatalogError): raise
            except Exception:
                raise HTTPException(502,'Модель не ответила или вернула некорректные данные. Попробуйте ещё раз; корзина не изменена.') from None
            reply['latency_ms']=round((time.perf_counter()-start)*1000,1)
            cart.cache_reply(sid,str(data.request_id),reply)
            return reply

    @app.post('/api/proposals')
    def propose(data:Add,request:Request):
        sid=request.state.session['id']
        with locks[hash(sid)%len(locks)]: return cart.propose(sid,data.product_id,data.quantity)

    @app.post('/api/proposals/{proposal_id}/confirm')
    def confirm(proposal_id:str,data:Confirm,request:Request):
        if data.confirm is not True: raise HTTPException(400,'Необходимо явное подтверждение.')
        return cart.confirm(request.state.session['id'],proposal_id)

    @app.post('/api/proposals/{proposal_id}/cancel')
    def cancel(proposal_id:str,request:Request): return cart.cancel(request.state.session['id'],proposal_id)

    @app.get('/api/cart')
    def get_cart(request:Request): return cart.get_cart(request.state.session['id'])

    @app.post('/api/upload')
    async def upload(file:UploadFile=File(...)):
        from starlette.concurrency import run_in_threadpool
        try:
            data=await file.read(MAX_SIZE+1)
            return await run_in_threadpool(extract,file.filename or '',data,agent.client,agent.model)
        except ValueError as exc: raise HTTPException(422,str(exc)) from None
        except Exception: raise HTTPException(422,'Не удалось прочитать файл. Проверьте формат и содержимое.') from None
        finally: await file.close()

    @app.get('/')
    @app.get('/cart')
    def index():
        path=ROOT/'frontend'/'dist'/'index.html'
        if not path.exists(): raise HTTPException(503,'Сначала соберите frontend: npm run build.')
        return FileResponse(path)

    @app.get('/embed.js')
    def embed(): return FileResponse(ROOT/'frontend'/'public'/'embed.js',media_type='application/javascript')

    app.mount('/assets',StaticFiles(directory=ROOT/'frontend'/'dist'/'assets',check_dir=False),name='assets')
    return app

app=create_app()
