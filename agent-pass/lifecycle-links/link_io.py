import csv,gzip,hashlib,io,json,pathlib,time,urllib.request
import pyarrow.parquet as pq
READS=[]
def fetch(repo,rev,path):
    url=f"https://raw.githubusercontent.com/{repo}/{rev}/{path}"
    for a in range(5):
        try:b=urllib.request.urlopen(url,timeout=120).read();break
        except Exception:
            if a==4:raise
            time.sleep(a+1)
    READS.append(dict(repository=repo,revision=rev,path=path,bytes=len(b),sha256=hashlib.sha256(b).hexdigest()))
    return b
def js(repo,rev,path):return json.loads(fetch(repo,rev,path))
def csvdata(repo,rev,path):
    b=fetch(repo,rev,path)
    if path.endswith(".gz"):b=gzip.decompress(b)
    return list(csv.DictReader(io.StringIO(b.decode())))
def parquet(repo,rev,path):return pq.read_table(io.BytesIO(fetch(repo,rev,path)))
def writejson(path,obj):
    path=pathlib.Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    b=json.dumps(obj,indent=1,ensure_ascii=False).encode()
    path.write_bytes(gzip.compress(b,mtime=0) if path.suffix==".gz" else b)
def selector(rev,path,**where):
    return dict(repository="DavisAI1974/markets-data",revision=rev,path=path,where=where)
def asof(times,clock):
    from bisect import bisect_right
    return bisect_right(times,clock)-1
def parent_key(day,cid,kind="candidate"):return f"{day}:{cid}:{kind}"
