import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import crypto from 'node:crypto';
import {spawnSync} from 'node:child_process';
import {evaluateAnalysis} from '../src/review-evidence.js';
const hash=x=>crypto.createHash('sha256').update(x).digest('hex');
const contract=semantics=>({sourceIdentity:'exact-values-with-nulls',calculationIdentity:'explicit-small-formula',schemaIdentity:'one-value-column',axisIdentity:'ordered-row',availabilityIdentity:'propagate-unknown',semantics});

test('independent and rolling extensions actually reproduce full output without filling nulls, bridging holes or losing overlap',()=>{
 const input=[1,2,null,4,5,6,7,8,9,10];
 for(const kind of ['independent','rolling']){
  const semantics=kind==='independent'?{kind}:{kind,lookbackRows:2,originRow:0};const c=contract(semantics);
  const calc=i=>{const values=kind==='independent'?[input[i]]:input.slice(Math.max(0,i-2),i+1);return values.some(v=>v===null)?null:kind==='independent'?values[0]**2:values.reduce((a,b)=>a+b,0);};
  const full=input.map((_,i)=>calc(i));
  const p={id:'values',required:{contract:c,rows:[{start:0,end:10}],columns:['value']},available:[{id:'retained',contract:c,regions:[{rows:{start:0,end:3},columns:['value']},{rows:{start:6,end:8},columns:['value']}]}]};
  const plan=evaluateAnalysis({version:1,products:[p]}).products[0];assert.deepEqual(plan.missing.map(m=>m.rows),[{start:3,end:6},{start:8,end:10}]);
  const restored=new Map([[0,full[0]],[1,full[1]],[2,full[2]],[6,full[6]],[7,full[7]]]);
  for(const step of plan.extension){
   const data=input.slice(step.inputRows.start,step.inputRows.end);
   for(let i=step.rows.start;i<step.rows.end;i++){
    const start=kind==='rolling'?Math.max(0,i-2):i;
    const values=data.slice(start-step.inputRows.start,i-step.inputRows.start+1);
    restored.set(i,values.some(v=>v===null)?null:kind==='independent'?values[0]**2:values.reduce((a,b)=>a+b,0));
   }
  }
  assert.deepEqual(input.map((_,i)=>restored.get(i)),full);
  assert.equal(restored.get(2),null);
  if(kind==='rolling'){assert.equal(plan.extension[0].inputRows.start,1);assert.equal(restored.get(3),null);}
 }
});

test('stateful extension uses the actual retained boundary state and refuses stale or mismatched state contracts',()=>{
 const input=[2,3,5,7,11,13,17], full=[];let value=0;for(const x of input){value+=x;full.push(value);}
 const c=contract({kind:'stateful',boundaryPolicy:{id:'cumulative-exact',stateSchemaIdentity:'sum-after-row',review:'State is exact cumulative sum of all prior rows; uninterrupted comparison passed',owner:'single-writer',missingValuePolicy:'unknown state blocks resume',ordering:'ordered-rows'}});
 const state={nextRow:3,total:full[2]}, stateBytes=JSON.stringify(state), stateHash=hash(stateBytes);
 const p={id:'sum',required:{contract:c,rows:[{start:0,end:7}],columns:['value']},available:[{contract:c,regions:[{rows:{start:0,end:3},columns:['value']}]}],boundaryStates:[{id:'prefix',row:3,stateIdentity:stateHash,contract:c,bindings:{'state.json':stateHash}}]};
 const read=(file,expected)=>({current:file==='state.json'&&expected===hash(stateBytes)});
 const plan=evaluateAnalysis({version:1,products:[p]},[],read).products[0];assert.equal(plan.extensionStatus,'conditional-plan-needs-output-verification');
 const output=full.slice(0,3);let resumed=JSON.parse(stateBytes).total;
 for(const step of plan.extension){assert.equal(step.boundaryState.stateIdentity,stateHash);for(let i=step.rows.start;i<step.rows.end;i++){resumed+=input[i];output[i]=resumed;}}
 assert.deepEqual(output,full);
 p.boundaryStates[0].contract={...c,sourceIdentity:'wrong-source'};assert.equal(evaluateAnalysis({version:1,products:[p]},[],read).products[0].extensionStatus,'blocked-needs-domain-boundary-state');
});

test('a real interrupted/resumed calculation exactly matches uninterrupted output and refuses incompatible/torn checkpoint state',t=>{
 const root=fs.mkdtempSync(path.join(os.tmpdir(),'buildmap-recovery-'));t.after(()=>fs.rmSync(root,{recursive:true,force:true}));
 const source=`import json,hashlib,sys,os\nfrom pathlib import Path\nmode=sys.argv[1]\nvalues=json.loads(Path('input.json').read_text())\nidentity=hashlib.sha256(Path('input.json').read_bytes()).hexdigest()\ncontract={'sourceIdentity':identity,'calculationIdentity':'cumulative-v1','schemaIdentity':'rows-and-sum','axisIdentity':'input-order','availabilityIdentity':'no-fill'}\nstate={'contract':contract,'nextRow':0,'sum':0,'outputs':[]}\nif mode=='resume':\n    state=json.loads(Path('state.json').read_text())\n    if state.get('contract')!=contract or state.get('nextRow')!=len(state.get('outputs',[])):\n        raise ValueError('incompatible or incomplete checkpoint')\nfor i in range(state['nextRow'],len(values)):\n    state['sum']+=values[i]\n    state['outputs'].append(state['sum'])\n    state['nextRow']=i+1\n    if mode=='interrupt' and i==2:\n        Path('state.tmp').write_text(json.dumps(state))\n        os.replace('state.tmp','state.json')\n        raise SystemExit(7)\nPath(mode+'-output.json').write_text(json.dumps(state['outputs']))\n`;
 fs.writeFileSync(path.join(root,'run.py'),source);fs.writeFileSync(path.join(root,'input.json'),'[2,3,5,7,11,13]');
 const run=mode=>spawnSync('python3',['-I','-S','run.py',mode],{cwd:root,encoding:'utf8'});
 assert.equal(run('full').status,0);assert.equal(run('interrupt').status,7);assert.equal(JSON.parse(fs.readFileSync(path.join(root,'state.json'))).nextRow,3);
 assert.equal(run('resume').status,0);assert.equal(fs.readFileSync(path.join(root,'full-output.json'),'utf8'),fs.readFileSync(path.join(root,'resume-output.json'),'utf8'));
 const checkpoint=JSON.parse(fs.readFileSync(path.join(root,'state.json')));checkpoint.contract.sourceIdentity='wrong';fs.writeFileSync(path.join(root,'state.json'),JSON.stringify(checkpoint));assert.notEqual(run('resume').status,0);
 fs.writeFileSync(path.join(root,'state.json'),'{"partial":');assert.notEqual(run('resume').status,0);
 assert.equal(fs.existsSync(path.join(root,'state.tmp')),false);
});
