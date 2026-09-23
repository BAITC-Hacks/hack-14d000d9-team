from pathlib import Path
from uuid import uuid4
from fastapi.testclient import TestClient
from backend.server import create_app
from backend.catalog import Catalog, ROOT

def test_catalog_context_reset_and_frontend_routes(tmp_path,monkeypatch):
    monkeypatch.setenv('AGENT_MODE','demo')
    app=create_app(Catalog(),tmp_path/'integration.sqlite')
    with TestClient(app) as client:
        client.headers['X-CSRF-Token']=client.get('/api/session').json()['csrf']
        products=client.get('/api/products').json()['items']
        assert len(products)==43
        assert next(p for p in products if p['id']=='515291')['conflicts']
        response=client.post('/api/chat',json={'message':'Какие характеристики у него?','context_product_id':'515291','request_id':str(uuid4())})
        assert response.status_code==200
        assert response.json()['products'][0]['id']=='515291'
        proposal=client.post('/api/proposals',json={'product_id':'demo-2','quantity':1}).json()
        assert client.post('/api/session/reset',json={}).status_code==200
        assert client.post('/api/proposals/'+proposal['id']+'/confirm',json={'confirm':True}).status_code==409
        assert app.state.cart.state(client.cookies['ekt_session'])['selected'] is None
        assert client.get('/').status_code==200
        assert client.get('/cart').status_code==200
        asset=next((ROOT/'frontend/dist/assets').glob('*.js'))
        assert client.get('/assets/'+asset.name).status_code==200
        assert client.get('/.env').status_code==404

def test_same_origin_mutation_and_foreign_origin_block(tmp_path,monkeypatch):
    monkeypatch.setenv('AGENT_MODE','demo')
    with TestClient(create_app(Catalog(),tmp_path/'csrf.sqlite')) as client:
        client.headers['X-CSRF-Token']=client.get('/api/session').json()['csrf']
        body={'product_id':'demo-2','quantity':1}
        assert client.post('/api/proposals',json=body,headers={'Origin':'http://testserver'}).status_code==200
        assert client.post('/api/proposals',json=body,headers={'Origin':'https://foreign.invalid'}).status_code==403
