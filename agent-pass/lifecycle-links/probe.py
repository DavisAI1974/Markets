import io,json,pathlib,urllib.request,pyarrow.parquet as pq
ROOT="tasks/family-research-20261022"
out={}
for revision,path in [
("9e3365f76fb4d34d97eb193d35072aae5f51b709",ROOT+"/whole-lifecycles/run-42573465249-1/audit-20231002/"+f)
for f in ("whole-lifecycles.parquet","component-windows.parquet","native-flow-source-clocks.parquet")]+[
("87dc338f2e74646eb731b3cd6f8968a5a0a653e2",ROOT+"/combined-events/run-42571551209-1/events-20231002/"+f)
for f in ("a-dipole-clocks.parquet","a-trade-dipole-overlaps.parquet","cross-study-event-links.parquet")]:
 b=urllib.request.urlopen(f"https://raw.githubusercontent.com/DavisAI1974/markets-data/{revision}/{path}").read()
 t=pq.read_table(io.BytesIO(b));out[path]={"schema":str(t.schema),"rows":len(t),"sample":t.slice(0,1).to_pylist()}
p=pathlib.Path("results");p.mkdir(exist_ok=True)
(p/"probe.json").write_text(json.dumps(out,indent=2,default=str))
print(json.dumps(out,indent=2,default=str))
