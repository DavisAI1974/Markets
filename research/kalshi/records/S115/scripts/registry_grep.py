import json,sys,re
d=json.load(open('/home/user/Markets/research/kalshi/OPEN_ITEMS.json'))['items']
pat=sys.argv[1]
rx=re.compile(pat,re.I)
for it in d:
    blob=it['id']+' '+it.get('title','')+' '+str(it.get('why',''))+' '+str(it.get('source',''))
    if rx.search(blob):
        m=[x.group(0) for x in rx.finditer(blob)][:3]
        print(it['id'],'|',it.get('status'),'|',it['title'][:105])
