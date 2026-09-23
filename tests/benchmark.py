"""Measure HTTP latency against the running local demo; no model inference claims."""
import json
import statistics
import time
from pathlib import Path
from uuid import uuid4
import httpx

def main():
    results=[]
    with httpx.Client(base_url='http://127.0.0.1:8765',timeout=25) as c:
        c.headers['X-CSRF-Token']=c.get('/api/session').json()['csrf']
        for query in ['Покажи 027228','Автомат 16 А','DEMO-A16','Условия доставки']:
            times=[]
            for _ in range(10):
                start=time.perf_counter()
                r=c.post('/api/chat',json={'message':query,'request_id':str(uuid4())})
                r.raise_for_status()
                times.append((time.perf_counter()-start)*1000)
            results.append({'query':query,'runs':len(times),'median_ms':round(statistics.median(times),2),'p95_ms':round(sorted(times)[-1],2)})
    report={'mode':'deterministic demo, HTTP loopback, persisted SQLite; no model calls','results':results}
    (Path(__file__).resolve().parents[1]/'docs'/'benchmark.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
