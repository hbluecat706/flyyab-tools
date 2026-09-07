import json, re, sys, time
from collections import Counter
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

PAGE='https://flyyab.ir/tours/tehran-mashhad?departing=1405-06-20&returning=1405-06-23&rooms=1&adt%5B0%5D=2'

opt=Options()
opt.add_argument('--headless=new')
opt.add_argument('--no-sandbox')
opt.add_argument('--disable-dev-shm-usage')
opt.add_argument('--window-size=1440,1200')
opt.add_argument('--lang=fa-IR')
opt.set_capability('goog:loggingPrefs', {'browser':'ALL'})
d=webdriver.Chrome(options=opt)
d.set_page_load_timeout(90)
d.set_script_timeout(90)

def mask(s):
    s=str(s or '')
    return s[:6]+'...'+s[-4:] if len(s)>12 else ('***' if s else '')

def fjson(url, method='GET', body=None, headers=None):
    script='''
    const [url, method, body, headers, done] = arguments;
    const opts={method:method,headers:headers||{}};
    if (body !== null) opts.body=JSON.stringify(body);
    fetch(url,opts).then(async r=>done({ok:r.ok,status:r.status,url:r.url,text:await r.text()}))
                   .catch(e=>done({ok:false,status:0,error:String(e),text:''}));
    '''
    h={'Accept':'application/json,text/plain,*/*'}
    if body is not None: h['Content-Type']='application/json'
    if headers: h.update(headers)
    res=d.execute_async_script(script,url,method,body,h)
    txt=res.get('text','')
    try: obj=json.loads(txt)
    except Exception: obj=None
    return res,obj

def status_of(x):
    return x.get('status',x.get('Status')) if isinstance(x,dict) else None

def walk(x,p=''):
    if isinstance(x,dict):
        for k,v in x.items(): yield from walk(v,f'{p}.{k}' if p else k)
    elif isinstance(x,list):
        for i,v in enumerate(x): yield from walk(v,f'{p}[{i}]')
    else: yield p,x

def find_cities(x, needle, country=None, out=None):
    if out is None: out=[]
    if isinstance(x,dict):
        c=x.get('countryID',x.get('CountryID',country))
        aps=x.get('airports',x.get('Airports',[])) or []
        text=(' '.join(str(x.get(k,'')) for k in ['cityFa','CityFa','cityEn','CityEn','nameFa','nameEn'])).lower()
        iatas=[str(a.get('iata',a.get('Iata',''))).lower() for a in aps if isinstance(a,dict)]
        if x.get('cityID',x.get('CityID')) is not None and (needle.lower() in text or needle.lower() in iatas):
            out.append((x,c))
        for v in x.values(): find_cities(v,needle,c,out)
    elif isinstance(x,list):
        for v in x: find_cities(v,needle,country,out)
    return out

def all_dicts(x):
    out=[]
    if isinstance(x,dict):
        out.append(x)
        for v in x.values(): out += all_dicts(v)
    elif isinstance(x,list):
        for v in x: out += all_dicts(v)
    return out

def flight_records(obj):
    if not isinstance(obj,dict): return [],[]
    def flat(v):
        out=[]
        if isinstance(v,list):
            for z in v:
                if isinstance(z,dict): out.append(z)
                else: out+=flat(z)
        elif isinstance(v,dict):
            for z in v.values(): out+=flat(z)
        return out
    return flat(obj.get('outbound2')), flat(obj.get('return'))

def hotel_records(obj):
    cands=[]
    def rec(x,p=''):
        if isinstance(x,dict):
            for k,v in x.items():
                np=f'{p}.{k}' if p else k
                if isinstance(v,list) and v and isinstance(v[0],dict):
                    score=sum(1 for kk in v[0].keys() if re.search(r'hotel|star|room|price|adult|name',kk,re.I))
                    if score>=2 or re.search(r'hotel|descriptive',np,re.I): cands.append((np,v,score))
                if isinstance(v,(dict,list)): rec(v,np)
        elif isinstance(x,list):
            for i,v in enumerate(x[:10]):
                if isinstance(v,(dict,list)): rec(v,f'{p}[{i}]')
    rec(obj)
    return max(cands,key=lambda z:(len(z[1]),z[2]),default=('',[],0))

def compact_fields(obj, rx, n=80):
    return [(p,v) for p,v in walk(obj) if re.search(rx,p,re.I)][:n]

try:
    print('=== BROWSER PAGE ===')
    d.get(PAGE)
    for _ in range(30):
        if d.execute_script('return document.readyState')=='complete': break
        time.sleep(1)
    time.sleep(8)
    print('TITLE',d.title)
    print('URL',d.current_url)
    print('BODY_TEXT_HEAD',d.find_element('tag name','body').text[:1800].replace('\n',' | '))
    resources=d.execute_script("return performance.getEntriesByType('resource').map(x=>x.name).filter(x=>x.includes('/_booking/')||x.includes('/_bookingplus/'))")
    print('RESOURCE_API_COUNT',len(resources))
    for u in resources[:80]: print('RESOURCE_API',u)

    ls=d.execute_script("let o={}; for(let i=0;i<localStorage.length;i++){let k=localStorage.key(i); if(/version|airport|token|^st$/i.test(k))o[k]=localStorage.getItem(k)} return o")
    st=d.execute_script("return localStorage.getItem('st')||''")
    print('LOCAL_STORAGE_KEYS',list(ls.keys()))
    print('ST_LEN',len(st),'ST_MASK',mask(st))
    if not st:
        r,t=fjson('/_booking/home/token/getVersion','POST',{'token':'','lang':'fa','hasTrain':False,'clientVer':''})
        st=(t or {}).get('token','')
        if st: d.execute_script("localStorage.setItem('st',arguments[0])",st)
        print('TOKEN_BOOTSTRAP_HTTP',r.get('status'),'TOKEN_LEN',len(st))
    if not st: sys.exit('NO_ST')

    print('\n=== AIRPORT DATA IN BROWSER CONTEXT ===')
    versions=['']
    for k,v in ls.items():
        if 'version' in k.lower() and v not in versions: versions.append(v)
    airport=None
    for ver in versions[:8]:
        r,a=fjson('/_booking/home/airportWithCountry','POST',{'version':ver})
        print('AIRPORT_HTTP',r.get('status'),'VERSION_KEY',repr(ver)[:80],'BYTES',len(r.get('text','')),'STATUS',status_of(a))
        if isinstance(a,(dict,list)):
            th=find_cities(a,'tehran') or find_cities(a,'تهران') or find_cities(a,'thr')
            mh=find_cities(a,'mashhad') or find_cities(a,'مشهد') or find_cities(a,'mhd')
            if th and mh:
                airport=a;break
    if airport is None:
        # Sometimes current page already made airport request; retry after a short browser idle.
        time.sleep(3)
        r,airport=fjson('/_booking/home/airportWithCountry','POST',{'version':''})
        print('AIRPORT_RETRY_HTTP',r.get('status'),'BYTES',len(r.get('text','')))
    th=find_cities(airport,'tehran') or find_cities(airport,'تهران') or find_cities(airport,'thr')
    mh=find_cities(airport,'mashhad') or find_cities(airport,'مشهد') or find_cities(airport,'mhd')
    print('CITY_MATCHES',len(th),len(mh))
    if not th or not mh:
        print('AIRPORT_TOP',json.dumps(airport,ensure_ascii=False,default=str)[:6000]);sys.exit('CITY_LOOKUP_FAILED')
    te,tc=th[0]; ma,mc=mh[0]
    print('TEHRAN',json.dumps(te,ensure_ascii=False,default=str)[:2800],'COUNTRY',tc)
    print('MASHHAD',json.dumps(ma,ensure_ascii=False,default=str)[:2800],'COUNTRY',mc)
    teaps=te.get('airports',te.get('Airports',[])) or []; maaps=ma.get('airports',ma.get('Airports',[])) or []
    te_iatas=[str(x.get('iata',x.get('Iata',''))) for x in teaps if isinstance(x,dict)]
    ma_iatas=[str(x.get('iata',x.get('Iata',''))) for x in maaps if isinstance(x,dict)]
    dep='THR' if 'THR' in te_iatas else (te_iatas[0] if te_iatas else 'THR')
    arr='MHD' if 'MHD' in ma_iatas else (ma_iatas[0] if ma_iatas else 'MHD')
    cityid=ma.get('cityID',ma.get('CityID')); safarid=ma.get('safarID',ma.get('SafarID'))
    cid=f'{cityid}_{safarid}_{mc}'
    print('ROUTE_SELECTED',dep,'->',arr,'TEHRAN_IATAS',te_iatas,'MASHHAD_IATAS',ma_iatas,'DEST_ID',cid)

    p={'activeTab':'TOUR-D','tourType':1,'tourFromCityIata':dep,'tourToCityIata':arr,'dateIn':'1405-06-20','dateOut':'1405-06-23','cabinType':'Economy','mixMode':'flight','cityID':cid,'selectedTourItm':None,'tourCode':None,'selectedTourDate':None,'roomNum':1,
       'room-1-ad-num':2,'room-1-child-numbers':0,'child-age-1-1':0,'child-age-1-2':0,'child-age-1-3':0,
       'room-2-ad-num':0,'room-2-child-numbers':0,'child-age-2-1':0,'child-age-2-2':0,'child-age-2-3':0,
       'room-3-ad-num':0,'room-3-child-numbers':0,'child-age-3-1':0,'child-age-3-2':0,'child-age-3-3':0,
       'token':st,'adt':2,'chd':0,'inf':0}

    print('\n=== TOUR SEARCH ===')
    r,tour=fjson('/_booking/tours/app/search','POST',p)
    hp,hotels,_=hotel_records(tour)
    print('TOUR_HTTP',r.get('status'),'STATUS',status_of(tour),'BYTES',len(r.get('text','')),'KEYS',list(tour.keys())[:50] if isinstance(tour,dict) else None,'HOTEL_PATH',hp,'HOTEL_COUNT',len(hotels))
    if hotels:
        print('TOUR_HOTEL_KEYS',list(hotels[0].keys())[:100])
        print('TOUR_HOTEL_FIELDS',json.dumps(compact_fields(hotels[0],r'hotel|name|star|price|adult|total|room',120),ensure_ascii=False,default=str)[:9000])
    else: print('TOUR_BODY',r.get('text','')[:4000])

    print('\n=== FLIGHTS ===')
    fb={'departure':dep,'arrival':arr,'date':'1405-06-20','adult':2,'child':0,'infant':0,'retDate':'1405-06-23','hasReturnAirline':False}
    r,fj=fjson('/_bookingplus/public/api/hub/check-route','POST',fb)
    ft=(fj or {}).get('token') if isinstance(fj,dict) else None
    print('FLIGHT_TOKEN_HTTP',r.get('status'),'STATUS',status_of(fj),'HAS_TOKEN',bool(ft),'BODY',json.dumps(fj,ensure_ascii=False,default=str)[:1800] if fj else r.get('text','')[:1800])
    flight=None; ob=[]; ib=[]
    if ft:
        for endpoint,maxtry in [('serachCacheTokenTour',1),('serachAvailTokenTour',10)]:
            for n in range(maxtry):
                r,fo=fjson('/_booking/CheapestPrice/'+endpoint+'/'+str(ft),'GET',None,{'authorization':st})
                ob,ib=flight_records(fo)
                print('FLIGHT_POLL',endpoint,n+1,'HTTP',r.get('status'),'STATUS',status_of(fo),'OUT',len(ob),'RET',len(ib),'BYTES',len(r.get('text','')))
                if ob and ib:
                    flight=fo;break
                if endpoint=='serachAvailTokenTour' and n<maxtry-1: time.sleep(2)
            if flight:break
    if flight:
        print('OUT_FIRST_KEYS',list(ob[0].keys())[:120]);print('RET_FIRST_KEYS',list(ib[0].keys())[:120])
        print('OUT_FIRST_FIELDS',json.dumps(compact_fields(ob[0],r'airline|time|price|adult|flight|iata|departure|arrival',150),ensure_ascii=False,default=str)[:10000])
        print('RET_FIRST_FIELDS',json.dumps(compact_fields(ib[0],r'airline|time|price|adult|flight|iata|departure|arrival',150),ensure_ascii=False,default=str)[:10000])

    print('\n=== HOTEL WEBSERVICE ===')
    r,w=fjson('/_booking/hotels/app/wbRequest','POST',p)
    print('HOTEL_REQUEST_HTTP',r.get('status'),'STATUS',status_of(w),'BYTES',len(r.get('text','')),'BODY',json.dumps(w,ensure_ascii=False,default=str)[:1600] if w is not None else r.get('text','')[:1600])
    best=[]; bestp=''; last=None
    for n in range(10):
        r,hj=fjson('/_booking/hotels/app/wbResponse/','POST',p); last=hj
        pp,items,_=hotel_records(hj)
        if len(items)>len(best): best=items;bestp=pp
        print('HOTEL_POLL',n+1,'HTTP',r.get('status'),'STATUS',status_of(hj),'COUNT',len(items),'PATH',pp,'BYTES',len(r.get('text','')))
        if items and str(status_of(hj)).lower()=='success': break
        if n<9: time.sleep(2)
    if best:
        print('HOTEL_COUNT',len(best),'PATH',bestp,'FIRST_KEYS',list(best[0].keys())[:120])
        print('HOTEL_FIRST_FIELDS',json.dumps(compact_fields(best[0],r'hotel|name|star|price|adult|total|room',180),ensure_ascii=False,default=str)[:11000])
        stars=[]; names5=[]
        for h in best:
            star=None
            for path,val in walk(h):
                if re.search(r'(^|\.)(hotelStar|star|stars)$',path,re.I):
                    try: star=int(float(val)); break
                    except: pass
            if star is not None: stars.append(star)
            if star==5:
                nm=None
                for path,val in walk(h):
                    if re.search(r'(hotelName|nameFa|hotel\.name|^name$)',path,re.I): nm=str(val);break
                if nm:names5.append(nm)
        print('STAR_COUNTS',dict(sorted(Counter(stars).items())))
        print('FIVE_STAR_NAMES',names5[:20])
    else: print('HOTEL_LAST',json.dumps(last,ensure_ascii=False,default=str)[:4000] if last is not None else '')

    print('\n=== FINAL ===')
    tour_ok=isinstance(tour,dict) and r is not None and (status_of(tour) in (None,'success','Success',True,1) or bool(hotels))
    flight_ok=bool(ob and ib)
    hotel_ok=bool(best)
    print('TOUR_OK',tour_ok,'FLIGHT_OK',flight_ok,'HOTEL_OK',hotel_ok,'ROUTE',dep,arr,'DATES','1405-06-20','1405-06-23')
    if not (tour_ok and flight_ok and hotel_ok): sys.exit(2)
finally:
    d.quit()
