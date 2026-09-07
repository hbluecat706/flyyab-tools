import json, ssl, urllib.request, urllib.error, http.cookiejar, time, sys
from collections import Counter

BOOK='https://flyyab.ir/_booking/'
PLUS='https://flyyab.ir/_bookingplus/public/api/'
PAGE='https://flyyab.ir/tours/tehran-mashhad?departing=1405-06-20&returning=1405-06-23&rooms=1&adt%5B0%5D=2'
UA='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/152 Safari/537.36'
ctx=ssl.create_default_context(); cj=http.cookiejar.CookieJar()
op=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj),urllib.request.HTTPSHandler(context=ctx))

def call(url,method='GET',body=None,headers=None):
    h={'User-Agent':UA,'Accept':'application/json,text/plain,*/*','Accept-Language':'fa-IR,fa;q=0.9,en;q=0.8','Origin':'https://flyyab.ir','Referer':PAGE}
    if headers:h.update(headers)
    data=None
    if body is not None:
        data=json.dumps(body,separators=(',',':'),ensure_ascii=False).encode();h['Content-Type']='application/json'
    q=urllib.request.Request(url,data=data,headers=h,method=method)
    try:
        with op.open(q,timeout=55) as r:return r.status,r.read()
    except urllib.error.HTTPError as e:return e.code,e.read()

def J(b):
    try:return json.loads(b.decode('utf-8','replace'))
    except:return None

def stat(x):return x.get('status',x.get('Status')) if isinstance(x,dict) else None

def flat(v):
    o=[]
    if isinstance(v,list):
        for x in v:
            if isinstance(x,dict):o.append(x)
            else:o+=flat(x)
    elif isinstance(v,dict):
        for x in v.values():o+=flat(x)
    return o

print('=== DIRECT SERVER-SIDE PROBE ===')
# 1 public session token
h,b=call(BOOK+'home/token/getVersion','POST',{'token':'','lang':'fa','hasTrain':False,'clientVer':''});t=J(b);st=(t or {}).get('token') if isinstance(t,dict) else None
print('TOKEN_HTTP',h,'TOKEN_LEN',len(st or ''),'VERSION',(t or {}).get('version') if isinstance(t,dict) else None)
if h!=200 or not st:sys.exit(10)

# Exact payload captured from Chrome network on the live page.
p={'activeTab':'TOUR-D','tourType':1,'tourFromCityIata':'THRALL','tourToCityIata':'MHD','dateIn':'1405-06-20','dateOut':'1405-06-23','cabinType':'Economy','mixMode':'flight','cityID':'6395_6395_1','selectedTourItm':None,'tourCode':None,'selectedTourDate':None,'roomNum':1,
'room-1-ad-num':2,'room-1-child-numbers':0,'child-age-1-1':0,'child-age-1-2':0,'child-age-1-3':0,
'room-2-ad-num':0,'room-2-child-numbers':0,'child-age-2-1':0,'child-age-2-2':0,'child-age-2-3':0,
'room-3-ad-num':0,'room-3-child-numbers':0,'child-age-3-1':0,'child-age-3-2':0,'child-age-3-3':0,
'token':st,'adt':2,'chd':0,'inf':0}

# 2 tour search
h,b=call(BOOK+'tours/app/search','POST',p);tour=J(b)
print('TOUR_HTTP',h,'STATUS',stat(tour),'BYTES',len(b),'KEYS',list(tour.keys()) if isinstance(tour,dict) else None)
tour_ok=h==200 and isinstance(tour,dict) and str(stat(tour)).lower()=='success'

# 3 flight token + data
fb={'departure':'THRALL','arrival':'MHD','date':'1405-06-20','adult':2,'child':0,'infant':0,'retDate':'1405-06-23','hasReturnAirline':False}
h,b=call(PLUS+'hub/check-route','POST',fb);fj=J(b);ft=(fj or {}).get('token') if isinstance(fj,dict) else None
print('CHECK_ROUTE_HTTP',h,'STATUS',stat(fj),'TOKEN_LEN',len(str(ft or '')))
flight_ok=False; out=[]; ret=[]
if ft:
    for ep,maxtry in [('serachCacheTokenTour',1),('serachAvailTokenTour',8)]:
        for n in range(maxtry):
            h,b=call(BOOK+'CheapestPrice/'+ep+'/'+str(ft),'GET',None,{'authorization':st});x=J(b)
            out=flat(x.get('outbound2')) if isinstance(x,dict) else [];ret=flat(x.get('return')) if isinstance(x,dict) else []
            print('FLIGHT',ep,'TRY',n+1,'HTTP',h,'STATUS',stat(x),'OUT',len(out),'RET',len(ret),'BYTES',len(b))
            if h==200 and out and ret:flight_ok=True;break
            if ep=='serachAvailTokenTour' and n<maxtry-1:time.sleep(2)
        if flight_ok:break

# 4 hotel webservice
h,b=call(BOOK+'hotels/app/wbRequest','POST',p);wr=J(b)
print('WB_REQUEST_HTTP',h,'STATUS',stat(wr),'BYTES',len(b))
wbreq_ok=h==200 and isinstance(wr,dict) and str(stat(wr)).lower() in ('success','process')
habs=[];last=None
for n in range(8):
    h,b=call(BOOK+'hotels/app/wbResponse/','POST',p);last=J(b)
    hs=(last or {}).get('HotelDescriptiveContents',[]) if isinstance(last,dict) else []
    print('WB_RESPONSE_TRY',n+1,'HTTP',h,'STATUS',stat(last),'HOTELS',len(hs),'BYTES',len(b))
    if len(hs)>len(habs):habs=hs
    if hs and str(stat(last)).lower()=='success':break
    if n<7:time.sleep(2)
hotel_ok=bool(habs)

stars=Counter();five=[]
for x in habs:
    try:stars[int(float(x.get('HotelStar')))]+=1
    except:pass
    if str(x.get('HotelStar'))=='5':five.append(x.get('HotelName'))
print('HOTEL_COUNT',len(habs),'STAR_COUNTS',dict(sorted(stars.items())))
print('FIVE_STAR',five[:20])

def hotel(name):
    for x in habs:
        if str(x.get('HotelName','')).strip()==name:return x
    return None

gol=hotel('گل نرگس')
if gol:
    small={k:gol.get(k) for k in ['HotelName','HotelStar','price','BoardPrice','CurrencyCode','HotelCode','provider_type_id','RoomStays'] if k in gol}
    # Keep RoomStays concise.
    if isinstance(small.get('RoomStays'),list):small['RoomStays']=small['RoomStays'][:1]
    print('GOL_NARGES_API',json.dumps(small,ensure_ascii=False,default=str)[:7000])
    try:
        hp=float(gol.get('price'))
        # Live DOM in the immediately preceding browser E2E: party flight total 419,304,000 IRR; 2 adults.
        calc=(419304000+hp)/2
        print('PACKAGE_FORMULA','HOTEL_PRICE',hp,'FLIGHT_PARTY_TOTAL',419304000,'ADULTS',2,'CALC_PER_ADULT',calc,'EXPECTED_DOM',230148000,'MATCH',abs(calc-230148000)<1)
    except Exception as e:print('PACKAGE_FORMULA_ERROR',repr(e))
else:print('GOL_NARGES_NOT_FOUND')

print('FINAL_DIRECT_OK',tour_ok and flight_ok and wbreq_ok and hotel_ok)
if not (tour_ok and flight_ok and wbreq_ok and hotel_ok):sys.exit(2)
