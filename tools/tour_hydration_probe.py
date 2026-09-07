import re, ssl, urllib.request, html, json
URL='https://flyyab.ir/tours/tehran-mashhad?departing=1405-06-20&returning=1405-06-23&rooms=1&adt%5B0%5D=2'
req=urllib.request.Request(URL,headers={'User-Agent':'Mozilla/5.0 Chrome/128 Safari/537.36','Accept':'text/html,*/*'})
with urllib.request.urlopen(req,timeout=50,context=ssl.create_default_context()) as r: raw=r.read()
s=html.unescape(raw.decode('utf-8','replace'))
# Next flight payload is JSON-string escaped. Keep raw and lightly de-escape copies.
variants=[('raw',s),('dequoted',s.replace('\\"','"')),('dequoted2',s.replace('\\\\"','"').replace('\\"','"'))]
terms=['مشهد','Mashhad','MHD','تهران','Tehran','THR','IKA','cityID','safarID','countryID']
print('PAGE_HTTP 200 BYTES',len(raw))
for name,t in variants:
 print('\n=== VARIANT',name,'LEN',len(t),'===')
 for term in terms:
  poss=[m.start() for m in re.finditer(re.escape(term),t,re.I)][:6]
  print('TERM',term,'COUNT_SHOWN',len(poss),'POS',poss)
  for i in poss[:2]: print('SNIP',term,t[max(0,i-1200):i+2600].replace('\n',' ')[:3800])
 # Find city-like objects/snippets with destination terms.
 for target in ['مشهد','Mashhad','MHD','تهران','Tehran','THR','IKA']:
  for m in list(re.finditer(re.escape(target),t,re.I))[:8]:
   i=m.start(); win=t[max(0,i-5000):i+7000]
   ids=re.findall(r'"?(cityID|safarID|countryID|iata|cityFa|cityEn)"?\s*:\s*"?([^",}\]]+)',win,re.I)
   print('FIELDS_AROUND',target,'@',i,json.dumps(ids[-30:],ensure_ascii=False))
