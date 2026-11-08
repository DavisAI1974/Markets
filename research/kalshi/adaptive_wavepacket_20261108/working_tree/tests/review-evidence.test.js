import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import crypto from 'node:crypto';
import { evaluateAnalysis, readAnalysis } from '../src/review-evidence.js';
import { scanProject } from '../src/scan.js';

const hash = x => crypto.createHash('sha256').update(x).digest('hex');
const contract = (semantics = { kind: 'independent' }) => ({ sourceIdentity: 'source:1', calculationIdentity: 'formula:1', schemaIdentity: 'schema:1', axisIdentity: 'ordered-rows:1', availabilityIdentity: 'missing-values:1', semantics });
const rows = (start,end) => ({ start,end });
const product = () => ({ id: 'table', path: 'table.parquet', required: { contract: contract(), rows: [rows(0,10)], columns: ['a','b'] }, available: [] });
const region = (start,end,columns) => ({ rows: rows(start,end), columns });
const available = regions => ({ id: 'saved', contract: contract(), regions });
const analyze = products => evaluateAnalysis({ version: 1, products });
const identity = () => ({ sourceIdentity: 'input:1', calculationIdentity: 'formula:1', workloadIdentity: 'fixture:1', environmentIdentity: 'machine:1', metricScopeIdentity: 'process-normalized-cpu:1' });
const runtime = id => ({ id, identity: identity(), counters: { eligibleJobs: '90071992547409930', completedJobs: 0, pairComparisons: '123456789012345678901234' }, metrics: { elapsedSeconds: 0, cpuUtilizationPercent: 0 }, bindings: { 'run.json': 'a'.repeat(64) } });
const current = () => ({ current: true, reason: 'matching test receipt' });
function fixture(t) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(),'buildmap-analysis-'));
  t.after(() => fs.rmSync(root, { recursive:true, force:true }));
  fs.mkdirSync(path.join(root,'.buildmap'));
  return root;
}

test('coverage unions per-column intervals, preserves holes and counts exact cells without zero-fill', () => {
  const p = product(); p.available = [available([region(0,4,['a']), region(3,7,['a']), region(9,20,['a']), region(0,10,['b'])])];
  const reviewed = analyze([p]).products[0];
  assert.equal(reviewed.status, 'partial-under-supplied-contracts');
  assert.equal(reviewed.requiredCells,'20'); assert.equal(reviewed.reusableCells,'18'); assert.equal(reviewed.missingCells,'2');
  assert.deepEqual(reviewed.missing,[{ column:'a', rows:rows(7,9) }]);
  assert.deepEqual(reviewed.extension,[{ column:'a', rows:rows(7,9), inputRows:rows(7,9) }]);
  assert.equal(reviewed.compatibleSources[0].freshness.status,'unbound'); assert.equal(reviewed.verified,false);
});

test('coverage excludes all incompatible identities, semantics, extra policy fields and stale receipts', () => {
  for (const key of ['sourceIdentity','calculationIdentity','schemaIdentity','axisIdentity','availabilityIdentity','semantics','extraPolicy']) {
    const p = product(), a = available([region(0,10,['a','b'])]);
    a.contract[key] = key === 'semantics' ? {kind:'stateful'} : 'different'; p.available = [a];
    const review = analyze([p]).products[0];
    assert.equal(review.reusableCells,'0',key); assert.equal(review.status,'incompatible-or-unavailable');
  }
  const p = product(); p.available = [{...available([region(0,10,['a','b'])]),bindings:{'receipt.json':'a'.repeat(64)}}];
  const review = analyze([p]).products[0]; assert.equal(review.reusableCells,'0'); assert.match(review.excludedSources[0].reason,/stale/);
});

test('rolling extension adds declared causal overlap, while stateful extension requires domain boundary state', () => {
  const p = product(); p.required.contract = contract({kind:'rolling',lookbackRows:3,originRow:0});
  p.available = [{...available([region(0,7,['a','b'])]),contract:p.required.contract}];
  const r = analyze([p]).products[0];
  assert.deepEqual(r.extension.map(x => x.inputRows),[rows(4,10),rows(4,10)]);
  p.required.contract = contract({kind:'stateful'}); p.available[0].contract = p.required.contract;
  const state = analyze([p]).products[0]; assert.equal(state.extensionStatus,'blocked-needs-domain-boundary-state'); assert.equal(state.extension[0].inputRows,null);
  p.required.contract = contract({kind:'rolling',lookbackRows:3});
  assert.match(analyze([p]).diagnostics[0].message,/originRow/);
});

test('empty inventories, missing contracts, invalid coordinates, duplicate columns and duplicate IDs stay explicit', () => {
  assert.equal(analyze([product()]).products[0].status,'absent');
  for (const modify of [p => delete p.available,p => delete p.required.contract.sourceIdentity,p => p.required.rows=[rows(2,2)],p => p.required.rows=[rows(-1,2)],p => p.required.rows=[rows(0,Number.MAX_SAFE_INTEGER+1)],p => p.required.columns=['a','a']]) {
    const p=product(); modify(p); const r=analyze([p]); assert.equal(r.products.length,0); assert.equal(r.diagnostics.length,1);
  }
  const r=analyze([product(),product(),product()]); assert.equal(r.products.length,0); assert.match(r.diagnostics[0].message,/duplicate/);
});

test('large row spaces retain exact arithmetic and disjoint required ranges never credit outside rows', () => {
  const p=product(); p.required.rows=[rows(0,Number.MAX_SAFE_INTEGER)];
  assert.equal(analyze([p]).products[0].requiredCells,'18014398509481982');
  p.required.rows=[rows(0,2),rows(5,8)]; p.available=[available([region(1,6,['a','b'])])];
  assert.deepEqual(analyze([p]).products[0].missing,[{column:'a',rows:rows(0,1)},{column:'a',rows:rows(6,8)},{column:'b',rows:rows(0,1)},{column:'b',rows:rows(6,8)}]);
});

test('runtime separates jobs and directional pairs, preserves exact huge counts and distinguishes unknown from zero', () => {
  const r=evaluateAnalysis({version:1,runtime:[runtime('one')]},[],current).observations[0];
  assert.equal(r.counters.eligibleJobs,'90071992547409930'); assert.equal(r.counters.completedJobs,'0'); assert.equal(r.counters.remainingJobs,null);
  assert.equal(r.counters.pairComparisons,'123456789012345678901234'); assert.equal(r.metrics.elapsedSeconds,0); assert.equal(r.metrics.peakMemoryBytes,null);
  assert.equal(r.freshness.status,'current'); assert.equal(r.execution,'reported-not-observed-by-buildmap');
});

test('runtime rejects unsafe counts, malformed metrics and inconsistent explicitly declared accounting', () => {
  for (const modify of [r=>r.counters.reads=-1,r=>r.counters.reads=1.5,r=>r.counters.reads=Number.MAX_SAFE_INTEGER+1,r=>r.metrics.cpuUtilizationPercent=101,r=>r.metrics.elapsedSeconds=Infinity,r=>r.metrics.peakMemoryBytes=1.5,r=>r.counters=[],r=>r.accounting='eligible=completed+remaining']) {
    const r=runtime('bad');modify(r); const result=evaluateAnalysis({version:1,runtime:[r]},[],current);assert.equal(result.observations.length,0);assert.equal(result.diagnostics.length,1);
  }
});

test('comparable observations use signed exact differences; mismatched identities, stages and stale bindings refuse comparison', () => {
  const before=runtime('before'),after=runtime('after');after.baselineId='before'; after.counters.eligibleJobs='90071992547409929'; after.metrics.elapsedSeconds=2;
  const evaluate=()=>evaluateAnalysis({version:1,runtime:[before,after]},[],current);
  let diff=evaluate().comparisons[0];assert.equal(diff.status,'comparable-reported-observations');assert.equal(diff.counterDifferences.eligibleJobs,'-1');assert.equal(diff.counterDifferences.remainingJobs,null);assert.equal(diff.metricDifferences.elapsedSeconds,2);
  for (const key of Object.keys(identity())) {after.identity[key]='mismatch';assert.equal(evaluate().comparisons[0].status,'refused');after.identity=identity();}
  after.stageId='other';assert.equal(evaluate().comparisons[0].status,'refused');delete after.stageId;
  delete after.bindings;assert.equal(evaluate().comparisons[0].status,'refused');
  after.baselineId='missing';assert.match(evaluate().comparisons[0].reason,/Baseline missing/);
});

test('declared stages reveal missing dependencies, cycles and competing producers without inventing a runtime schedule', () => {
  const result=evaluateAnalysis({version:1,products:[product()],stages:[{id:'a',dependsOn:['b'],outputs:['table']},{id:'b',dependsOn:['a','missing'],outputs:['table'],checkpointProducts:['unknown']} ]});
  assert.equal(result.stages.length,2); assert.equal(result.stages[0].execution,'unobserved');
  assert.ok(result.diagnostics.some(d=>/Cycle/.test(d.message)));assert.ok(result.diagnostics.some(d=>/Multiple declared producers/.test(d.message)));assert.ok(result.diagnostics.some(d=>/dependency missing/.test(d.message)));assert.ok(result.diagnostics.some(d=>/Product unknown/.test(d.message)));
  const unordered=evaluateAnalysis({version:1,products:[product()],stages:[{id:'produce',outputs:['table']},{id:'consume',inputs:['table']}]});
  assert.match(unordered.diagnostics[0].message,/predecessor set/);
});

test('local reader binds small receipts, invalidates on edits, stays read-only and never blesses component proof', t => {
  const root=fixture(t), p=product();
  fs.writeFileSync(path.join(root,'run.json'),'record one');
  const r=runtime('observed');r.bindings={'run.json':hash('record one')};
  fs.writeFileSync(path.join(root,'.buildmap/analysis.json'),JSON.stringify({version:1,products:[p],runtime:[r]}));
  const before=scanProject(root);assert.equal(before.workflow.review.observations[0].freshness.status,'current');
  assert.equal(before.project.counts.verified,0);
  fs.writeFileSync(path.join(root,'run.json'),'record two');
  const after=scanProject(root);assert.equal(after.workflow.review.observations[0].freshness.status,'stale-or-unavailable');assert.notEqual(after.fingerprint,before.fingerprint);
  assert.equal(fs.readFileSync(path.join(root,'run.json'),'utf8'),'record two');
});

test('optional analysis read refuses malformed/oversized/outside files and receipts; absence remains optional', t => {
  const root=fixture(t), file=path.join(root,'.buildmap/analysis.json');assert.equal(readAnalysis(root,[]).status,'not-supplied');
  fs.writeFileSync(file,'{');assert.equal(readAnalysis(root,[]).status,'invalid');
  fs.writeFileSync(file,' '.repeat(1_000_001));assert.equal(readAnalysis(root,[]).status,'invalid');
  const outside=fixture(t);fs.writeFileSync(path.join(outside,'outside.json'),'{}');fs.unlinkSync(file);fs.symlinkSync(path.join(outside,'outside.json'),file);assert.equal(readAnalysis(root,[]).status,'invalid');fs.unlinkSync(file);
  const r=runtime('unsafe');r.bindings={'../outside.json':'a'.repeat(64)};
  fs.writeFileSync(file,JSON.stringify({version:1,runtime:[r]}));assert.equal(readAnalysis(root,[]).observations[0].freshness.status,'stale-or-unavailable');
  fs.writeFileSync(path.join(root,'large-receipt.json'),' '.repeat(1_000_001));r.bindings={'large-receipt.json':'a'.repeat(64)};
  fs.writeFileSync(file,JSON.stringify({version:1,runtime:[r]}));
  assert.match(readAnalysis(root,[]).observations[0].freshness.files[0].reason,/no larger than/);
});

test('source resource/restart review recognizes guards, bounded queues, releases and pool controls without executing the project', t => {
  const root=fixture(t);fs.writeFileSync(path.join(root,'flow.py'),`from collections import deque
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import numpy as np
raise RuntimeError('never execute')
def run(jobs, identity):
    results = []
    bounded = deque(maxlen=2)
    pool = ThreadPoolExecutor(max_workers=2)
    if Path('checkpoint.json').exists():
        if identity.schema == 'v1':
            state = Path('checkpoint.json').read_text()
    for job in jobs:
        future = pool.submit(job)
        results.append(future.result())
        bounded.append(job)
    results.clear()
    np.save('checkpoint.npy', results)
    return results
`);
  const w=scanProject(root).workflow,c=w.calculations.find(c=>c.name==='run');
  assert.ok(w.findings.some(f=>f.type==='checkpoint-compatibility'));assert.ok(w.findings.some(f=>f.type==='sequencing-barrier'));
  const growth=w.findings.filter(f=>f.type==='collection-retention');assert.equal(growth.length,1);assert.match(growth[0].impact,/Release-call syntax/);
  assert.ok(c.facts.some(f=>f.kind==='worker-pool'&&f.workersExpression==='2'));
  const checkpoint=w.checkpoints.find(c=>c.operation==='load');assert.equal(checkpoint.guards.length,2);assert.equal(checkpoint.identityComparisons.length,1);assert.equal(checkpoint.compatibility,'unverified');
  assert.equal(w.checkpoints.filter(c=>c.literalPath==='checkpoint.npy'&&c.operation==='save').length,1);
  assert.ok(w.findings.every(f=>f.sources.every(s=>s.sourceHash&&s.line>0)));assert.equal(fs.existsSync(path.join(root,'checkpoint.npy')),false);
});

test('coverage distinguishes parsed, excluded, invalid, oversized and other-language inventory without claiming complete workflow analysis', t => {
  const root=fixture(t);
  for(const [name,source] of Object.entries({'good.py':'def run():\n    return 1\n','not-selected.py':'def skip():\n    pass\n','broken.py':'def invalid(:','large.py':'#'.repeat(1_000_001),'launch.sh':'# syntax only, never execute\n'}))fs.writeFileSync(path.join(root,name),source);
  const map=scanProject(root,{workflowFiles:['good.py','broken.py','large.py']}), c=map.workflow.coverage;
  assert.equal(c.inventoryFiles,5);assert.equal(c.pythonFiles,4);assert.equal(c.parsedPythonFiles,1);
  assert.deepEqual(c.statuses,{'not-selected':1,'parse-error':1,parsed:1,'size-limit':1});
  assert.deepEqual(c.outsideAdapter.map(f=>f.path),['launch.sh']);assert.equal(c.unreviewedPython.length,3);
  assert.match(c.boundary,/Ignored.*may be absent/);assert.ok(c.inventoryMode);
  assert.equal(map.project.counts.verified,0);
});

test('reported observations resolve explicit or stage calculation references; ambiguity and stale hashes never guess a target', () => {
  const source={path:'flow.py',sourceHash:'b'.repeat(64),line:1,column:1};
  const calculations=[{id:'calc-one',name:'run',source},{id:'calc-two',name:'other',source:{...source,line:3}}];
  const before=runtime('before'),after=runtime('after');after.baselineId='before';
  before.stageId=after.stageId='run';after.calculation={path:'flow.py',name:'run',sourceHash:source.sourceHash};
  const doc={version:1,stages:[{id:'run',calculation:{path:'flow.py',name:'run'}}],runtime:[before,after]};
  let review=evaluateAnalysis(doc,calculations,current);
  assert.equal(review.observations[0].calculationMatch.basis,'declared-stage-calculation');
  assert.equal(review.observations[1].calculationMatch.basis,'explicit-observation-reference');
  assert.deepEqual(review.observations[1].calculationMatch.source,source);assert.equal(review.comparisons[0].status,'comparable-reported-observations');
  after.calculation.sourceHash='c'.repeat(64);review=evaluateAnalysis(doc,calculations,current);
  assert.equal(review.observations[1].calculationMatch.status,'stale-source');assert.equal(review.observations[1].calculationMatch.source,null);assert.equal(review.comparisons[0].status,'refused');
  delete after.calculation.sourceHash;after.calculation.name='other';assert.equal(evaluateAnalysis(doc,calculations,current).comparisons[0].status,'refused');
  after.calculation.name='run';review=evaluateAnalysis(doc,[...calculations,calculations[0]],current);
  assert.equal(review.observations[1].calculationMatch.status,'unresolved');assert.equal(review.observations[1].calculationMatch.calculationId,null);
  after.calculation.name='absent';review=evaluateAnalysis(doc,calculations,current);assert.equal(review.observations[1].calculationMatch.source,null);
});
