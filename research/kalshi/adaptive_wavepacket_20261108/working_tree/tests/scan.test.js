import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import crypto from 'node:crypto';
import { scanProject, resolveStatus } from '../src/scan.js';

function fixture() {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'buildmap-scan-'));
  fs.mkdirSync(path.join(root, '.buildmap'));
  fs.mkdirSync(path.join(root, 'src'));
  fs.writeFileSync(path.join(root, 'README.md'), '# Demo\n\nDemo turns input into output.');
  return root;
}

test('shows manifest pieces before their files exist', () => {
  const root = fixture();
  fs.writeFileSync(path.join(root, '.buildmap', 'project.json'), JSON.stringify({
    name: 'Demo', components: [{ id:'engine', name:'Engine', files:['src/engine.js'] }]
  }));
  const map = scanProject(root);
  const engine = map.nodes.find(n => n.id === 'engine');
  assert.equal(engine.status, 'planned');
  assert.deepEqual(engine.presentFiles, []);
});

test('lights files up from coded to connected when code wiring appears', () => {
  const root = fixture();
  fs.writeFileSync(path.join(root, 'src', 'a.js'), 'export const a = 1;\n');
  fs.writeFileSync(path.join(root, 'src', 'b.js'), "import { a } from './a.js'; export const b = a + 1;\n");
  const map = scanProject(root);
  const a = map.nodes.find(n => n.files.includes('src/a.js'));
  const b = map.nodes.find(n => n.files.includes('src/b.js'));
  assert.equal(a.status, 'connected');
  assert.equal(b.status, 'connected');
  assert.ok(map.edges.some(e => e.from === a.id && e.to === b.id));
});

test('explicit evidence can advance but never downgrade a discovered state', () => {
  assert.equal(resolveStatus({ base:'connected', evidence:'verified' }), 'verified');
  assert.equal(resolveStatus({ base:'connected', evidence:'coded' }), 'connected');
});

test('README gives brownfield intent without requiring a manifest', () => {
  const root = fixture();
  fs.writeFileSync(path.join(root, 'src', 'main.js'), 'export const main = true;\n');
  const map = scanProject(root);
  assert.equal(map.project.intent.source, 'README.md');
  assert.match(map.project.intent.text, /input into output/);
});

function write(root, rel, text) {
  fs.mkdirSync(path.dirname(path.join(root, rel)), { recursive: true });
  fs.writeFileSync(path.join(root, rel), typeof text === 'string' ? text : JSON.stringify(text));
}
function planned(root, components) { write(root, '.buildmap/project.json', { components }); }
function node(map, id) { return map.nodes.find(n => n.id === id); }

test('code guide explains parsed function inputs, returns and calls without executing source or confusing nested bodies', t => {
  const root = fixture(); t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  write(root, 'src/engine.js', `throw new Error('Mapping must never execute this module');
function format(value) { return value * 2; }
export { format as present };
export function outer({amount} = {}, ...rest) {
  function format(value) { return value + 1; }
  const callback = () => hiddenCall();
  const example = 'function invented() { fakeCall(); }';
  if (amount) return { total: format(amount), note: example };
  return service['save'](...rest);
}
export const echo = input => ({ value: input.amount + 1 });
function unique() { return echo({ amount: 7 }); }
function bigintKey(input) { return service[1n](input); }
`);
  const map = scanProject(root), n = map.nodes.find(n => n.files.includes('src/engine.js'));
  const file = n.codeGuide.files[0]; assert.equal(file.status, 'parsed'); assert.equal(file.sourceHash, n.sourceHashes['src/engine.js']);
  assert.deepEqual(file.functions.map(f => f.name), ['format', 'outer', 'echo', 'unique', 'bigintKey']);
  assert.equal(file.functions[0].exported, true);
  const outer = file.functions[1]; assert.deepEqual(outer.parameters, ['object fields: amount (default: an object)', 'remaining arguments in rest']);
  assert.deepEqual(outer.calls.map(c => c.target), ['format', "service['save']"]);
  assert.deepEqual(outer.calls[0].arguments, ['the value at amount']);
  assert.deepEqual(outer.calls[1].arguments, ['spread values from the value at rest']);
  assert.ok(outer.calls.every(c => c.resolution === 'unresolved-source-reference'));
  assert.equal(outer.conditions, 1); assert.equal(outer.throws, 0); assert.equal(outer.line, 4);
  assert.equal(outer.returns.length, 2); assert.equal(outer.returns[0].fields[0].name, 'total');
  assert.equal(file.functions[3].calls[0].resolution, 'same-file-function');
  assert.equal(file.functions[3].calls[0].targetLocation.line, 11);
  assert.equal(file.functions[4].calls[0].target, 'service[1n]');
  assert.match(file.functions[2].returns[0].fields[0].summary, /input.amount/);
  assert.equal(n.status, 'coded'); assert.equal(map.project.counts.verified, 0); assert.equal(map.project.counts.live, 0);
  assert.ok(n.codeGuide.limitations.some(s => s.includes('not runtime order')));
});

test('code guide discloses unsupported, parse-failed, large and missing files while retaining complete piece scope', t => {
  const root = fixture(); t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  write(root, 'src/typed.ts', 'export const fn = (x: number) => x;');
  write(root, 'src/broken.js', 'export function {');
  write(root, 'src/large.js', '//'+ 'x'.repeat(1_000_001));
  write(root, 'src/empty.cjs', 'module.exports = 7;');
  planned(root, [{ id: 'all', files: ['src/typed.ts', 'src/broken.js', 'src/large.js', 'src/empty.cjs', 'src/missing.js'] }]);
  const n = node(scanProject(root), 'all');
  assert.deepEqual(n.codeGuide.files.map(f => f.status), ['unsupported', 'parse-error', 'size-limit', 'parsed', 'missing']);
  assert.ok(n.codeGuide.files.every(f => f.functions.length === 0));
  assert.equal(n.codeGuide.files.at(-1).sourceHash, null); assert.equal(n.status, 'planned');
  assert.deepEqual(n.missingFiles, ['src/missing.js']);
});

test('code explanations follow source edits, share source identity and cannot keep an earlier receipt accepted', t => {
  const root = fixture(); t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  write(root, 'src/main.js', 'export function first(value) { return value; }');
  planned(root, [{ id: 'main', files: ['src/main.js'] }]);
  const first = scanProject(root);
  write(root, '.buildmap/evidence.json', { components: { main: { status: 'verified', note: 'Earlier check.', sourceHashes: node(first, 'main').sourceHashes } } });
  const bound = scanProject(root); assert.equal(node(bound, 'main').status, 'verified');
  write(root, 'src/main.js', 'export async function second(value) { return await fetch(value); }');
  const changed = scanProject(root), n = node(changed, 'main');
  assert.notEqual(changed.fingerprint, bound.fingerprint); assert.equal(n.status, 'coded'); assert.equal(n.evidenceAssessment.accepted, false);
  const guide = n.codeGuide.files[0]; assert.equal(guide.functions[0].name, 'second'); assert.equal(guide.functions[0].async, true);
  assert.equal(guide.sourceHash, n.sourceHashes['src/main.js']); assert.equal(guide.functions[0].calls[0].target, 'fetch');
  assert.match(guide.functions[0].returns[0].summary, /awaited result.*calling fetch/);
});

test('planned dependencies are visible but cannot establish a code connection', () => {
  const root = fixture();
  write(root, 'src/a.js', 'export const a = 1;'); write(root, 'src/b.js', 'export const b = 1;');
  planned(root, [{ id: 'a', files: ['src/a.js'] }, { id: 'b', files: ['src/b.js'], dependsOn: ['a', 'missing'] }]);
  const map = scanProject(root);
  assert.equal(node(map, 'b').status, 'coded');
  assert.ok(map.edges.some(e => e.type === 'planned' && !e.observed));
  assert.ok(map.gaps.some(g => g.kind === 'unknown-dependency'));
  assert.ok(map.gaps.some(g => g.kind === 'unobserved-dependency'));
});

test('manifest status and status-only evidence cannot manufacture verification', () => {
  const root = fixture(); write(root, 'src/a.js', 'export const a = 1;');
  planned(root, [{ id: 'a', files: ['src/a.js'], status: 'live' }]);
  assert.equal(node(scanProject(root), 'a').status, 'coded');
  write(root, '.buildmap/evidence.json', { components: { a: { status: 'verified' } } });
  const map = scanProject(root);
  assert.equal(node(map, 'a').status, 'coded');
  assert.ok(map.gaps.some(g => g.kind === 'unsupported-evidence'));
});

test('partial implementation cannot be hidden by an explicit proof claim', () => {
  const root = fixture(); write(root, 'src/a.js', 'export const a = 1;');
  planned(root, [{ id: 'a', files: ['src/a.js', 'src/missing.js'] }]);
  write(root, '.buildmap/evidence.json', { components: { a: { status: 'live', note: 'Old deployment.' } } });
  const n = node(scanProject(root), 'a');
  assert.equal(n.status, 'planned'); assert.equal(n.implementation, 'partial');
  assert.deepEqual(n.missingFiles, ['src/missing.js']); assert.equal(n.evidenceAssessment.accepted, false);
});

test('source-bound receipts become stale on edits; content changes refresh the fingerprint', () => {
  const root = fixture(); write(root, 'src/a.js', 'export const a = 1;');
  planned(root, [{ id: 'a', files: ['src/a.js'] }]);
  const before = scanProject(root);
  write(root, '.buildmap/evidence.json', { components: { a: { status: 'verified', command: 'node --test', sourceHashes: node(before, 'a').sourceHashes } } });
  const proved = scanProject(root); assert.equal(node(proved, 'a').status, 'verified');
  assert.equal(node(proved, 'a').evidenceAssessment.binding, 'current');
  assert.equal(node(proved, '__mission__').status, 'planned');
  write(root, 'src/a.js', 'export const a = 2;');
  const after = scanProject(root); assert.notEqual(after.fingerprint, proved.fingerprint);
  assert.equal(node(after, 'a').status, 'coded'); assert.equal(node(after, 'a').evidenceAssessment.binding, 'stale');
});

test('unbound explicit receipts remain supported and disclose unknown freshness', () => {
  const root = fixture(); write(root, 'src/a.js', 'export const a = 1;');
  write(root, '.buildmap/evidence.json', { files: { 'src/a.js': { status: 'verified', note: 'Behavior check passed.' } } });
  const n = node(scanProject(root), 'file:src/a.js');
  assert.equal(n.status, 'verified'); assert.equal(n.evidenceAssessment.binding, 'unbound');
});

test('HTML, CSS, and explicitly declared config files count as implementation', () => {
  const root = fixture();
  write(root, 'public/index.html', '<script src="./app.js"></script><link rel="stylesheet" href="./styles.css">');
  write(root, 'public/app.js', 'export const app = 1;'); write(root, 'public/styles.css', 'body {}'); write(root, 'config.json', '{}');
  planned(root, [{ id: 'ui', files: ['public/index.html', 'public/app.js', 'public/styles.css', './config.json', 'config.json'] }]);
  const n = node(scanProject(root), 'ui');
  assert.equal(n.implementation, 'complete'); assert.equal(n.status, 'connected'); assert.equal(n.files.length, 4);
});

test('ignores JS import examples in comments/strings and discovers re-exports and TS emitted filenames', () => {
  const root = fixture(); write(root, 'src/a.ts', 'export const a = 1;');
  write(root, 'src/unused.js', 'export const unused = 1;');
  write(root, 'src/b.ts', `// import './unused.js';\nconst text = "import './unused.js'";\nexport { default as a } from './a.js';`);
  const map = scanProject(root);
  assert.equal(node(map, 'file:src/unused.js').status, 'coded');
  const edge = map.edges.find(e => e.type === 'code');
  assert.equal(edge.from, 'file:src/a.ts'); assert.equal(edge.to, 'file:src/b.ts');
  assert.deepEqual(edge.observations, [{ importer: 'src/b.ts', imported: 'src/a.ts' }]);
});

test('Python relative modules, sibling imports, parent imports, and packages resolve locally', () => {
  const root = fixture();
  write(root, 'pkg/__init__.py', ''); write(root, 'pkg/a.py', 'a = 1'); write(root, 'pkg/sub/b.py', 'b = 1');
  write(root, 'pkg/sub/main.py', 'from ..a import a\nfrom . import b\nimport pkg');
  const map = scanProject(root);
  for (const rel of ['pkg/a.py', 'pkg/sub/b.py', 'pkg/__init__.py']) assert.ok(map.edges.some(e => e.from === `file:${rel}` && e.to === 'file:pkg/sub/main.py'));
});

test('malformed configuration and duplicate ids are diagnosed without killing the map', () => {
  const root = fixture(); write(root, '.buildmap/project.json', '{ broken');
  assert.ok(scanProject(root).diagnostics.some(d => d.code === 'invalid-config'));
  planned(root, [{ id: 'same', files: [] }, { id: 'same', files: [] }, { id: '__mission__' }]);
  const map = scanProject(root); assert.equal(map.nodes.filter(n => n.id === 'same').length, 1);
  assert.equal(map.diagnostics.length, 2);
});

test('unresolved relative imports and large source files remain visible as scan gaps', () => {
  const root = fixture(); write(root, 'src/a.js', "import './gone.js';"); write(root, 'src/large.js', ' '.repeat(1_000_001));
  const map = scanProject(root);
  assert.ok(node(map, 'file:src/large.js'));
  assert.ok(map.gaps.some(g => g.kind === 'large-file'));
  assert.ok(map.gaps.some(g => g.kind === 'unresolved-import'));
});

test('manifest file paths cannot establish implementation outside the mapped root', () => {
  const root = fixture();
  const outside = fs.mkdtempSync(path.join(os.tmpdir(), 'buildmap-outside-'));
  write(outside, 'secret.js', 'export const secret = 1;');
  fs.symlinkSync(path.join(outside, 'secret.js'), path.join(root, 'linked.js'));
  planned(root, [{ id: 'outside', files: [path.join(outside, 'secret.js'), 'linked.js'] }]);
  assert.deepEqual(node(scanProject(root), 'outside').presentFiles, []);
});

test('invalid component field types are diagnosed rather than reaching the UI', () => {
  const root = fixture();
  planned(root, [{ id: 'bad', name: {} }, { id: 'bad2', dependsOn: 'engine' }, { id: 'bad3', visual: { kind: [] } }, { id: 'good', files: [] }]);
  const map = scanProject(root);
  assert.deepEqual(map.nodes.filter(n => n.kind === 'component').map(n => n.id), ['good']);
  assert.equal(map.diagnostics.length, 3);
  assert.equal(new Set(map.gaps.map(g => g.id)).size, map.gaps.length);
});

test('observed dependencies outside an explicit plan become drift gaps without changing proof states', () => {
  const root = fixture();
  write(root, 'src/feed.js', 'export const feed = 1;'); write(root, 'src/extra.js', 'export const extra = 1;');
  write(root, 'src/engine.js', "import './feed.js'; import './extra.js';");
  planned(root, [{ id: 'feed', files: ['src/feed.js'] }, { id: 'extra', files: ['src/extra.js'] }, { id: 'engine', files: ['src/engine.js'], dependsOn: ['feed'] }]);
  write(root, '.buildmap/evidence.json', { components: { engine: { status: 'verified', note: 'Behavior check passed.' } } });
  const map = scanProject(root);
  assert.equal(node(map, 'engine').status, 'verified');
  assert.equal(map.edges.find(e => e.type === 'code' && e.from === 'feed').planStatus, 'matched');
  assert.equal(map.edges.find(e => e.type === 'code' && e.from === 'extra').planStatus, 'undeclared');
  const drift = map.gaps.filter(g => g.kind === 'unexpected-dependency'); assert.equal(drift.length, 1);
  assert.equal(drift[0].nodeId, 'engine'); assert.equal(drift[0].dependencyId, 'extra');
  assert.deepEqual(drift[0].observations, [{ importer: 'src/engine.js', imported: 'src/extra.js' }]);
});

test('omitted dependency intent remains unspecified; explicit empty intent detects extra wiring', () => {
  const root = fixture(); write(root, 'src/a.js', 'export const a = 1;'); write(root, 'src/b.js', "import './a.js';");
  const components = [{ id: 'a', files: ['src/a.js'] }, { id: 'b', files: ['src/b.js'] }];
  planned(root, components); const unspecified = scanProject(root);
  assert.equal(node(unspecified, 'b').dependencyIntent, 'unspecified');
  assert.equal(unspecified.gaps.some(g => g.kind === 'unexpected-dependency'), false);
  components[1].dependsOn = []; planned(root, components); const explicit = scanProject(root);
  assert.equal(node(explicit, 'b').dependencyIntent, 'declared');
  assert.equal(explicit.gaps.filter(g => g.kind === 'unexpected-dependency').length, 1);
  assert.equal(node(explicit, 'b').status, node(unspecified, 'b').status);
});

test('unmapped evidence targets remain visible with their recorded claims', () => {
  const root = fixture();
  const receipt = { status: 'live', note: 'Prior deployment claim.' };
  write(root, '.buildmap/evidence.json', { components: { typo: receipt }, files: { 'src/deleted.js': receipt } });
  const map = scanProject(root); const gaps = map.gaps.filter(g => g.kind === 'unmapped-evidence');
  assert.equal(gaps.length, 2);
  for (const gap of gaps) { assert.equal(gap.priority, 'blocker'); assert.equal(gap.nodeId, null); assert.deepEqual(gap.evidence, receipt); }
  assert.equal(map.project.counts.live, 0);
});

test('file-only evidence is inspected without granting proof to its containing component', () => {
  const root = fixture(); write(root, 'src/a.js', 'export const a = 1;'); write(root, 'src/b.js', 'export const b = 1;');
  planned(root, [{ id: 'bundle', files: ['src/a.js', 'src/b.js'] }]);
  const receipt = { status: 'verified', note: 'Only file a was checked.' };
  write(root, '.buildmap/evidence.json', { files: { 'src/a.js': receipt } });
  const map = scanProject(root); const bundle = node(map, 'bundle');
  assert.equal(bundle.status, 'coded'); assert.equal(bundle.fileEvidence[0].assessment.accepted, true);
  assert.deepEqual(bundle.fileEvidence[0].evidence, receipt);
  assert.equal(map.gaps.find(g => g.kind === 'file-evidence-in-component').nodeId, 'bundle');
});

test('malformed evidence collections and falsy mapped receipts cannot disappear or promote state', () => {
  const root = fixture(); write(root, 'src/a.js', 'export const a = 1;');
  planned(root, [{ id: '0', files: ['src/a.js'] }]);
  write(root, '.buildmap/evidence.json', { components: [{ status: 'live', note: 'Bad collection.' }] });
  let map = scanProject(root); assert.equal(node(map, '0').status, 'coded');
  assert.ok(map.gaps.some(g => g.kind === 'invalid-config'));
  write(root, '.buildmap/evidence.json', { components: { 0: null } });
  map = scanProject(root); assert.equal(node(map, '0').status, 'coded');
  assert.ok(map.gaps.some(g => g.kind === 'invalid-evidence-record' && g.nodeId === '0'));
});

test('ordinary object prototype names are not mistaken for evidence records', () => {
  const root = fixture(); write(root, 'src/a.js', 'export const a = 1;');
  planned(root, [{ id: 'constructor', files: ['src/a.js'] }]);
  write(root, '.buildmap/evidence.json', { components: {} });
  const map = scanProject(root);
  assert.equal(node(map, 'constructor').evidence, null);
  assert.equal(map.gaps.some(g => g.kind === 'unsupported-evidence'), false);
});

test('clone provenance reports the selected revision without granting evidence states', () => {
  const root = fixture(); write(root, 'src/a.js', 'export const a = 1;');
  const source = { kind: 'github', repoName: 'DemoRepo', url: 'https://github.com/owner/DemoRepo', ref: 'feature/map', revision: 'a'.repeat(40), snapshot: true };
  const map = scanProject(root, { source });
  assert.equal(map.project.name, 'DemoRepo'); assert.deepEqual(map.project.source, source);
  assert.equal(map.nodes.find(n => n.kind === 'file').status, 'coded');
  assert.equal(scanProject(root).project.source.kind, 'local');
});

test('overlapping declarations retain full proof scope and never choose an arbitrary wiring/evidence owner', t => {
  const root = fixture(); t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  write(root, 'src/shared.js', 'export const shared = 1;');
  write(root, 'src/own.js', 'export const own = 1;');
  write(root, 'src/use.js', "import './shared.js'; import './own.js';");
  const components = [{ id: 'first', files: ['src/shared.js'] },
    { id: 'second', files: ['src/shared.js', 'src/own.js'] }, { id: 'consumer', files: ['src/use.js'] }];
  planned(root, components);
  const initial = scanProject(root);
  const receipts = Object.fromEntries(['first', 'second'].map(id => [id,
    { status: 'verified', note: 'Recorded check.', sourceHashes: node(initial, id).sourceHashes }]));
  const fileReceipt = { status: 'live', note: 'Recorded file use.' };
  write(root, '.buildmap/evidence.json', { components: receipts, files: { 'src/shared.js': fileReceipt } });
  for (const order of [components, [...components].reverse()]) {
    planned(root, order); const map = scanProject(root);
    for (const id of ['first', 'second']) {
      assert.equal(node(map, id).implementation, 'complete');
      assert.deepEqual(node(map, id).conflictingFiles, ['src/shared.js']);
      assert.equal(node(map, id).evidenceAssessment.accepted, false);
      assert.notEqual(node(map, id).status, 'verified');
      assert.ok(map.gaps.some(g => g.kind === 'overlapping-file' && g.nodeId === id && g.priority === 'blocker'));
    }
    assert.deepEqual(node(map, 'second').files, ['src/shared.js', 'src/own.js']);
    assert.deepEqual(Object.keys(node(map, 'second').sourceHashes), ['src/shared.js', 'src/own.js']);
    const observations = map.edges.filter(e => e.type === 'code').flatMap(e => e.observations);
    assert.deepEqual(observations, [{ importer: 'src/use.js', imported: 'src/own.js' }]);
    assert.deepEqual(map.gaps.find(g => g.kind === 'ambiguous-evidence-target').evidence, fileReceipt);
  }
  // The old reduced-scope receipt is also blocked while the declaration overlaps.
  receipts.second.sourceHashes = { 'src/own.js': node(initial, 'second').sourceHashes['src/own.js'] };
  write(root, '.buildmap/evidence.json', { components: receipts });
  assert.equal(node(scanProject(root), 'second').evidenceAssessment.accepted, false);
  // Removing the overlap restores the full-scope claim and routes file evidence correctly.
  planned(root, [components[0], components[2]]);
  write(root, '.buildmap/evidence.json', { components: { first: receipts.first }, files: { 'src/shared.js': fileReceipt } });
  const resolved = scanProject(root);
  assert.equal(node(resolved, 'first').status, 'verified');
  assert.equal(node(resolved, 'first').fileEvidence[0].assessment.accepted, true);
  assert.ok(resolved.edges.some(e => e.type === 'code' && e.from === 'first' && e.to === 'consumer'));
});

test('computed JS import arguments cannot invent connections to a literal prefix', t => {
  const root = fixture(); t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  write(root, 'src/prefix.js', 'export const prefix = 1;');
  write(root, 'src/direct.js', 'export const direct = 1;');
  write(root, 'src/options.json', '{}');
  write(root, 'src/main.js', `require('./prefix.js' + suffix); import('./prefix.js' + suffix);
    require('./prefix.js'.replace('prefix', 'other'));
    require('./direct.js'); import('./options.json', { with: { type: 'json' } });`);
  planned(root, [{ id: 'options', files: ['src/options.json'] }]);
  const map = scanProject(root);
  assert.equal(node(map, 'file:src/prefix.js').status, 'coded');
  const imported = map.edges.filter(e => e.type === 'code').flatMap(e => e.observations.map(o => o.imported));
  assert.deepEqual(imported.sort(), ['src/direct.js', 'src/options.json']);
});

test('root-relative HTML/CSS assets resolve with query strings and fragments', t => {
  const root = fixture(); t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  write(root, 'public/index.html', '<script src="/public/app.js?v=2#module"></script><link href="/public/styles.css?v=2" rel="stylesheet">');
  write(root, 'public/app.js', 'export const app = 1;');
  write(root, 'public/styles.css', '@import url("/public/theme.css?v=2#theme");');
  write(root, 'public/theme.css', 'body {}');
  const map = scanProject(root);
  for (const [importer, imported] of [['public/index.html', 'public/app.js'], ['public/index.html', 'public/styles.css'], ['public/styles.css', 'public/theme.css']]) {
    assert.ok(map.edges.some(e => e.type === 'code' && e.observations.some(o => o.importer === importer && o.imported === imported)));
  }
});

test('selected dependency and non-source input changes stale a receipt without changing its implementation', t => {
  const root = fixture(); t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  write(root, 'src/dependency.js', 'export const dependency = 1;');
  write(root, 'src/engine.js', "import './dependency.js';");
  write(root, 'fixtures/input.json', '{"value":1}');
  planned(root, [{ id: 'engine', files: ['src/engine.js'] }]);
  const before = scanProject(root);
  const digest = file => crypto.createHash('sha256').update(fs.readFileSync(path.join(root, file))).digest('hex');
  const receipt = { status: 'verified', note: 'Behavior check passed with these inputs.',
    sourceHashes: node(before, 'engine').sourceHashes,
    inputHashes: Object.fromEntries(['src/dependency.js', 'fixtures/input.json'].map(f => [f, digest(f)])) };
  write(root, '.buildmap/evidence.json', { components: { engine: receipt } });
  const current = scanProject(root);
  assert.equal(node(current, 'engine').status, 'verified');
  assert.equal(node(current, 'engine').evidenceAssessment.inputs.binding, 'current');
  assert.equal(current.nodes.some(n => n.files.includes('fixtures/input.json')), false);
  for (const file of Object.keys(receipt.inputHashes)) {
    const original = fs.readFileSync(path.join(root, file), 'utf8');
    write(root, file, original + '\n');
    const changed = scanProject(root); const engine = node(changed, 'engine');
    assert.deepEqual(engine.sourceHashes, receipt.sourceHashes);
    assert.equal(engine.status, engine.baseStatus); assert.equal(engine.status, 'connected');
    assert.equal(engine.evidenceAssessment.binding, 'stale');
    assert.ok(engine.evidenceAssessment.inputs.issues.some(i => i.file === file));
    assert.equal(engine.evidenceAssessment.inputs.currentHashes[file], digest(file));
    assert.notEqual(changed.fingerprint, current.fingerprint);
    assert.ok(changed.gaps.some(g => g.kind === 'unsupported-evidence' && g.nodeId === 'engine' && g.message.includes(file)));
    write(root, file, original);
    assert.equal(node(scanProject(root), 'engine').status, 'verified');
  }
  fs.rmSync(path.join(root, 'fixtures/input.json'));
  const missing = node(scanProject(root), 'engine');
  assert.equal(missing.evidenceAssessment.accepted, false);
  assert.equal(missing.evidenceAssessment.inputs.currentHashes['fixtures/input.json'], null);
});

test('input bindings are optional and cannot replace source binding or a descriptive proof claim', t => {
  const root = fixture(); t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  write(root, 'src/a.js', 'export const a = 1;'); write(root, 'data.json', '{}');
  planned(root, [{ id: 'a', files: ['src/a.js'] }]);
  const inputHashes = { 'data.json': crypto.createHash('sha256').update('{}').digest('hex') };
  const note = 'Recorded check.';
  write(root, '.buildmap/evidence.json', { components: { a: { status: 'verified', note } } });
  let map = scanProject(root); assert.equal(node(map, 'a').status, 'verified');
  assert.equal(node(map, 'a').evidenceAssessment.inputs, undefined);
  write(root, '.buildmap/evidence.json', { components: { a: { status: 'verified', note, inputHashes } } });
  map = scanProject(root);
  assert.equal(node(map, 'a').evidenceAssessment.binding, 'unbound');
  assert.equal(node(map, 'a').evidenceAssessment.inputs.binding, 'current');
  assert.ok(map.gaps.some(g => g.kind === 'unbound-evidence'));
  write(root, 'src/a.js', 'export const a = 2;');
  assert.equal(node(scanProject(root), 'a').evidenceAssessment.binding, 'unbound');
  write(root, '.buildmap/evidence.json', { components: { a: { status: 'live', inputHashes } } });
  assert.equal(node(scanProject(root), 'a').status, 'coded');
});

test('malformed input bindings reject proof and unsafe paths never expose outside hashes', t => {
  const root = fixture(); const outside = fs.mkdtempSync(path.join(os.tmpdir(), 'buildmap-input-outside-'));
  t.after(() => { fs.rmSync(root, { recursive: true, force: true }); fs.rmSync(outside, { recursive: true, force: true }); });
  write(root, 'src/a.js', 'export const a = 1;'); write(outside, 'private.json', '{"private":true}');
  fs.symlinkSync(path.join(outside, 'private.json'), path.join(root, 'escape.json'));
  planned(root, [{ id: 'a', files: ['src/a.js'] }]);
  const sourceHashes = node(scanProject(root), 'a').sourceHashes;
  for (const inputHashes of [null, [], {}, 'data.json', { 'src/a.js': 'invalid' }, { 'src/a.js': { hash: 'invalid' } }]) {
    write(root, '.buildmap/evidence.json', { components: { a: { status: 'verified', note: 'Check.', sourceHashes, inputHashes } } });
    const assessment = node(scanProject(root), 'a').evidenceAssessment;
    assert.equal(assessment.accepted, false); assert.equal(assessment.inputs.binding, 'invalid');
  }
  for (const file of [path.join(outside, 'private.json'), '../private.json', './src/a.js', 'src/../src/a.js', 'C:/private.json', 'escape.json', 'src']) {
    write(root, '.buildmap/evidence.json', { components: { a: { status: 'live', note: 'Check.', sourceHashes, inputHashes: { [file]: '0'.repeat(64) } } } });
    const assessment = node(scanProject(root), 'a').evidenceAssessment;
    assert.equal(assessment.accepted, false); assert.equal(assessment.inputs.currentHashes[file], null);
    assert.ok(assessment.inputs.issues.some(i => i.file === file));
  }
});

test('file-only input-bound claims retain their scope and report stale inputs inside a component', t => {
  const root = fixture(); t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  write(root, 'src/a.js', 'export const a = 1;'); write(root, 'src/b.js', 'export const b = 1;');
  write(root, 'test-data.json', '{}'); planned(root, [{ id: 'bundle', files: ['src/a.js', 'src/b.js'] }]);
  const receipt = { status: 'verified', note: 'File check.',
    sourceHashes: { 'src/a.js': node(scanProject(root), 'bundle').sourceHashes['src/a.js'] },
    inputHashes: { 'test-data.json': crypto.createHash('sha256').update('{}').digest('hex') } };
  write(root, '.buildmap/evidence.json', { files: { 'src/a.js': receipt } });
  let map = scanProject(root);
  assert.equal(node(map, 'bundle').status, 'coded');
  assert.equal(node(map, 'bundle').fileEvidence[0].assessment.accepted, true);
  write(root, 'test-data.json', '{"changed":true}'); map = scanProject(root);
  assert.equal(node(map, 'bundle').status, 'coded');
  assert.equal(node(map, 'bundle').fileEvidence[0].assessment.inputs.binding, 'stale');
  assert.equal(map.gaps.find(g => g.kind === 'file-evidence-in-component').priority, 'blocker');
  planned(root, []); // The same receipt may verify only the standalone discovered file.
  assert.equal(node(scanProject(root), 'file:src/a.js').status, 'coded');
  write(root, 'test-data.json', '{}');
  assert.equal(node(scanProject(root), 'file:src/a.js').status, 'verified');
});

function httpServer(endpoint = '/api/map') {
  return `import http from 'node:http';
http.createServer((req, res) => {
  const url = new URL(req.url || '/', 'http://localhost');
  if (url.pathname === '${endpoint}') return res.end('ok');
});`;
}

test('HTTP source matches preserve endpoint/method/location provenance and grant source state only', t => {
  const root = fixture(); t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  write(root, 'server.js', `import {createServer as serve} from 'node:http';
serve((req, res) => {
  const url = new URL(req.url, 'http://localhost');
  if (url.pathname === '/api/map') res.end('ok');
  if (req.method === 'POST' && url.pathname === '/submit') res.end('submitted');
  if (req.url === '/raw?key=1') res.end('raw');
});`);
  write(root, 'client.js', "fetch('/api/map?version=1#part');\nfetch('/api/map');\nfetch('/submit', {method:'POST'});\nfetch('/raw?key=1#part');");
  planned(root, [{ id: 'server', files: ['server.js'] }, { id: 'client', files: ['client.js'], dependsOn: ['server'] }]);
  const map = scanProject(root), edge = map.edges.find(e => e.type === 'code');
  assert.equal(edge.from, 'server'); assert.equal(edge.to, 'client'); assert.equal(edge.planStatus, 'matched');
  assert.equal(edge.observations.length, 4); assert.equal(map.scan.httpReferenceCount, 4); assert.equal(map.scan.importCount, 0);
  for (const o of edge.observations) {
    assert.equal(o.kind, 'http-source'); assert.equal(o.heuristic, true);
    assert.ok(o.importerLocation.line > 0); assert.ok(o.providerLocation.line > 0);
  }
  assert.equal(edge.observations.find(o => o.endpoint === '/submit').providerMethod, 'POST');
  assert.equal(node(map, 'client').status, 'connected'); assert.equal(map.project.counts.verified, 0); assert.equal(map.project.counts.live, 0);
  assert.ok(map.gaps.some(g => g.kind === 'unproved' && g.nodeId === 'client'));
  assert.equal(map.gaps.some(g => g.kind === 'unobserved-dependency'), false);
  planned(root, [{ id: 'server', files: ['server.js'] }, { id: 'client', files: ['client.js'], dependsOn: [] }]);
  assert.ok(scanProject(root).gaps.some(g => g.kind === 'unexpected-dependency' && g.dependencyId === 'server'));
});

test('ambiguous/missing HTTP providers stay unresolved and source-bound input edits invalidate proof', t => {
  const root = fixture(); t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  write(root, 'one.js', httpServer()); write(root, 'two.js', httpServer()); write(root, 'client.js', "fetch('/api/map');");
  planned(root, [{ id: 'server', files: ['one.js'] }, { id: 'second', files: ['two.js'] }, { id: 'client', files: ['client.js'], dependsOn: ['server'] }]);
  let map = scanProject(root);
  assert.equal(map.scan.httpReferenceCount, 0); assert.equal(node(map, 'client').status, 'coded');
  assert.ok(map.gaps.some(g => g.kind === 'ambiguous-http-reference'));
  fs.rmSync(path.join(root, 'two.js')); map = scanProject(root);
  assert.equal(map.scan.httpReferenceCount, 1);
  write(root, '.buildmap/evidence.json', { components: { client: { status: 'verified', note: 'Fixture check.',
    sourceHashes: node(map, 'client').sourceHashes, inputHashes: node(map, 'server').sourceHashes } } });
  assert.equal(node(scanProject(root), 'client').status, 'verified');
  write(root, 'one.js', httpServer('/other')); map = scanProject(root);
  assert.equal(map.scan.httpReferenceCount, 0); assert.equal(node(map, 'client').status, 'coded');
  assert.ok(map.gaps.some(g => g.kind === 'unresolved-http-reference'));
  assert.ok(map.gaps.some(g => g.kind === 'unsupported-evidence' && g.nodeId === 'client'));
});

test('parser discovers actual imports in template expressions while excluding regex/examples and shadowed calls', t => {
  const root = fixture(); t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  for (const f of ['a.js', 'b.js', 'unused.js']) write(root, f, 'export const value = 1;');
  write(root, 'main.js', String.raw`const regex = /import\('\.\/unused.js'\)/;
const example = "require('./unused.js'); fetch('/api/map')";
const literal = import('./\u0061.js');
const template = ` + '`value ${import("./b.js")}`;' + `
function custom(require, fetch) { require('./unused.js'); fetch('/api/map'); }`);
  write(root, 'server.js', httpServer());
  const map = scanProject(root);
  assert.equal(node(map, 'file:unused.js').status, 'coded');
  assert.equal(map.scan.httpReferenceCount, 0);
  for (const f of ['a.js', 'b.js']) assert.ok(map.edges.some(e => e.from === `file:${f}` && e.to === 'file:main.js'));
});

test('unsupported JavaScript syntax and unsupported HTTP forms cannot invent connections', t => {
  const root = fixture(); t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  write(root, 'dep.js', 'export const dep = 1;');
  write(root, 'broken.js', "import './dep.js'; const = invalid;");
  write(root, 'client.js', "fetch('/api/map'); fetch('https://example.invalid/api/map'); fetch('/api/map'+suffix);");
  write(root, 'server.js', `const http = {createServer: callback => callback};
http.createServer((req,res) => {if(req.url === '/api/map') res.end('mock');});`);
  let map = scanProject(root);
  assert.equal(node(map, 'file:broken.js').status, 'coded'); assert.equal(node(map, 'file:dep.js').status, 'coded');
  assert.ok(map.gaps.some(g => g.kind === 'javascript-parse-failed'));
  assert.equal(map.scan.httpReferenceCount, 0);
  write(root, 'server.js', `const {createServer: serve} = require('node:http');
serve((req,res) => {if(req.method === 'POST' && req.url === '/api/map') res.end('post');});`);
  map = scanProject(root); assert.equal(map.scan.httpReferenceCount, 0);
  write(root, 'client.js', "fetch('/api/map', {method:'POST'});");
  assert.equal(scanProject(root).scan.httpReferenceCount, 1);
  write(root, 'server.js', `import http from 'node:http';
http.createServer((req,res) => {if(req.url !== '/api/map') res.end('other');});`);
  assert.equal(scanProject(root).scan.httpReferenceCount, 0);
  write(root, 'server.js', `import http from 'node:http';
http.createServer((req,res) => {if(req.url === '/api/map') console.log(res);});`);
  assert.equal(scanProject(root).scan.httpReferenceCount, 0);
  write(root, 'server.js', `import http from 'node:http';
function send(response, value) { response.end(value); }
http.createServer((req,res) => {if(req.url === '/api/map') send(res, 'ok');});`);
  assert.equal(scanProject(root).scan.httpReferenceCount, 1);
});
