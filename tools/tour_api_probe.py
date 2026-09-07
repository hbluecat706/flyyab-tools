import json, ssl, urllib.request, urllib.error, http.cookiejar, time, re, sys
from collections import Counter

PAGE='https://flyyab.ir/tours/tehran-mashhad?departing=1405-06-20&returning=1405-06-23&rooms=1&adt%5B0%5D=2'
BOOK='https://flyyab.ir/_booking/'
PLUS='https://flyyab.ir/_bookingplus/public/api/'
UA='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/128 Safari/537.36'
ctx=ssl.create_default_context(); cj=http.cookiejar.CookieJar()
op=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj),urllib.request.HTTPSHandler(context=ctx))

def call(url,method='GET',body=None,headers=None):
    h={'User-Agent':UA,'Accept':'application/json,text/plain,*/*','Accept-Language':'fa-IR,fa;q=0.9,en;q=0.8','Origin':'https://flyyab.ir','Referer':PAGE}
    if headers:h.update(headers)
    data=None
    if body is not None:
        data=json.dumps(body,separators=(',',':'),ensure_ascii=False).encode('utf-8'); h['Content-Type']='application/json'
    q=urllib.request.Request(url,data=data,headers=h,method=method)
    try:
        with op.open(q,timeout=50) as r:return r.status,dict(r.headers),r.read()
    except urllib.error.HTTPError as e:return e.code,dict(e.headers),e.read()

def J(b):
    try:return json.loads(b.decode('utf-8','replace'))
    except:return None

def S(x):return x.get('status',x.get('Status')) if isinstance(x,dict) else None

def walk(x,p=''):
    if isinstance(x,dict):
        for k,v in x.items():yield from walk(v,f'{p}.{k}' if p else k)
    elif isinstance(x,list):
        for i,v in enumerate(x):yield from walk(v,f'{p}[{i}]')
    else:yield p,x

def cities(x,needle,country=None,out=None):
    if out is None:out=[]
    if isinstance(x,dict):
        c=x.get('countryID',x.get('CountryID',country)); aps=x.get('airports') or []
        text=(str(x.get('cityFa',''))+' '+str(x.get('cityEn',''))).lower()
        if x.get('cityID') is not None and (needle.lower() in text or any(str(a.get('iata','')).lower()==needle.lower() for a in aps if isinstance(a,dict))):out.append((x,c))
        for v in x.values():cities(v,needle,c,out)
    elif isinstance(x,list):
        for v in x:cities(v,needle,country,out)
    return out

def flights(v):
    o=[]
    if isinstance(v,list):
        for z in v:o += [z] if isinstance(z,dict) else flights(z)
    elif isinstance(v,dict):
        for z in v.values():o+=flights(z)
    return o

def hotel_lists(x,p=''):
    out=[]
    if isinstance(x,dict):
        for k,v in x.items():
            np=f'{p}.{k}' if p else k
            if isinstance(v,list) and v and isinstance(v[0],dict) and re.search(r'hotel|descriptive|content',np,re.I):out.append((np,v))
            elif isinstance(v,dict):out+=hotel_lists(v,np)
    return out

def field_dump(obj,rx,limit=120):
    return json.dumps([(p,v) for p,v in walk(obj) if re.search(rx,p,re.I)][:limit],ensure_ascii=False,default=str)[:9000]

def ok_status(x):
    s=str(S(x)).lower()
    return isinstance(x,dict) and (s in ('success','true','1','ok') or (S(x) is None and bool(x)))

# Page
hp,_,pr=call(PAGE); print('PAGE_HTTP',hp,'BYTES',len(pr))
if hp!=200:sys.exit(10)

# Public session token exactly as frontend initializes it.
ht,_,tr=call(BOOK+'home/token/getVersion','POST',{'token':'','lang':'fa','hasTrain':False,'clientVer':''}); tj=J(tr)
st=tj.get('token') if isinstance(tj,dict) else None; ver=tj.get('version','') if isinstance(tj,dict) else ''
print('TOKEN_HTTP',ht,'TOKEN_LEN',len(st or ''),'VERSION',ver,'KEYS',list(tj)[:20] if isinstance(tj,dict) else None)
if not st: print(tr[:1500]);sys.exit(11)

# airportWithCountry is called WITHOUT authorization by current frontend.
aj=None; ar=b''
for av in ['',ver]:
    ha,_,ar=call(BOOK+'home/airportWithCountry','POST',{'version':av})
    aj=J(ar); print('AIRPORT_ATTEMPT','VERSION',repr(av),'HTTP',ha,'STATUS',S(aj),'BYTES',len(ar),'KEYS',list(aj)[:20] if isinstance(aj,dict) else None)
    if isinstance(aj,(dict,list)) and (cities(aj,'tehran') or cities(aj,'تهران') or cities(aj,'ika')):break
th=cities(aj,'tehran') or cities(aj,'تهران') or cities(aj,'ika') if aj is not None else []
mh=cities(aj,'mashhad') or cities(aj,'مشهد') or cities(aj,'mhd') if aj is not None else []
print('CITY_MATCHES','TEHRAN',len(th),'MASHHAD',len(mh))
if not th or not mh: print('AIRPORT_BODY',ar.decode('utf-8','replace')[:5000]);sys.exit(12)
te,tc=th[0]; ma,mc=mh[0]
print('TEHRAN_CITY',json.dumps({k:te.get(k) for k in ['cityID','cityFa','cityEn','safarID','airports']},ensure_ascii=False)[:2500],'COUNTRY',tc)
print('MASHHAD_CITY',json.dumps({k:ma.get(k) for k in ['cityID','cityFa','cityEn','safarID','airports']},ensure_ascii=False)[:2500],'COUNTRY',mc)
dep=(te.get('airports') or [{}])[0].get('iata'); arr=(ma.get('airports') or [{}])[0].get('iata'); cid=f"{ma.get('cityID')}_{ma.get('safarID')}_{mc}"
print('ROUTE',dep,'->',arr,'DEST_ID',cid)

p={'activeTab':'TOUR-D','tourType':1,'tourFromCityIata':dep,'tourToCityIata':arr,'dateIn':'1405-06-20','dateOut':'1405-06-23','cabinType':'Economy','mixMode':'flight','cityID':cid,'selectedTourItm':None,'tourCode':None,'selectedTourDate':None,'roomNum':1,'room-1-ad-num':2,'room-1-child-numbers':0,'child-age-1-1':0,'child-age-1-2':0,'child-age-1-3':0,'room-2-ad-num':0,'room-2-child-numbers':0,'child-age-2-1':0,'child-age-2-2':0,'child-age-2-3':0,'room-3-ad-num':0,'room-3-child-numbers':0,'child-age-3-1':0,'child-age-3-2':0,'child-age-3-3':0,'token':st,'adt':2,'chd':0,'inf':0}

# Base tour search: frontend sends token in body, not Authorization.
hs,_,sr=call(BOOK+'tours/app/search','POST',p); sj=J(sr); hc=hotel_lists(sj); hp0,hi=max(hc,key=lambda z:len(z[1]),default=('',[]))
print('TOUR_SEARCH','HTTP',hs,'STATUS',S(sj),'BYTES',len(sr),'KEYS',list(sj)[:40] if isinstance(sj,dict) else None,'HOTELS',len(hi),'PATH',hp0)
if hi:
    print('TOUR_HOTEL_KEYS',list(hi[0])[:100]); print('TOUR_HOTEL_FIELDS',field_dump(hi[0],r'name|star|price|adult|total|room|hotel'))
if not isinstance(sj,dict):print('TOUR_BODY',sr.decode('utf-8','replace')[:4000])

# Flights
fb={'departure':dep,'arrival':arr,'date':'1405-06-20','adult':2,'child':0,'infant':0,'retDate':'1405-06-23','hasReturnAirline':False}
hf,_,fr=call(PLUS+'hub/check-route','POST',fb); fj=J(fr); ft=fj.get('token') if isinstance(fj,dict) else None
print('FLIGHT_TOKEN','HTTP',hf,'STATUS',S(fj),'HAS_TOKEN',bool(ft),'BODY',json.dumps(fj,ensure_ascii=False,default=str)[:1800] if fj is not None else fr.decode('utf-8','replace')[:1800])
flight=None
if ft:
    for ep,nmax in [('serachCacheTokenTour',1),('serachAvailTokenTour',10)]:
        for n in range(nmax):
            hu,_,ur=call(BOOK+'CheapestPrice/'+ep+'/'+str(ft),'GET',None,{'authorization':st}); uj=J(ur)
            ob=flights(uj.get('outbound2')) if isinstance(uj,dict) else []; ib=flights(uj.get('return')) if isinstance(uj,dict) else []
            print('FLIGHT_POLL',ep,n+1,'HTTP',hu,'STATUS',S(uj),'OUT',len(ob),'RET',len(ib),'BYTES',len(ur))
            if ob and ib:
                flight=uj; print('OUT_KEYS',list(ob[0])[:100]);print('RET_KEYS',list(ib[0])[:100]);print('OUT_FIELDS',field_dump(ob[0],r'airline|time|price|adult|flight|iata|departure|arrival'));print('RET_FIELDS',field_dump(ib[0],r'airline|time|price|adult|flight|iata|departure|arrival'));break
            if ep=='serachAvailTokenTour' and n<nmax-1:time.sleep(2)
        if flight:break

# Hotel webservice: current frontend uses same payload; no Authorization header in fetch.
hw,_,wr=call(BOOK+'hotels/app/wbRequest','POST',p); wj=J(wr)
print('HOTEL_REQUEST','HTTP',hw,'STATUS',S(wj),'BYTES',len(wr),'KEYS',list(wj)[:30] if isinstance(wj,dict) else None,'BODY',json.dumps(wj,ensure_ascii=False,default=str)[:1500] if wj is not None else wr.decode('utf-8','replace')[:1500])
best=[];bp='';last=None
for n in range(10):
    hr,_,rr=call(BOOK+'hotels/app/wbResponse/','POST',p); rj=J(rr); last=rj
    c=hotel_lists(rj); path,items=max(c,key=lambda z:len(z[1]),default=('',[]))
    if len(items)>len(best):best=items;bp=path
    print('HOTEL_POLL',n+1,'HTTP',hr,'STATUS',S(rj),'COUNT',len(items),'PATH',path,'BYTES',len(rr))
    if items and str(S(rj)).lower()=='success':break
    if n<9:time.sleep(2)
if best:
    print('HOTEL_COUNT',len(best),'PATH',bp,'KEYS',list(best[0])[:100]);print('HOTEL_FIELDS',field_dump(best[0],r'name|star|price|adult|total|room|hotel',150))
    stars=[]
    for h in best:
        for k in ['HotelStar','hotelStar','star','Star','stars']:
            if k in h:
                try:stars.append(int(float(h[k])))
                except:pass
                break
    print('STAR_COUNTS',dict(sorted(Counter(stars).items())))
else: print('HOTEL_LAST_BODY',json.dumps(last,ensure_ascii=False,default=str)[:3500] if last is not None else '')

tour_ok=isinstance(sj,dict) and ok_status(sj); flight_ok=flight is not None; hotel_ok=bool(best)
print('FINAL','TOUR_OK',tour_ok,'FLIGHT_OK',flight_ok,'HOTEL_OK',hotel_ok,'ROUTE',dep,arr,'DATES','1405-06-20','1405-06-23')
if not (tour_ok and flight_ok and hotel_ok):sys.exit(2)
