import json, re, time, sys
from collections import Counter
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

PAGE='https://flyyab.ir/tours/tehran-mashhad?departing=1405-06-20&returning=1405-06-23&rooms=1&adt%5B0%5D=2'
MATCHES=['/tours/app/search','/hub/check-route','/CheapestPrice/serachCacheTokenTour/','/CheapestPrice/serachAvailTokenTour/','/hotels/app/wbRequest','/hotels/app/wbResponse/']

opt=Options(); opt.add_argument('--headless=new'); opt.add_argument('--no-sandbox'); opt.add_argument('--disable-dev-shm-usage'); opt.add_argument('--window-size=1440,1200'); opt.add_argument('--lang=fa-IR')
opt.set_capability('goog:loggingPrefs',{'performance':'ALL','browser':'ALL'})
d=webdriver.Chrome(options=opt); d.set_page_load_timeout(90)
d.execute_cdp_cmd('Network.enable', {'maxTotalBufferSize':100000000,'maxResourceBufferSize':50000000,'maxPostDataSize':5000000})

requests={}; responses={}; bodies={}

def redact_post(s):
    if not s:return s
    try:
        o=json.loads(s)
        if isinstance(o,dict):
            for k in list(o):
                if re.search(r'token|authorization',k,re.I): o[k]='***REDACTED***'
        return json.dumps(o,ensure_ascii=False,default=str)
    except:return s[:4000]

def ingest():
    for row in d.get_log('performance'):
        try:m=json.loads(row['message'])['message']; method=m['method']; p=m['params']
        except:continue
        if method=='Network.requestWillBeSent':
            req=p.get('request',{}); url=req.get('url','')
            if any(x in url for x in MATCHES):
                requests[p['requestId']]={'url':url,'method':req.get('method'),'postData':req.get('postData'),'headers':req.get('headers',{})}
        elif method=='Network.responseReceived':
            r=p.get('response',{}); url=r.get('url','')
            if any(x in url for x in MATCHES):
                rid=p['requestId']; responses[rid]={'url':url,'status':r.get('status'),'mimeType':r.get('mimeType'),'fromDiskCache':r.get('fromDiskCache'),'fromServiceWorker':r.get('fromServiceWorker')}
                try:
                    b=d.execute_cdp_cmd('Network.getResponseBody',{'requestId':rid}); bodies[rid]=b.get('body','')
                except Exception as e:
                    bodies[rid]='__BODY_ERROR__ '+repr(e)

def J(s):
    try:return json.loads(s)
    except:return None

def walk(x,p=''):
    if isinstance(x,dict):
        for k,v in x.items():yield from walk(v,f'{p}.{k}' if p else str(k))
    elif isinstance(x,list):
        for i,v in enumerate(x):yield from walk(v,f'{p}[{i}]')
    else:yield p,x

def flat(v):
    out=[]
    if isinstance(v,list):
        for z in v:
            if isinstance(z,dict):out.append(z)
            else:out+=flat(z)
    elif isinstance(v,dict):
        for z in v.values():out+=flat(z)
    return out

def find_lists(x,p=''):
    out=[]
    if isinstance(x,dict):
        for k,v in x.items():
            np=f'{p}.{k}' if p else k
            if isinstance(v,list) and v and isinstance(v[0],dict): out.append((np,v))
            if isinstance(v,(dict,list)): out+=find_lists(v,np)
    elif isinstance(x,list):
        for i,v in enumerate(x[:8]):
            if isinstance(v,(dict,list)):out+=find_lists(v,f'{p}[{i}]')
    return out

def likely_hotels(obj):
    scored=[]
    for p,ls in find_lists(obj):
        keys=set().union(*(set(x.keys()) for x in ls[:3] if isinstance(x,dict)))
        score=sum(1 for k in keys if re.search(r'hotel|star|room|price|adult|name|descriptive',k,re.I))
        if score>=2 or re.search(r'hotel|descriptive',p,re.I):scored.append((len(ls),score,p,ls))
    return max(scored,default=(0,0,'',[]),key=lambda x:(x[0],x[1]))

def fval(o,rx):
    for p,v in walk(o):
        if re.search(rx,p,re.I) and not isinstance(v,(dict,list)):return v
    return None

def flight_summary(obj):
    if not isinstance(obj,dict):return 0,0,[],[]
    ob=flat(obj.get('outbound2')); ib=flat(obj.get('return'))
    def rows(xs):
        out=[]
        for x in xs[:5]:
            out.append({'airline':fval(x,r'airline.*(name|title)|airlineName|airline$'),'depTime':fval(x,r'(departure|dep).*time|flightTime|time$'),'adultPrice':fval(x,r'adultPrice|adult.*price'),'price':fval(x,r'(^|\.)price$|totalPrice'),'flightNo':fval(x,r'flight(No|Number)|flight_number')})
        return out
    return len(ob),len(ib),rows(ob),rows(ib)

def hotel_summary(obj):
    n,score,path,hs=likely_hotels(obj)
    stars=Counter(); five=[]; samples=[]
    for h in hs:
        star=fval(h,r'(^|\.)(HotelStar|hotelStar|Star|stars?)$')
        try:si=int(float(star));stars[si]+=1
        except:si=None
        name=fval(h,r'HotelName|hotel.*name|nameFa|(^|\.)name$')
        if si==5 and name:five.append(str(name))
        if len(samples)<5:samples.append({'name':name,'star':star,'adultPrice':fval(h,r'adult.*price|price.*adult'),'total':fval(h,r'total.*price|price.*total|(^|\.)price$'),'room':fval(h,r'room.*name|name.*room')})
    return {'path':path,'count':n,'stars':dict(sorted(stars.items())),'fiveStar':five[:25],'samples':samples,'keys':list(hs[0].keys())[:120] if hs else []}

try:
    print('=== LOAD LIVE PAGE ===')
    d.get(PAGE)
    start=time.time(); stable=0; last_count=-1
    while time.time()-start<55:
        time.sleep(1); ingest()
        count=len(responses)
        if count==last_count:stable+=1
        else:stable=0;last_count=count
        body=d.find_element('tag name','body').text
        # Once wbResponse + flight avail/cache have appeared and page has hotels, allow a few stable seconds.
        urls='\n'.join(x['url'] for x in responses.values())
        if '/hotels/app/wbResponse/' in urls and '/CheapestPrice/' in urls and ('هتل' in body) and stable>=5:break
    ingest()
    body=d.find_element('tag name','body').text
    print('PAGE_TITLE',d.title)
    print('BODY_HEAD',body[:2600].replace('\n',' | '))
    m=re.search(r'نتایج کل:\s*([0-9۰-۹,]+)\s*هتل',body)
    print('DOM_TOTAL_HOTELS',m.group(1) if m else 'NOT_PARSED')
    print('CAPTURED_REQUESTS',len(requests),'RESPONSES',len(responses),'BODIES',len(bodies))

    endpoint_ok={}
    for rid,res in responses.items():
        req=requests.get(rid,{})
        url=res['url']; key=next((x for x in MATCHES if x in url),'OTHER')
        text=bodies.get(rid,''); obj=J(text)
        print('\n=== ENDPOINT',key,'===')
        print('URL',url)
        print('METHOD',req.get('method'),'HTTP',res.get('status'),'BODY_BYTES',len(text.encode('utf-8','ignore')),'JSON',isinstance(obj,(dict,list)))
        if req.get('postData'): print('REQUEST_BODY',redact_post(req.get('postData'))[:6000])
        if isinstance(obj,dict): print('TOP_KEYS',list(obj.keys())[:80],'STATUS_FIELD',obj.get('status',obj.get('Status')))
        elif isinstance(obj,list):print('TOP_LIST_LEN',len(obj))
        else: print('BODY_HEAD',text[:1200])

        if '/tours/app/search' in url:
            hs=hotel_summary(obj); print('TOUR_HOTEL_SUMMARY',json.dumps(hs,ensure_ascii=False,default=str)[:10000]); endpoint_ok['tour']=res.get('status')==200 and isinstance(obj,dict)
        elif '/hub/check-route' in url:
            tok=(obj or {}).get('token') if isinstance(obj,dict) else None; print('CHECK_ROUTE_TOKEN',('present len='+str(len(str(tok)))) if tok else 'missing'); endpoint_ok['check-route']=res.get('status')==200 and bool(tok)
        elif '/CheapestPrice/' in url:
            oc,ic,ors,irs=flight_summary(obj); print('FLIGHT_COUNTS','OUT',oc,'RET',ic); print('OUT_SAMPLES',json.dumps(ors,ensure_ascii=False,default=str)[:5000]);print('RET_SAMPLES',json.dumps(irs,ensure_ascii=False,default=str)[:5000]);
            if oc and ic:endpoint_ok['flight-data']=True
        elif '/hotels/app/wbRequest' in url:
            endpoint_ok['wbRequest']=res.get('status')==200 and isinstance(obj,(dict,list))
        elif '/hotels/app/wbResponse/' in url:
            hs=hotel_summary(obj); print('HOTEL_WS_SUMMARY',json.dumps(hs,ensure_ascii=False,default=str)[:12000]);
            if hs['count']>0:endpoint_ok['wbResponse']=True

    # DOM facts prove what the page actually consumed/displayed even if response body was served from cache and CDP body was unavailable.
    facts={
      'total120': bool(re.search(r'نتایج کل:\s*120\s*هتل',body)),
      'ata': 'آتا' in body,
      'karun': 'کارون' in body,
      'out97150000': '97,150,000' in body,
      'ret112502000': '112,502,000' in body,
      'flightTotal419304000': '419,304,000' in body,
      'package230148000': '230,148,000' in body,
      'fiveStarFilter': 'پنج ستاره' in body and '★★★★★' in body,
    }
    print('\n=== DOM_FACTS ===',json.dumps(facts,ensure_ascii=False))
    print('=== ENDPOINT_OK ===',json.dumps(endpoint_ok,ensure_ascii=False))
    required=['tour','check-route','flight-data','wbRequest','wbResponse']
    all_ok=all(endpoint_ok.get(k) for k in required) and all(facts.values())
    print('FINAL_E2E_OK',all_ok)
    if not all_ok:sys.exit(2)
finally:
    d.quit()
