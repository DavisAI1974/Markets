import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import crypto from 'node:crypto';
import {spawnSync} from 'node:child_process';
import {generateCollectorKey,observePython,verifyCollectedRun,observedReuseGroups,compareCollectedRuns} from '../src/collected-runs.js';
import {scanProject} from '../src/scan.js';
const hash=x=>crypto.createHash('sha256').update(x).digest('hex');
function setup(t,source){const temp=fs.mkdtempSync(path.join(os.tmpdir(),'buildmap-observe-'));t.after(()=>fs.rmSync(temp,{recursive:true,force:true}));
 const root=path.join(temp,'project');fs.mkdirSync(root);fs.mkdirSync(path.join(root,'.buildmap'));fs.writeFileSync(path.join(root,'main.py'),source);
 const privateKeyFile=path.join(temp,'key.pem'),publicFile=path.join(root,'.buildmap/collectors.json');generateCollectorKey(privateKeyFile,publicFile,'local');
 return {temp,root,privateKeyFile,collectorId:'local',sourceHashes:{'main.py':hash(source)},entry:'main.py',output:path.join(root,'run.json'),trust:JSON.parse(fs.readFileSync(publicFile))};}

test('opt-in collector traces dynamic dispatch/nested calls, authenticates the receipt and retains directional input identities',async t=>{
 const s=setup(t,`from pathlib import Path\ndef outer():\n    def inner(a,b):\n        return a-b\n    dispatch={'calc':inner}\n    return dispatch['calc'](4,1), dispatch['calc'](1,4), dispatch['calc'](4,1)\nassert outer()==(3,-3,3)\nPath('observed.txt').write_text('exact')\n`);
 const result=await observePython(s);assert.equal(result.receipt.payload.exitCode,0,result.stderr.toString());assert.equal(result.receipt.payload.completeWithinScope,true);
 const m=scanProject(s.root), run=verifyCollectedRun(result.receipt,s.trust,s.sourceHashes,m.workflow.calculations);
 assert.equal(run.status,'verified-collector-current-source');assert.equal(run.verifiedSignature,true);
 const inner=run.calculations.find(c=>c.name==='outer.inner');assert.equal(inner.calls,'3');assert.equal(inner.sourceMatch,'current-declaration');
 assert.equal(inner.inputGroups.length,2);assert.deepEqual(inner.inputGroups.map(g=>g.calls).sort(),['1','2']);
 assert.ok(run.payload.relationships.some(e=>e.to===inner.id));assert.ok(run.payload.operations.find(o=>o.path==='observed.txt').openAttempts>0);
 const groups=observedReuseGroups(run);assert.ok(groups.some(g=>g.name==='outer.inner'&&g.calls==='2'&&g.stableObservedOutputs));
 assert.ok(run.payload.metrics.elapsedSeconds>0);assert.ok(run.payload.metrics.peakMemoryBytes>0);
 fs.writeFileSync(path.join(s.root,'.buildmap/analysis.json'),JSON.stringify({version:1,collectedRuns:['run.json']}));
 const mapped=scanProject(s.root).workflow.collected;assert.equal(mapped.runs[0].eligibleForComparison,true);
 assert.equal(fs.statSync(s.privateKeyFile).mode&0o777,0o600);
});

test('tampered receipts, unknown keys, changed source and incomplete runs cannot justify reuse',async t=>{
 const s=setup(t,'def value(x):\n    return x+1\nassert value(2)==3\n'), {receipt}=await observePython(s), map=scanProject(s.root);
 const bad=structuredClone(receipt);bad.payload.metrics.elapsedSeconds=0;
 assert.equal(verifyCollectedRun(bad,s.trust,s.sourceHashes,map.workflow.calculations).status,'refused');
 assert.equal(verifyCollectedRun(receipt,{version:1,collectors:[]},s.sourceHashes).status,'refused');
 const stale=verifyCollectedRun(receipt,s.trust,{'main.py':'0'.repeat(64)},map.workflow.calculations);assert.equal(stale.status,'stale');assert.deepEqual(observedReuseGroups(stale),[]);
 const dup={version:1,collectors:[...s.trust.collectors,...s.trust.collectors]};assert.equal(verifyCollectedRun(receipt,dup,s.sourceHashes).status,'refused');
});

test('failed/changed-source/timed-out observations preserve signed partial receipts without successful-run claims',async t=>{
 for(const source of ["raise RuntimeError('expected test failure')\n", "from pathlib import Path\nPath(__file__).write_text('changed')\n",'import time\ntime.sleep(2)\n']){
  const s=setup(t,source), result=await observePython({...s,timeoutMs:source.includes('sleep')?150:5000});
  const sourceHashes={'main.py':hash(fs.readFileSync(path.join(s.root,'main.py')))};
  const run=verifyCollectedRun(result.receipt,s.trust,sourceHashes,[]);
  assert.equal(run.verifiedSignature,true);assert.equal(run.eligibleForComparison,false);
  if(source.includes('sleep'))assert.equal(result.receipt.payload.parent.timedOut,true);
  if(source.includes('write_text'))assert.deepEqual(result.receipt.payload.sourceChanges,['main.py']);
 }
});

test('output collision, unsafe entry and in-project private key refuse before running mapped code',async t=>{
 const s=setup(t,"from pathlib import Path\nPath('must-not-exist').write_text('bad')\n");
 fs.writeFileSync(s.output,'preserve');await assert.rejects(observePython(s),/EEXIST/);assert.equal(fs.existsSync(path.join(s.root,'must-not-exist')),false);
 await assert.rejects(observePython({...s,entry:'../escape.py'}),/entry point/);
 fs.copyFileSync(s.privateKeyFile,path.join(s.root,'unsafe.pem'));await assert.rejects(observePython({...s,privateKeyFile:path.join(s.root,'unsafe.pem')}),/outside/);
});

test('CLI observation is explicit and signs a run while default JSON mapping remains non-executing',t=>{
 const s=setup(t,"from pathlib import Path\nPath('ran.txt').write_text('yes')\n");
 const cli=fileURL();
 const mapped=spawnSync(process.execPath,[cli,s.root,'--json'],{encoding:'utf8'});assert.equal(mapped.status,0,mapped.stderr);assert.equal(fs.existsSync(path.join(s.root,'ran.txt')),false);
 const run=spawnSync(process.execPath,[cli,s.root,'--observe-python','main.py','--collector-key',s.privateKeyFile,'--collector-id','local','--observation-output',s.output],{encoding:'utf8'});
 assert.equal(run.status,0,run.stderr);assert.equal(fs.readFileSync(path.join(s.root,'ran.txt'),'utf8'),'yes');assert.equal(JSON.parse(fs.readFileSync(s.output)).kind,'buildmap-collected-run');
});
function fileURL(){return new URL('../src/cli.js',import.meta.url).pathname;}

test('signed before/after comparison requires current source/input scope and a bound finite-case review for code changes',async t=>{
 const source=`import json\ndef read():\n    with open('input.json') as f:\n        return json.load(f)\ndef run():\n    total=0\n    for i in range(3):\n        total+=sum(read())\n    return total\nassert run()==30\n`;
 const s=setup(t,source);fs.writeFileSync(path.join(s.root,'input.json'),'[1,2,3,4]');
 const first=await observePython(s);
 const optimized=source.replace('    total=0\n    for i in range(3):\n        total+=sum(read())','    values=read()\n    total=0\n    for i in range(3):\n        total+=sum(values)');
 fs.writeFileSync(path.join(s.root,'main.py'),optimized);const hashes={'main.py':hash(optimized)};
 const second=await observePython({...s,sourceHashes:hashes,output:path.join(s.root,'after.json')});const map=scanProject(s.root);
 const inputCheck=(p,h)=>hash(fs.readFileSync(path.join(s.root,p)))===h;
 const before=verifyCollectedRun(first.receipt,s.trust,hashes,map.workflow.calculations,inputCheck),after=verifyCollectedRun(second.receipt,s.trust,hashes,map.workflow.calculations,inputCheck);
 assert.equal(before.status,'stale');assert.equal(after.status,'verified-collector-current-source');
 assert.equal(compareCollectedRuns(before,after,{calculation:{path:'main.py',name:'run'}}).status,'refused');
 const compared=compareCollectedRuns(before,after,{calculation:{path:'main.py',name:'run'},codeReview:{currentBindings:true,note:'Compare exact result on this input; read is pure for this test',paths:['main.py']}});
 assert.equal(compared.status,'comparable-signed-observations');assert.equal(compared.finiteValueComparison.directionalInputGroups,1);
 assert.equal(first.receipt.payload.operations.find(o=>o.path==='input.json'&&o.mode==='r').openAttempts,3);
 assert.equal(second.receipt.payload.operations.find(o=>o.path==='input.json'&&o.mode==='r').openAttempts,1);
 assert.equal(after.payload.inputs.find(i=>i.path==='input.json').status,'current');
 fs.writeFileSync(path.join(s.root,'input.json'),'[0,0,0,10]');
 const third=await observePython({...s,sourceHashes:hashes,output:path.join(s.root,'different.json')});
 const different=verifyCollectedRun(third.receipt,s.trust,hashes,map.workflow.calculations,inputCheck);
 assert.equal(compareCollectedRuns(after,different,{calculation:{path:'main.py',name:'run'}}).status,'refused');
});

test('custom values never invoke repr hooks and floating-point signs retain distinct input identities',async t=>{
 const s=setup(t,`from pathlib import Path\nclass Trap:\n    def __repr__(self):\n        Path('bad-repr').write_text('bad')\n        return 'trap'\ndef call(value):\n    return 1\ncall(Trap())\ncall(0.0)\ncall(-0.0)\n`);
 const {receipt}=await observePython(s);assert.equal(receipt.payload.exitCode,0);assert.equal(fs.existsSync(path.join(s.root,'bad-repr')),false);
 const call=receipt.payload.calculations.find(c=>c.name==='call');assert.equal(call.inputGroups.length,2);assert.equal(call.calls,'3');assert.ok(receipt.payload.coverage.unsupportedValues>0);
});

test('numeric NumPy observations are byte/shape/dtype exact and oversized/object arrays remain unknown',async t=>{
 const available=spawnSync('python3',['-c','import numpy'],{encoding:'utf8'});if(available.status!==0){t.skip('Optional NumPy unavailable');return;}
 const s=setup(t,`import numpy as np\ndef inspect(value):\n    return value\ninspect(np.array([1.,2.]))\ninspect(np.array([1.,2.]))\ninspect(np.array([2.,1.]))\ninspect(np.zeros(100000))\ninspect(np.array([object()],dtype=object))\n`);
 const {receipt}=await observePython(s);assert.equal(receipt.payload.exitCode,0);
 const c=receipt.payload.calculations.find(c=>c.name==='inspect');assert.equal(c.calls,'5');assert.equal(c.inputGroups.length,2);assert.equal(c.inputGroups.find(g=>g.calls==='2').unavailableReturns,0);
 assert.ok(receipt.payload.coverage.unsupportedValues>=2);
});
