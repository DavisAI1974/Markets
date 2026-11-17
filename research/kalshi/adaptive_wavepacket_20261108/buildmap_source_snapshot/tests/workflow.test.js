import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import crypto from 'node:crypto';
import { spawnSync } from 'node:child_process';
import { once } from 'node:events';
import { scanProject } from '../src/scan.js';
import { pythonGuides } from '../src/workflow.js';
import { startServer } from '../src/server.js';
import { snapshotHtml } from '../src/export.js';

const example = fs.readFileSync(new URL('./fixtures/workflow-pipeline.py', import.meta.url), 'utf8');
function fixture(t, source = example) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'buildmap-workflow-'));
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  fs.writeFileSync(path.join(root, 'workflow.py'), source);
  return root;
}
const hash = source => crypto.createHash('sha256').update(source).digest('hex');

test('Multi-stage source yields source-bound calculations, possible shared products and cautious risks without execution', t => {
  const root = fixture(t), map = scanProject(root), w = map.workflow;
  assert.equal(w.files[0].status, 'parsed');
  assert.equal(w.basis, 'static-source-syntax');
  assert.equal(w.coverage.pythonFiles,1);assert.equal(w.coverage.parsedPythonFiles,1);assert.equal(w.coverage.unreviewedPython.length,0);
  const prepare = w.calculations.find(c => c.name === 'prepare'), search = w.calculations.find(c => c.name === 'search');
  assert.deepEqual(search.inputs, ['cells', 'transforms', 'series']);
  assert.equal(prepare.source.sourceHash, hash(example));
  assert.equal(prepare.source.line, 8); assert.equal(prepare.outputs[0].summary, 'table');
  assert.equal(prepare.transformations[0].summary, "table = pd.read_csv('raw.csv')");
  assert.equal(prepare.transformations[0].source.line, 9);
  const shared = w.dataProducts.find(p => p.pathExpression === 'prepared.parquet');
  assert.equal(shared.producers[0].calculationId, prepare.id);
  assert.equal(w.calculations.find(c => c.id === shared.consumers[0].calculationId).name, 'saved_preparation');
  assert.equal(shared.compatibility, 'unknown');
  const reads = w.findings.find(f => f.type === 'potential-repeated-read');
  assert.equal(reads.confidence, 'Needs runtime evidence'); assert.equal(reads.sources.length, 2);
  assert.match(reads.impact, /Actual bytes.*unknown/);
  assert.ok(reads.reuseCues.some(c => c.expression.includes('LazyJobs')));
  assert.ok(reads.reuseCues.some(c => c.expression.includes('JobSubset')));
  assert.ok(reads.reuseCues.some(c => c.expression.includes('partner_fft_cache')));
  assert.ok(reads.reuseCues.some(c => c.expression.includes('exact_pair_reuse')));
  assert.ok(reads.reuseCues.some(c => c.expression.includes('load_restart_receipt')));
  assert.ok(w.calculations.find(c => c.name === 'saved_preparation').reuseCues.some(c => c.expression.includes('lru_cache')));
  for (const finding of w.findings) {
    assert.ok(finding.sources.every(s => s.path === 'workflow.py' && s.sourceHash === hash(example) && s.line > 0));
    assert.ok(finding.requiredVerification.length && finding.correctnessTradeoff && finding.suggestedAction);
  }
  assert.equal(map.project.counts.verified, 0); assert.equal(map.project.counts.live, 0);
  assert.deepEqual(fs.readdirSync(root), ['workflow.py']); // Top-level raising fixture was never run; no writes.
});

test('fan-out separates symbolic dimensions and literal potential iterations from jobs and directional pairs', t => {
  const w = scanProject(fixture(t)).workflow;
  const search = w.findings.find(f => f.type === 'nested-loop-fanout' && f.title.startsWith('search:'));
  assert.equal(search.workload.symbolic, 'cells × transforms × series');
  assert.equal(search.workload.potentialIterations, null);
  const literal = w.findings.find(f => f.title.startsWith('literal_dimensions:'));
  assert.equal(literal.workload.potentialIterations, '594');
  assert.equal(w.findings.filter(f => f.type === 'nested-loop-fanout').length, 2);
  for (const f of [search, literal]) {
    assert.equal(f.workload.actualJobs, null); assert.equal(f.workload.pairComparisons, null); assert.equal(f.workload.remainingJobs, null);
    assert.match(f.correctnessTradeoff, /AB\/BA/);
  }
  const ab = w.calculations.find(c => c.name === 'directional_ab');
  const ba = w.calculations.find(c => c.name === 'directional_ba');
  assert.notEqual(ab.id, ba.id); assert.deepEqual(ab.calls[0].arguments, ['a', 'b']); assert.deepEqual(ba.calls[0].arguments, ['b', 'a']);
  assert.equal(w.dataProducts.find(p => p.pathExpression === 'saved-checkpoint.json').compatibility, 'unknown');
});

test('comments and shadowed imports do not invent reads; nested bodies have their own source-only findings', t => {
  const root = fixture(t, `import pandas as pd
# pd.read_csv('fake.csv')
text = "pd.read_csv('fake.csv')"
def read(path):
    return pd.read_csv(path)
def shadow(pd):
    pd.read_csv('shadow.csv')
    pd.read_csv('shadow.csv')
def outer():
    def inner():
        open('nested.csv')
        open('nested.csv')
`);
  const w = scanProject(root).workflow;
  assert.deepEqual(w.dataProducts.map(p=>p.pathExpression), ['nested.csv']);
  const inner=w.calculations.find(c=>c.name==='outer.inner');
  assert.ok(w.findings.every(f=>f.calculationIds.every(id=>id===inner.id)));
  assert.equal(w.findings[0].confidence,'Needs runtime evidence');
  assert.equal(w.calculations.find(c=>c.name==='outer').io.length,0);
  assert.equal(w.calculations.find(c=>c.name==='outer.inner').io[0].pathExpression,'nested.csv');
  assert.ok(w.calculations.some(c => c.name === 'read'));
  assert.equal(w.calculations.some(c => ['inner', 'Reader.read'].includes(c.name)), false);
  assert.match(w.limitations.join(' '), /Dynamic|dynamic/);
});

test('loop iterator reads and else suites do not become repeated inner-body work; guards are not execution proof', t => {
  const root = fixture(t, `def run():
    for row in open('once.csv'):
        pass
    else:
        for other in range(5):
            pass
    if False:
        open('branch.csv')
    else:
        open('branch.csv')
`);
  const w = scanProject(root).workflow;
  assert.equal(w.findings.some(f => f.type === 'nested-loop-fanout'), false);
  assert.equal(w.findings.some(f => f.title.includes('once.csv')), false);
  assert.equal(w.findings.find(f => f.title.includes('branch.csv')).confidence, 'Needs runtime evidence');
});

test('literal ranges handle descending, empty and huge counts without assuming runtime execution', t => {
  const root = fixture(t, `def loops():
    for i in range(5, 0, -2):
        for j in range(0):
            work()
def huge():
    for i in range(1000000000):
        for j in range(1000000000):
            work()
`);
  const findings = scanProject(root).workflow.findings;
  assert.equal(findings.find(f => f.title.startsWith('loops:')).workload.potentialIterations, '0');
  assert.equal(findings.find(f => f.title.startsWith('huge:')).workload.potentialIterations, '1000000000000000000');
});

test('unavailable parser, parse errors and source limits preserve the free inventory and disclose unreviewed scope', t => {
  const root = fixture(t, 'def broken(:\n');
  fs.writeFileSync(path.join(root, 'large.py'), '#' + 'x'.repeat(1_000_001));
  let map = scanProject(root);
  assert.equal(map.workflow.files.find(f => f.path === 'workflow.py').status, 'parse-error');
  assert.equal(map.workflow.files.find(f => f.path === 'large.py').status, 'size-limit');
  assert.equal(map.scan.fileCount, 2); assert.deepEqual(map.workflow.findings, []);
  const result = spawnSync(process.execPath, ['--input-type=module', '-e', `import {scanProject} from './src/scan.js'; console.log(JSON.stringify(scanProject(process.argv[1])))`, root], {
    cwd: new URL('..', import.meta.url), env: { ...process.env, PATH: '/missing-buildmap-python' }, encoding: 'utf8'
  });
  assert.equal(result.status, 0, result.stderr); map = JSON.parse(result.stdout);
  assert.equal(map.workflow.files.find(f => f.path === 'workflow.py').status, 'analyzer-unavailable');
  assert.equal(map.scan.fileCount, 2);
  const sources = Array.from({ length: 65 }, (_, i) => ({ path: `${i}.py`, source: 'value = 1' }));
  const guides = new Map(sources.map(s => [s.path, { functions: [] }]));
  pythonGuides(sources, guides);
  assert.equal(guides.get('63.py').status, 'parsed'); assert.equal(guides.get('64.py').status, 'analysis-limit');
});

test('source edits invalidate calculation identities and old receipts without changing or blessing checkpoints', t => {
  const root = fixture(t);
  fs.mkdirSync(path.join(root, '.buildmap'));
  fs.writeFileSync(path.join(root, '.buildmap/evidence.json'), JSON.stringify({ files: { 'workflow.py': { status: 'verified', note: 'Recorded prior check', sourceHashes: { 'workflow.py': hash(example) } } } }));
  fs.writeFileSync(path.join(root, 'saved-checkpoint.json'), '{"source":"old","coverage":"partial"}');
  const before = scanProject(root);
  assert.equal(before.nodes.find(n => n.id === 'file:workflow.py').status, 'verified');
  fs.writeFileSync(path.join(root, 'workflow.py'), example.replace("'raw.csv'", "'new-raw.csv'"));
  const after = scanProject(root);
  assert.notEqual(after.fingerprint, before.fingerprint);
  assert.notEqual(after.workflow.calculations[0].source.sourceHash, before.workflow.calculations[0].source.sourceHash);
  assert.notEqual(after.nodes.find(n => n.id === 'file:workflow.py').status, 'verified');
  assert.equal(after.workflow.dataProducts.find(p => p.pathExpression === 'saved-checkpoint.json').compatibility, 'unknown');
  assert.equal(fs.readFileSync(path.join(root, 'saved-checkpoint.json'), 'utf8'), '{"source":"old","coverage":"partial"}');
});

test('explicit whole-source batching retains invalid and over-budget files without omitting later eligible source', () => {
  const sources=Array.from({length:70},(_,i)=>({path:`piece${i}.py`,source:`def piece_${i}():\n    return ${i}\n`}));
  sources[64].source='def broken(:\n';
  const guides=new Map(sources.map(s=>[s.path,{functions:[]}]));pythonGuides(sources,guides,{all:true});
  assert.equal(guides.get('piece64.py').status,'parse-error');assert.equal(guides.get('piece69.py').status,'parsed');
  assert.equal([...guides.values()].filter(g=>g.status==='parsed').length,69);
  const large=Array.from({length:5},(_,i)=>({path:`large${i}.py`,source:'#'+'x'.repeat(899999)+`\ndef large_${i}():\n    pass\n`}));
  const split=new Map(large.map(s=>[s.path,{functions:[]}]));pythonGuides(large,split,{all:true});
  assert.equal([...split.values()].filter(g=>g.status==='parsed').length,5);
});

test('workflow definitions remain visible in the full inventory with unsupported semantics and explicit scope', t => {
  const root=fixture(t,'def run():\n    pass\n');
  fs.writeFileSync(path.join(root,'pipeline.yml'),'jobs:\n  build: run\n');fs.writeFileSync(path.join(root,'worker.service'),'[Service]\nExecStart=python3 workflow.py\n');fs.writeFileSync(path.join(root,'project.toml'),'name="fixture"\n');
  const map=scanProject(root,{workflowAll:true});assert.equal(map.scan.fileCount,4);assert.equal(map.workflow.coverage.parsedPythonFiles,1);
  assert.equal(map.workflow.coverage.outsideAdapter.length,3);assert.ok(map.nodes.some(n=>n.files.includes('pipeline.yml')));
  assert.equal(map.workflow.scope.mode,'whole-python-inventory');assert.throws(()=>scanProject(root,{workflowAll:'yes'}),/boolean/);
});

test('live API, CLI JSON and self-contained exports carry the same risk records with read-only boundaries', async t => {
  const root = fixture(t), map = scanProject(root);
  const server = startServer({ root, port: 0 }); await once(server, 'listening');
  t.after(() => new Promise(resolve => server.close(resolve)));
  const url = `http://127.0.0.1:${server.address().port}/api/map`;
  const live = await (await fetch(url)).json(); assert.deepEqual(live.workflow, map.workflow);
  assert.equal((await fetch(url, { method: 'POST' })).status, 405);
  const result = spawnSync(process.execPath, ['src/cli.js', root, '--json'], { encoding: 'utf8' });
  assert.equal(result.status, 0, result.stderr); assert.deepEqual(JSON.parse(result.stdout).workflow, map.workflow);
  const html = snapshotHtml(map);
  assert.ok(html.includes('nested-loop-fanout')); assert.ok(html.includes('Before you run'));
  assert.equal((await fetch(url.replace('/api/map', '/workflow.py'))).status, 404);
});

test('eager and deferred comprehensions expose axes and filters without claiming jobs, pairs or generator execution', t => {
  const root = fixture(t, `raise RuntimeError('never execute this fixture')
def build_jobs(cells, transforms, series):
    return [(cell, tx, x) for cell in cells for tx in transforms for x in series if eligible(x)]
def defer(cells, series):
    return (open('deferred.csv') for cell in cells for x in series)
def formats():
    pairs = {(x, y) for x in range(2) for y in range(3) if False}
    return {(x, y): x for x in range(2) for y in range(x)}
`);
  const w = scanProject(root).workflow;
  const findings = w.findings.filter(f => f.type === 'comprehension-fanout');
  assert.equal(findings.length, 4);
  const eager = findings.find(f => f.title.startsWith('build_jobs:'));
  assert.equal(eager.workload.symbolic, 'cells × transforms × series');
  assert.equal(eager.workload.evaluation, 'eager-container');
  assert.deepEqual(eager.workload.filters, ['eligible(x)']);
  assert.equal(eager.workload.potentialIterations, null);
  const generator = findings.find(f => f.title.startsWith('defer:'));
  assert.equal(generator.workload.evaluation, 'deferred-expression');
  assert.match(generator.impact, /may never be consumed/);
  assert.equal(w.dataProducts.some(p => p.pathExpression === 'deferred.csv'), false);
  assert.equal(w.calculations.find(c => c.name === 'defer').calls.some(c => c.target === 'open'), false);
  assert.equal(findings.find(f => f.title.includes('SetComp')).workload.potentialIterations, '6');
  assert.equal(findings.find(f => f.title.includes('DictComp')).workload.potentialIterations, null);
  for (const f of findings) {
    assert.equal(f.workload.actualJobs, null); assert.equal(f.workload.pairComparisons, null); assert.equal(f.workload.remainingJobs, null);
    assert.ok(f.sources[0].sourceHash && f.requiredVerification.length);
  }
});

test('direct class methods expose workflow syntax while nested bodies, inheritance and dispatch remain unproven', t => {
  const root = fixture(t, `class Pipeline:
    def run(self, stages, days):
        def hidden():
            open('nested.csv')
            open('nested.csv')
        for stage in stages:
            for day in days:
                getattr(self, stage)(day)
        return self.result
    @staticmethod
    def jobs():
        return [(x,y) for x in range(2) for y in range(3)]
    async def wait(self):
        return await self.pending()
    def stream(self):
        yield from self.saved
`);
  const w = scanProject(root).workflow;
  assert.deepEqual(w.calculations.map(c => c.name), ['Pipeline.run', 'Pipeline.jobs', 'Pipeline.wait', 'Pipeline.stream', 'Pipeline.run.hidden']);
  assert.ok(w.calculations.slice(0,4).every(c => c.scopeKind === 'method'));
  assert.equal(w.calculations[4].scopeKind,'nested-function');
  assert.deepEqual(w.calculations[0].inputs, ['self', 'stages', 'days']);
  assert.equal(w.dataProducts.length, 1);
  assert.equal(w.dataProducts[0].consumers[0].calculationId,w.calculations[4].id);
  assert.equal(w.calculations[0].io.length,0);
  assert.ok(w.findings.some(f => f.title.startsWith('Pipeline.run:')));
  assert.equal(w.findings.find(f => f.title.startsWith('Pipeline.jobs:')).workload.potentialIterations, '6');
  assert.match(w.limitations.join(' '), /inheritance\/dispatch/);
  assert.equal(w.calculations[0].calls.some(c => c.resolution !== 'unresolved-source-reference'), false);
  assert.equal(w.calculations.find(c => c.name === 'Pipeline.stream').generator, true);
});

test('eager comprehension reads are potential repetition; imported range names cannot ground counts', t => {
  const root = fixture(t, `from custom import range
def build():
    return [open('read.csv') for x in range(2) for y in range(3)]
`);
  const w = scanProject(root).workflow;
  assert.equal(w.findings.find(f => f.type === 'comprehension-fanout').workload.potentialIterations, null);
  assert.equal(w.findings.find(f => f.type === 'potential-repeated-read').confidence, 'Needs runtime evidence');
});

test('explicit Python review scope retains all free files and imports and discloses unselected/missing files', t => {
  const root = fixture(t, 'import other\ndef work():\n    return 1\n');
  fs.writeFileSync(path.join(root, 'other.py'), 'def other():\n    return 2\n');
  const full = scanProject(root), selected = scanProject(root, { workflowFiles: ['workflow.py', 'missing.py'] });
  assert.deepEqual(selected.nodes.map(n => ({id:n.id,status:n.status,files:n.files})), full.nodes.map(n => ({id:n.id,status:n.status,files:n.files})));
  assert.deepEqual(selected.edges, full.edges);
  assert.equal(selected.workflow.files.find(f => f.path === 'other.py').status, 'not-selected');
  assert.equal(selected.workflow.files.find(f => f.path === 'workflow.py').status, 'parsed');
  assert.deepEqual(selected.workflow.scope.unavailableFiles, ['missing.py']);
  assert.equal(selected.workflow.scope.mode, 'selected-files');
  assert.equal(selected.workflow.calculations.some(c => c.name === 'other'), false);
  assert.notEqual(selected.fingerprint, full.fingerprint);
  assert.throws(() => scanProject(root, {workflowFiles:'workflow.py'}), /array/);
});

test('source-call links connect calculations across modules without inventing execution order or data propagation', t => {
  const root = fixture(t, `from stages.prepare import build as prepare
import stages.transform as transforms
from stages.transform import finish as publish
def run(source):
    prepared = prepare(source)
    measured = transforms.measure(prepared)
    return publish(measured)
`);
  fs.mkdirSync(path.join(root, 'stages'));
  fs.writeFileSync(path.join(root, 'stages/prepare.py'), 'def build(source):\n    return source + 1\n');
  fs.writeFileSync(path.join(root, 'stages/transform.py'), 'def measure(value):\n    return value * 2\ndef finish(value):\n    return value\n');
  const map = scanProject(root), w = map.workflow;
  assert.equal(w.relationships.length, 3);
  const names = new Map(w.calculations.map(c => [c.id,c.name]));
  assert.deepEqual(w.relationships.map(r => names.get(r.to)), ['build','measure','finish']);
  assert.deepEqual(w.relationships[1].arguments, ['prepared']);
  for (const r of w.relationships) {
    assert.equal(r.kind, 'candidate-source-call'); assert.equal(r.execution, 'unobserved'); assert.equal(r.dataFlow, 'unverified');
    assert.equal(r.source.path, 'workflow.py'); assert.ok(r.targetSource.sourceHash); assert.ok(r.importSource.line > 0);
  }
  assert.ok(map.nodes.every(n => !['computing','verified','live'].includes(n.status)));
  assert.equal(map.edges.some(e => e.type === 'candidate-source-call'), false);
  assert.equal(w.callCoverage.totalCallSites, 3); assert.equal(w.callCoverage.unresolvedCallSites, 0);
});

test('unique same-file and relative imports link source declarations; dynamic method dispatch stays unresolved', t => {
  const root = fixture(t, `def helper(value):
    return value
def run(value):
    return helper(value)
class Runner:
    def perform(self, value):
        return self.helper(value)
    def helper(self, value):
        return value
`);
  // A method with the same name conservatively prevents a bare-name match.
  assert.equal(scanProject(root).workflow.relationships.length, 0);
  fs.writeFileSync(path.join(root,'workflow.py'), 'def helper(value):\n    return value\ndef run(value):\n    return helper(value)\n');
  let w = scanProject(root).workflow;
  assert.equal(w.relationships.length, 1); assert.equal(w.relationships[0].basis, 'unique-same-file-declaration');
  fs.mkdirSync(path.join(root,'pkg'));
  fs.writeFileSync(path.join(root,'pkg/entry.py'), 'from .worker import execute as work\ndef start(value):\n    return work(value)\n');
  fs.writeFileSync(path.join(root,'pkg/worker.py'), 'def execute(value):\n    return value\n');
  w = scanProject(root).workflow;
  assert.ok(w.relationships.some(r => r.source.path === 'pkg/entry.py' && r.targetSource.path === 'pkg/worker.py'));
});

test('shadowed, reassigned, duplicated, decorated, mutated and star-imported targets do not gain source links', t => {
  const root = fixture(t);
  fs.writeFileSync(path.join(root, 'worker.py'), 'def execute(value):\n    return value\n');
  const cases = [
    'import worker\ndef run(worker):\n    return worker.execute(1)\n',
    'import worker\nworker = replacement\ndef run():\n    return worker.execute(1)\n',
    'import worker\nworker.execute = replacement\ndef run():\n    return worker.execute(1)\n',
    'import worker as task\nimport another as task\ndef run():\n    return task.execute(1)\n',
    'from worker import *\ndef run():\n    return execute(1)\n',
    'def helper(value):\n    return value\ndef run(helper):\n    return helper(1)\n'
  ];
  for (const source of cases) {
    fs.writeFileSync(path.join(root,'workflow.py'), source);
    assert.deepEqual(scanProject(root).workflow.relationships, [], source);
  }
  fs.writeFileSync(path.join(root,'workflow.py'), 'from worker import execute\ndef run():\n    return execute(1)\n');
  fs.writeFileSync(path.join(root,'worker.py'), '@decorate\ndef execute(value):\n    return value\n');
  const w=scanProject(root).workflow;
  assert.deepEqual(w.relationships, []); assert.match(w.unresolvedCalls[0].reason,/undecorated/);
});

test('ambiguous and unselected modules remain visible without guessed targets or expanded review scope', t => {
  const root = fixture(t, 'value=1\n');
  fs.mkdirSync(path.join(root,'pkg'));
  fs.writeFileSync(path.join(root,'pkg/entry.py'), 'import worker\ndef run():\n    return worker.execute(1)\n');
  fs.writeFileSync(path.join(root,'worker.py'), 'def execute(value):\n    return value\n');
  fs.writeFileSync(path.join(root,'pkg/worker.py'), 'def execute(value):\n    return value\n');
  let w=scanProject(root).workflow;
  assert.deepEqual(w.relationships, []); assert.equal(w.unresolvedCalls[0].candidateFiles.length,2);
  assert.match(w.unresolvedCalls[0].reason,/Multiple/);
  fs.rmSync(path.join(root,'worker.py'));
  w=scanProject(root,{workflowFiles:['pkg/entry.py']}).workflow;
  assert.deepEqual(w.relationships, []); assert.match(w.unresolvedCalls[0].reason,/unselected/);
  assert.equal(w.files.find(f=>f.path==='pkg/worker.py').status,'not-selected');
});
