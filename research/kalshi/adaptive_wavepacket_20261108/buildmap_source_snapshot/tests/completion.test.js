import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import crypto from 'node:crypto';
import { spawnSync } from 'node:child_process';
import { scanProject } from '../src/scan.js';
import { traceCalculation } from '../src/workflow-explain.js';
import { evaluateAnalysis } from '../src/review-evidence.js';
import { importMeasurements } from '../src/measurements.js';
import { prepareGuideTask, serializeGuideSession, restoreGuideSession, compareGuideTask } from '../public/guide-tasks.js';
const hash = x => crypto.createHash('sha256').update(x).digest('hex');
const fixture = t => { const root = fs.mkdtempSync(path.join(os.tmpdir(), 'buildmap-completion-')); t.after(() => fs.rmSync(root, { recursive: true, force: true })); return root; };
const write = (root, name, content) => { fs.mkdirSync(path.dirname(path.join(root, name)), { recursive: true }); fs.writeFileSync(path.join(root, name), content); };

test('source walkthrough follows real arguments, transformed values, saved products and consumers without running the project', t => {
  const root = fixture(t);
  write(root,'prepare.py', `import pandas as pd\ndef prepare(source):\n    """Build the shared feature table for later comparisons."""\n    frame = pd.read_csv(source)\n    frame.to_parquet('prepared.parquet')\n    return frame\n`);
  write(root,'main.py', `from prepare import prepare\nimport pandas as pd\ndef run():\n    table = prepare('raw.csv')\n    return table\ndef consume():\n    return pd.read_parquet('prepared.parquet')\nraise RuntimeError('must not execute')\n`);
  const w = scanProject(root).workflow, run = w.calculations.find(c => c.name === 'run'), prepare = w.calculations.find(c => c.name === 'prepare');
  assert.match(prepare.purpose, /shared feature table/);
  const link = w.relationships.find(r => r.from === run.id);
  assert.deepEqual(link.inputBindings.map(b => [b.parameter,b.expression]), [['source',"'raw.csv'"]]);
  assert.deepEqual(link.resultTargets,['table']);
  assert.equal(run.explanation.throughCalls[0].expression,"'raw.csv'");
  assert.match(run.explanation.throughCalls[0].basis,/not resolved runtime paths/);
  assert.equal(prepare.explanation.consumers[0].product,'prepared.parquet');
  const trace = traceCalculation(w,run.id); assert.deepEqual(trace.steps.map(s => s.name),['run','prepare']);
  assert.equal(trace.truncated,false); assert.match(trace.basis,/not a runtime schedule/);
  assert.throws(() => traceCalculation(w,'missing'));
  assert.equal(traceCalculation(w,run.id,{limit:1}).truncated,true);
  assert.deepEqual(fs.readdirSync(root).sort(),['main.py','prepare.py']);
});

test('JavaScript shares the workflow model, links exported local imports and retains directional arguments', t => {
  const root = fixture(t);
  write(root,'support.js', `import fs from 'node:fs';\nexport function prepare(file) { const data=fs.readFileSync('raw.csv'); fs.writeFileSync('prepared.csv',data); return data; }\nfunction hidden() { return 1; }\n`);
  write(root,'main.js', `import {prepare,hidden} from './support.js';\nexport function run(a,b) { const table=prepare('raw.csv'); prepare('raw.csv'); hidden(); return table; }\n`);
  const w=scanProject(root).workflow, run=w.calculations.find(c=>c.name==='run');
  assert.equal(run.language,'JavaScript');
  assert.ok(w.relationships.some(r=>r.from===run.id && w.calculations.find(c=>c.id===r.to).name==='prepare'));
  assert.equal(w.relationships.some(r=>w.calculations.find(c=>c.id===r.to).name==='hidden'),false);
  assert.equal(w.coverage.parsedJavaScriptFiles,2);
  assert.ok(w.dataProducts.find(p=>p.pathExpression==='raw.csv'));
  assert.ok(w.findings.find(f=>f.type==='potential-repeated-computation'));
});

test('helper input propagation substitutes identifier nodes without rewriting quoted text or merging symbolic file identities', t=>{
  const root=fixture(t);
  write(root,'read.js',`import fs from 'node:fs';\nimport path from 'node:path';\nfunction read(root,rel) { return fs.readFileSync(path.join(root,rel,'rel')); }\nexport function load(root) { return read(root,'input.csv'); }\n`);
  const w=scanProject(root).workflow, load=w.calculations.find(c=>c.name==='load');
  assert.equal(load.explanation.throughCalls[0].expression,`path.join(root, 'input.csv', "rel")`);
  assert.equal(w.dataProducts.length,0);
  assert.equal(w.calculations.find(c=>c.name==='read').io[0].pathKind,'symbolic');
});

test('opposite branches and existing cache helpers are contextualized without declaring reuse or dropping warnings', t => {
  const root=fixture(t);
  write(root,'pipeline.py', `def cached_read():\n    return reuse_cache('raw.csv')\ndef run(flag):\n    if flag:\n        return open('raw.csv')\n    else:\n        return open('raw.csv')\ndef search(a,b):\n    cached_read()\n    for x in a:\n        for y in b:\n            compare(x,y)\n`);
  const w=scanProject(root).workflow;
  const read=w.findings.find(f=>f.type==='potential-repeated-read');
  assert.equal(read.reviewPriority,'context-first');
  assert.equal(read.reviewContext.branchRelationship,'opposite-branches-of-same-condition');
  const fanout=w.findings.find(f=>f.type==='nested-loop-fanout');
  assert.equal(fanout.reviewContext.reuseStatus,'existing-controls-need-validation');
  assert.equal(fanout.workload.actualJobs,null);
});

test('stateful partial extension needs exact boundary state, reviewed policy and current receipts; holes stay separate', () => {
  const contract={sourceIdentity:'input',calculationIdentity:'causal-sum',schemaIdentity:'one-column',axisIdentity:'ordered-event',availabilityIdentity:'no-fill',semantics:{kind:'stateful',boundaryPolicy:{id:'sum-v1',stateSchemaIdentity:'sum-state',review:'Interrupted prefix equals full-prefix state',owner:'one-writer',missingValuePolicy:'preserve',ordering:'ordered-rows'}}};
  const product={id:'sums',required:{contract,rows:[{start:0,end:10}],columns:['sum']},available:[{id:'prefix',contract,regions:[{rows:{start:0,end:5},columns:['sum']}]}],boundaryStates:[{id:'after-five',row:5,stateIdentity:'sha256-state',contract,bindings:{'state.json':'a'.repeat(64)}}]};
  const doc={version:1,products:[product]};
  let p=evaluateAnalysis(doc,[],()=>({current:true})).products[0];
  assert.equal(p.extensionStatus,'conditional-plan-needs-output-verification'); assert.equal(p.extension[0].boundaryState.row,5); assert.equal(p.verified,false);
  p=evaluateAnalysis(doc,[],()=>({current:false})).products[0]; assert.equal(p.extensionStatus,'blocked-needs-domain-boundary-state');
  product.boundaryStates.push({...product.boundaryStates[0],id:'conflicting'});
  p=evaluateAnalysis(doc,[],()=>({current:true})).products[0]; assert.equal(p.extension[0].boundaryState,null);
});

test('saved Guide task restores original baseline across actual source edits, rejects another project and unsafe imports', t => {
  const root=fixture(t); write(root,'worker.js','export function work(a) { return a+1; }');
  const before=scanProject(root), node=before.nodes.find(n=>n.files.includes('worker.js'));
  const fields={goal:'Return exact result',criteria:'Check values',limits:'Preserve source contract',supportIds:[],functionKey:'',outcomeId:''};
  const task=prepareGuideTask(before,node.id,fields), encoded=serializeGuideSession({nodeId:node.id,phase:'agreed',fields,task},before);
  write(root,'worker.js','export function work(a) { return a+2; }'); const after=scanProject(root);
  const restored=restoreGuideSession(encoded,after); assert.equal(restored.task.snapshot.fingerprint,before.fingerprint);
  assert.equal(compareGuideTask(restored.task,after,{freshRead:true}).fileChanges[0].kind,'content changed');
  assert.throws(()=>restoreGuideSession(encoded,{...after,project:{...after.project,root:root+'/different'}}),/different/);
  const bad=JSON.parse(encoded); bad.session.task.allowedPaths=['../escape']; assert.throws(()=>restoreGuideSession(JSON.stringify(bad),after));
  assert.equal(restoreGuideSession(encoded,after,{imported:true}).imported,true);
});

test('actual small workflow measurements import, bind log bytes and preserve exact counters and duplicate refusal', t => {
  const root=fixture(t);
  // This trusted test project is deliberately executed by the test, never by the scanner.
  const worker=`import json\nfrom time import perf_counter\nt=perf_counter()\nvalues=list(range(10))\nresult=sum(x*x for x in values)\nassert result==285\nidentity=dict(sourceIdentity='input-0-9',calculationIdentity='sum-squares',workloadIdentity='ten',environmentIdentity='test-python',metricScopeIdentity='whole-process')\nprint(json.dumps(dict(type='buildmap-measurement',version=1,observation=dict(id='observed',identity=identity,counters=dict(eligibleJobs=10,completedJobs=10,remainingJobs=0,pairComparisons=0),metrics=dict(elapsedSeconds=perf_counter()-t)))))\n`;
  write(root,'worker.py',worker);
  const run=spawnSync('python3',['-I','-S',path.join(root,'worker.py')],{encoding:'utf8'}); assert.equal(run.status,0,run.stderr);
  write(root,'measured.ndjson',run.stdout);
  const imported=importMeasurements(root,path.join(root,'measured.ndjson'));
  assert.equal(imported.imported,1); assert.equal(imported.input.bound,true);
  assert.equal(imported.document.runtime[0].bindings['measured.ndjson'],hash(run.stdout));
  write(root,'.buildmap/analysis.json',JSON.stringify(imported.document));
  const w=scanProject(root).workflow; assert.equal(w.review.observations[0].freshness.status,'current');
  assert.equal(w.review.observations[0].counters.remainingJobs,'0');
  assert.throws(()=>importMeasurements(root,path.join(root,'measured.ndjson'),imported.document),/Conflicting/);
  write(root,'measured.ndjson','{}'); assert.throws(()=>importMeasurements(root,path.join(root,'measured.ndjson')));
});

test('dimension forecasts require exact captured axes, current receipts and independent bounds; measured jobs remain separate', t => {
  const root=fixture(t); write(root,'jobs.py','def jobs(cells,transforms):\n    for cell in cells:\n        for transform in transforms:\n            compare(cell,transform)\n');
  const calculations=scanProject(root).workflow.calculations, c=calculations.find(c=>c.name==='jobs');
  const record={id:'forecast',workloadIdentity:'input-v1',independentCartesian:true,calculation:{path:c.source.path,name:c.name,sourceHash:c.source.sourceHash},axes:[{expression:'cells',min:'2',likely:'4',max:'6'},{expression:'transforms',min:'3',likely:'5',max:'7'}],bindings:{'dimensions.json':'a'.repeat(64)}};
  const doc={version:1,workloads:[record]};
  let w=evaluateAnalysis(doc,calculations,()=>({current:true})).workloads[0];
  assert.deepEqual(w.potentialIterations,{min:'6',likely:'20',max:'42'}); assert.equal(w.actualJobs,null); assert.equal(w.pairComparisons,null);
  assert.equal(evaluateAnalysis(doc,calculations,()=>({current:false})).workloads[0].status,'refused');
  record.axes[0].expression='unknown'; assert.equal(evaluateAnalysis(doc,calculations,()=>({current:true})).workloads[0].status,'refused');
  record.independentCartesian=false; assert.equal(evaluateAnalysis(doc,calculations).workloads.length,0);
});

test('real repeated-read test case preserves outputs, measures three reads versus one and compares current bound reports', t => {
  const root=fixture(t);
  write(root,'raw.json',JSON.stringify([1,2,3,4]));
  const source=`import json,sys,time\nreads=0\ndef read():\n    global reads\n    reads+=1\n    with open('raw.json') as f:\n        return json.load(f)\ndef legacy():\n    total=0\n    for i in range(3):\n        total+=sum(read())\n    return total\ndef shared():\n    values=read()\n    return sum(values)*3\nstarted=time.perf_counter()\nresult=legacy() if sys.argv[1]=='before' else shared()\nassert result==30\nprint(json.dumps({'type':'buildmap-measurement','version':1,'observation':{'id':sys.argv[1],'baselineId':'before' if sys.argv[1]=='after' else None,'identity':{'sourceIdentity':'same-program-and-input','calculationIdentity':'repeat-sum-exact','workloadIdentity':'three-times-four','environmentIdentity':'python-test-one-process','metricScopeIdentity':'whole-program-read-calls'},'counters':{'eligibleJobs':3,'completedJobs':3,'remainingJobs':0,'reads':reads,'pairComparisons':0},'metrics':{'elapsedSeconds':time.perf_counter()-started}}}))\n`;
  write(root,'read_case.py',source);
  const logs=['before','after'].map(mode=>{const r=spawnSync('python3',['-I','-S','read_case.py',mode],{cwd:root,encoding:'utf8'});assert.equal(r.status,0,r.stderr);return r.stdout;}).join('');
  write(root,'observed.ndjson',logs);
  const report=importMeasurements(root,path.join(root,'observed.ndjson')).document;
  for(const r of report.runtime) r.bindings['read_case.py']=hash(source);
  write(root,'.buildmap/analysis.json',JSON.stringify(report));
  const w=scanProject(root).workflow, comparison=w.review.comparisons[0];
  assert.ok(w.calculations.find(c=>c.name==='legacy').calls.some(c=>c.target==='read'));
  assert.ok(w.findings.some(f=>f.type==='potential-repeated-read-through-helper' && f.title.includes('legacy')));
  assert.equal(comparison.status,'comparable-reported-observations');assert.equal(comparison.counterDifferences.reads,'-2');
  assert.equal(w.review.observations[0].counters.reads,'3');assert.equal(w.review.observations[1].counters.reads,'1');
  assert.equal(w.review.observations[1].counters.pairComparisons,'0');
});

test('reported stage traces retain clocks, checkpoint contracts and incomplete handoffs without inventing a runtime schedule', t => {
  const root=fixture(t), doc={version:1,stages:[{id:'prepare',outputs:['table'],checkpointProducts:['table']},{id:'consume',dependsOn:['prepare'],inputs:['table']}],products:[]};
  const event=(id,stageId,event,sequence,extra={})=>({type:'buildmap-stage-event',version:1,event:{id,stageId,event,sequence,runIdentity:'small-run',clockIdentity:'monotonic-main',...extra}});
  const events=[event('a','prepare','start',0),event('b','prepare','save-checkpoint',1,{productId:'table'}),event('c','prepare','finish',2,{result:'passed'}),event('d','consume','start',3),event('e','consume','read-product',4,{productId:'table'}),event('f','consume','finish',5,{result:'passed'})];
  write(root,'events.ndjson',events.map(e=>JSON.stringify(e)).join('\n'));
  const imported=importMeasurements(root,path.join(root,'events.ndjson'),doc);
  assert.equal(imported.importedEvents,6);
  const result=evaluateAnalysis(imported.document,[],()=>({current:true}));
  assert.equal(result.events.length,6);assert.equal(result.events[1].event,'save-checkpoint');
  assert.equal(result.diagnostics.some(d=>d.section==='events'),false);
  const partial={...imported.document,events:[imported.document.events[3],imported.document.events[5]]};
  assert.ok(evaluateAnalysis(partial,[],()=>({current:true})).diagnostics.some(d=>/No preceding successful finish/.test(d.message)));
  const reversed={...imported.document,events:[imported.document.events[2],imported.document.events[0]]};
  assert.ok(evaluateAnalysis(reversed,[],()=>({current:true})).diagnostics.some(d=>/strictly increasing/.test(d.message)));
  const retry={...imported.document,events:[...imported.document.events.slice(0,3),{...imported.document.events[0],id:'retry',sequence:3},{...imported.document.events[3],id:'consumer-after-retry',sequence:4}]};
  assert.ok(evaluateAnalysis(retry,[],()=>({current:true})).diagnostics.some(d=>/No preceding successful finish/.test(d.message)));
});

test('plain operation explanations, exact field selectors and SQL-like literal references remain source-attributed',t=>{
 const root=fixture(t);
 write(root,'calculate.py',`def total(rows, connection):\n    """Calculate the requested subtotal from the provided price values."""\n    selected=rows['price']\n    squared=selected*selected\n    summed=sum(selected)\n    connection.execute("SELECT price FROM orders JOIN customers ON orders.id=customers.id WHERE label='FROM fake' -- JOIN imaginary\\n")\n    return {'square':squared,'sum':summed}\nraise RuntimeError('must never execute while scanning')\n`);
 write(root,'guide.js','/** Build the source subtotal for the selected rows. */\nexport function subtotal(price) { const total=price*2; return total; }');
 const w=scanProject(root).workflow,c=w.calculations.find(c=>c.name==='total');
 assert.match(c.purpose,/Source documentation: Calculate/);assert.ok(c.steps.some(s=>s.explanation.includes('Sums the supplied values')));
 assert.equal(c.fieldAccesses[0].selector,"'price'");assert.deepEqual(c.sql[0].tables.map(t=>t.tableExpression),['orders','customers']);
 assert.match(c.sql[0].basis,/unverified/);
 const js=w.calculations.find(c=>c.name==='subtotal');assert.match(js.purpose,/Build the source subtotal/);assert.match(js.steps[0].explanation,/expression using \*/);
});
