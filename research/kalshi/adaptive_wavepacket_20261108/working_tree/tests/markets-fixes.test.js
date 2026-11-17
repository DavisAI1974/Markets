// Markets working-tree fixes (CCODE_INDEPENDENT_REVIEW_20261108.md, BM-* ids).
// One test per finding id so the fix log can point at a proving test.
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { scanProject } from '../src/scan.js';
import { importSpecs, resolveImport } from '../src/imports.js';
import { readIntent } from '../src/intent.js';

function fixture(t, prefix = 'buildmap-markets-') {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), prefix));
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  return root;
}
function write(root, rel, text) {
  fs.mkdirSync(path.dirname(path.join(root, rel)), { recursive: true });
  fs.writeFileSync(path.join(root, rel), typeof text === 'string' ? text : JSON.stringify(text));
}
const node = (map, id) => map.nodes.find(n => n.id === id);

test('BM-1: unresolved local Python imports are diagnosed; stdlib/third-party names are not', t => {
  const root = fixture(t);
  write(root, 'pkg/__init__.py', '');
  write(root, 'pkg/present.py', 'value = 1\n');
  write(root, 'pkg/a.py', 'from .missing import f\nimport pkg.absent\nfrom . import maybe_symbol\nfrom .present import value\nimport numpy\nimport json\nfrom os import path\n');
  write(root, 'research/kalshi/script.py', 'from . import gone\nimport third_party_name\n');
  const map = scanProject(root);
  const unresolved = map.diagnostics.filter(d => d.code === 'unresolved-import').map(d => d.message);
  assert.ok(unresolved.some(m => m.startsWith('pkg/a.py') && m.includes('.missing')), unresolved.join('\n'));
  assert.ok(unresolved.some(m => m.startsWith('pkg/a.py') && m.includes('pkg.absent')), unresolved.join('\n'));
  assert.ok(unresolved.some(m => m.startsWith('research/kalshi/script.py') && m.includes('.gone')), unresolved.join('\n'));
  assert.ok(!unresolved.some(m => /numpy|json|\bos\b|third_party_name|maybe_symbol|present/.test(m)), unresolved.join('\n'));
  assert.equal(unresolved.length, 3, unresolved.join('\n'));
  assert.ok(map.gaps.some(g => g.kind === 'unresolved-import'));
});

test('BM-2: Python resolver tries the importer directory before the root and agrees with workflow call links', t => {
  const root = fixture(t);
  write(root, 'research/kalshi/a.py', 'import b\nfrom b import f\nimport odcore.x\nfrom odcore.x import g\n\ndef run(v):\n    return f(v) + g(v) + b.f(v)\n');
  write(root, 'research/kalshi/b.py', 'def f(v):\n    return v\n');
  write(root, 'odcore/__init__.py', '');
  write(root, 'odcore/x.py', 'def g(v):\n    return v * 2\n');
  write(root, 'pkg/__init__.py', '');
  write(root, 'pkg/c.py', 'def h():\n    return 1\n');
  write(root, 'pkg/main.py', 'from . import c\n\ndef go():\n    return c.h()\n');
  const files = new Set(['research/kalshi/a.py', 'research/kalshi/b.py', 'odcore/__init__.py', 'odcore/x.py', 'pkg/__init__.py', 'pkg/c.py', 'pkg/main.py', 'b.py']);
  assert.equal(resolveImport('research/kalshi/a.py', 'b', files, '.py'), 'research/kalshi/b.py');
  assert.equal(resolveImport('research/kalshi/a.py', 'odcore.x', files, '.py'), 'odcore/x.py');
  assert.equal(resolveImport('research/kalshi/a.py', 'odcore', files, '.py'), 'odcore/__init__.py');
  assert.equal(resolveImport('pkg/main.py', '.c', files, '.py'), 'pkg/c.py');
  const map = scanProject(root);
  const observed = map.edges.filter(e => e.type === 'code').flatMap(e => e.observations.map(o => `${o.importer}->${o.imported}`));
  for (const expected of ['research/kalshi/a.py->research/kalshi/b.py', 'research/kalshi/a.py->odcore/x.py', 'pkg/main.py->pkg/c.py']) {
    assert.ok(observed.includes(expected), `missing map edge ${expected}; have ${observed.join(', ')}`);
  }
  const linked = map.workflow.relationships.filter(r => r.importSource);
  const linkedPairs = linked.map(r => `${r.source.path}->${r.targetSource.path}`);
  assert.ok(linkedPairs.includes('research/kalshi/a.py->research/kalshi/b.py'), linkedPairs.join(', '));
  assert.ok(linkedPairs.includes('research/kalshi/a.py->odcore/x.py'), linkedPairs.join(', '));
  for (const pair of linkedPairs) assert.ok(observed.includes(pair), `workflow link ${pair} has no map edge`);
  assert.ok(!map.workflow.unresolvedCalls.some(c => c.reason.startsWith('Multiple')), JSON.stringify(map.workflow.unresolvedCalls));
});

test('BM-3: crossWired separates intra-piece wiring from cross-piece connections', t => {
  const root = fixture(t);
  write(root, 'ui/index.js', "import './helper.js'; export const ui = 1;");
  write(root, 'ui/helper.js', 'export const helper = 1;');
  write(root, 'core/engine.js', 'export const engine = 1;');
  write(root, 'main.js', "import './core/engine.js';");
  write(root, 'lonely.js', 'export const lonely = 1;');
  write(root, '.buildmap/project.json', { components: [{ id: 'ui', files: ['ui/index.js', 'ui/helper.js'] }, { id: 'core', files: ['core/engine.js'] }] });
  const map = scanProject(root);
  assert.equal(node(map, 'ui').wired, true); assert.equal(node(map, 'ui').crossWired, false);
  assert.equal(node(map, 'core').wired, true); assert.equal(node(map, 'core').crossWired, true);
  assert.equal(node(map, 'file:main.js').crossWired, true);
  assert.equal(node(map, 'file:lonely.js').wired, false); assert.equal(node(map, 'file:lonely.js').crossWired, false);
  assert.equal(node(map, 'ui').status, 'connected'); // retained semantics: any present import edge
  const gap = map.gaps.find(g => g.kind === 'intra-piece-wiring' && g.nodeId === 'ui');
  assert.ok(gap, JSON.stringify(map.gaps.map(g => g.kind)));
  assert.match(gap.message, /inside this piece/);
  assert.ok(!map.gaps.some(g => g.kind === 'intra-piece-wiring' && g.nodeId === 'core'));
});

test('BM-4: progress and counts exclude the mission target from the denominator', t => {
  const root = fixture(t);
  write(root, 'README.md', '# Demo\n\nDemo does one thing.');
  write(root, 'only.js', 'export const only = 1;');
  const map = scanProject(root);
  assert.ok(map.nodes.some(n => n.id === '__mission__'));
  assert.equal(map.project.progress, 20);
  assert.equal(Object.values(map.project.counts).reduce((a, b) => a + b, 0), 1);
});

test('BM-5: the same tree at two checkout paths yields the same fingerprint', t => {
  const a = path.join(fixture(t, 'buildmap-fp-a-'), 'proj'), b = path.join(fixture(t, 'buildmap-fp-b-'), 'proj');
  for (const root of [a, b]) {
    write(root, 'README.md', '# Demo\n\nDemo does one thing.');
    write(root, 'src/a.js', "import './b.js'; export const a = 1;"); write(root, 'src/b.js', 'export const b = 1;');
    write(root, 'tool.py', 'def f(x):\n    return x\n');
    write(root, '.buildmap/project.json', { name: 'Demo', components: [{ id: 'core', files: ['src/a.js', 'src/b.js'] }] });
  }
  const left = scanProject(a), right = scanProject(b);
  assert.notEqual(left.project.root, right.project.root);
  assert.equal(left.fingerprint, right.fingerprint);
  assert.equal(left.scan.inventoryMode, 'filesystem');
  write(a, 'src/b.js', 'export const b = 2;');
  assert.notEqual(scanProject(a).fingerprint, right.fingerprint);
});

test('BM-7: parenthesized and backslash-continued Python imports keep every name', () => {
  const source = 'from pkg.mod import (\n    alpha,\n    beta,  # trailing comment\n    gamma as g,\n)\nfrom other import a, \\\n    b\nimport x, \\\n    y\nfrom single import one\n';
  const specs = importSpecs(source, '.py');
  for (const expected of ['pkg.mod', 'pkg.mod.alpha', 'pkg.mod.beta', 'pkg.mod.gamma', 'other', 'other.a', 'other.b', 'x', 'y', 'single', 'single.one']) {
    assert.ok(specs.includes(expected), `${expected} missing from ${specs.join(', ')}`);
  }
  assert.ok(!specs.some(s => /[()\\#]/.test(s) || s.includes('comment')), specs.join(', '));
});

test('exclude: manifest exclude prefixes and .buildmapignore drop nested trees from the inventory in both modes', t => {
  for (const git of [false, true]) {
    const root = fixture(t);
    if (git) assert.equal(spawnSync('git', ['-C', root, 'init', '--quiet'], { encoding: 'utf8' }).status, 0);
    write(root, 'src/a.js', 'export const a = 1;');
    write(root, 'research/snapshot/b.js', 'export const b = 1;');
    write(root, 'vendor_copy/c.py', 'c = 1\n');
    write(root, 'keep/d.py', 'd = 1\n');
    write(root, '.buildmapignore', '# frozen provenance copy\nvendor_copy/\n\n');
    write(root, '.buildmap/project.json', { exclude: ['./research/snapshot'], components: [{ id: 'frozen', files: ['research/snapshot/b.js'] }] });
    const map = scanProject(root);
    assert.equal(map.scan.inventoryMode, git ? 'git' : 'filesystem');
    assert.deepEqual(map.nodes.flatMap(n => n.files).sort(), ['keep/d.py', 'research/snapshot/b.js', 'src/a.js']);
    assert.deepEqual(node(map, 'frozen').presentFiles, []);
    assert.deepEqual(map.scan.excludes, ['research/snapshot', 'vendor_copy']);
    assert.ok(map.diagnostics.some(d => d.code === 'excluded-declared-file' && d.nodeId === 'frozen'));
  }
  const bad = fixture(t);
  write(bad, '.buildmap/project.json', { exclude: 'not-a-list' });
  assert.ok(scanProject(bad).diagnostics.some(d => d.code === 'invalid-config' && /exclude/.test(d.message)));
});

test('workflow YAML is inventoried-only and says so instead of appearing as silently coded', t => {
  const root = fixture(t); // Git inventory: dot-directories are only listed through git.
  assert.equal(spawnSync('git', ['-C', root, 'init', '--quiet'], { encoding: 'utf8' }).status, 0);
  write(root, '.github/workflows/ci.yml', 'name: ci\non: push\n');
  write(root, 'config/app.yml', 'key: value\n');
  const map = scanProject(root);
  const wf = node(map, 'file:.github/workflows/ci.yml');
  assert.equal(wf.kind, 'workflow-yaml');
  assert.equal(wf.status, 'coded');
  assert.deepEqual(wf.analysis, { kind: 'workflow-yaml', status: 'inventoried', text: 'inventoried, not analyzed' });
  assert.match(wf.purpose, /inventoried, not analyzed/);
  assert.equal(wf.codeGuide.files[0].status, 'inventoried');
  assert.equal(wf.codeGuide.files[0].reason, 'inventoried, not analyzed');
  assert.equal(node(map, 'file:config/app.yml').kind, 'file');
});

test('workflow-tool JavaScript with a top-level return is parsed; ordinary modules still report the parse error', t => {
  const root = fixture(t);
  write(root, 'tools/run.workflow.js', "import './lib.js';\nconst x = 1;\nreturn x;\n");
  write(root, 'tools/lib.js', 'export const lib = 1;');
  write(root, 'tools/plain.js', 'const y = 1;\nreturn y;\n');
  const map = scanProject(root);
  assert.equal(node(map, 'file:tools/run.workflow.js').codeGuide.files[0].status, 'parsed');
  assert.ok(map.edges.some(e => e.type === 'code' && e.from === 'file:tools/lib.js' && e.to === 'file:tools/run.workflow.js'));
  assert.ok(!map.diagnostics.some(d => d.code === 'javascript-parse-failed' && d.message.startsWith('tools/run.workflow.js')));
  assert.ok(map.diagnostics.some(d => d.code === 'javascript-parse-failed' && d.message.startsWith('tools/plain.js')));
});

test('intent: CLAUDE.md and KALSHI_TRADING.md are intent sources after README and before docs; manifest mission wins', t => {
  const root = fixture(t);
  write(root, 'docs/README.md', '# Docs\n\nDocs prose.');
  write(root, 'KALSHI_TRADING.md', '# Index\n\nKalshi file index prose.');
  assert.equal(readIntent(root).source, 'KALSHI_TRADING.md');
  write(root, 'CLAUDE.md', '# Project\n\n## Rules\n\n- a bullet\n\n**One-line state:** the lag is the edge.');
  const claude = readIntent(root);
  assert.equal(claude.source, 'CLAUDE.md'); assert.match(claude.text, /lag is the edge/);
  write(root, 'README.md', '# Repo\n\nREADME prose.');
  assert.equal(readIntent(root).source, 'README.md');
  assert.equal(readIntent(root, { mission: 'Declared.' }).source, '.buildmap/project.json');
  assert.equal(scanProject(root).project.intent.source, 'README.md');
});

// ---- batch 2: analyzer timeout, CLI target creation, server cache, host check, observe gate
import http from 'node:http';
import { once } from 'node:events';
import { pythonGuides } from '../src/workflow.js';
import { parseArgs, prepareTarget } from '../src/cli.js';
import { startServer } from '../src/server.js';
import { observePython } from '../src/collected-runs.js';

const cliPath = new URL('../src/cli.js', import.meta.url).pathname;
function withEnv(name, value, fn) {
  const had = Object.hasOwn(process.env, name), previous = process.env[name];
  if (value === undefined) delete process.env[name]; else process.env[name] = value;
  const restore = () => { if (had) process.env[name] = previous; else delete process.env[name]; };
  try { const result = fn(); if (result && typeof result.then === 'function') return result.finally(restore); restore(); return result; }
  catch (err) { restore(); throw err; }
}
function request(base, route, headers = {}) {
  return new Promise((resolve, reject) => {
    const req = http.request(base + route, { method: 'GET', headers }, res => {
      let body = ''; res.setEncoding('utf8'); res.on('data', d => body += d); res.on('end', () => resolve({ status: res.statusCode, body }));
    });
    req.on('error', reject); req.end();
  });
}

test('BM-6: analyzer timeout is configurable and bounded mode isolates a slow file instead of failing the batch', t => {
  const calls = [];
  const run = batch => { calls.push(batch.map(s => s.path)); return batch.some(s => s.path === 'slow.py') ? { failure: 'timeout' }
    : { parsed: batch.map(() => ({ status: 'parsed', reason: 'stub', functions: [] })) }; };
  const sources = ['a.py', 'slow.py', 'c.py'].map(p => ({ path: p, source: 'value = 1\n' }));
  const guides = new Map(sources.map(s => [s.path, { path: s.path, functions: [] }]));
  pythonGuides(sources, guides, { runAnalyzer: run });
  assert.equal(guides.get('a.py').status, 'parsed'); assert.equal(guides.get('c.py').status, 'parsed');
  assert.equal(guides.get('slow.py').status, 'analyzer-unavailable');
  assert.match(guides.get('slow.py').reason, /timed out/); assert.match(guides.get('slow.py').reason, /this file/);
  assert.ok(calls.length > 1, 'bounded mode must bisect the failed batch');
  assert.deepEqual(calls[0], ['a.py', 'slow.py', 'c.py']);
  // Real analyzer with a tiny timeout: every file is retried alone and reports the timeout itself.
  const real = ['x.py', 'y.py'].map(p => ({ path: p, source: 'def f():\n    return 1\n' }));
  const realGuides = new Map(real.map(s => [s.path, { path: s.path, functions: [] }]));
  withEnv('BUILDMAP_ANALYZER_TIMEOUT_MS', '1', () => pythonGuides(real, realGuides));
  for (const p of ['x.py', 'y.py']) { assert.equal(realGuides.get(p).status, 'analyzer-unavailable'); assert.match(realGuides.get(p).reason, /timed out after 1 ms/); }
  withEnv('BUILDMAP_ANALYZER_TIMEOUT_MS', 'nonsense', () => pythonGuides(real, realGuides));
  assert.equal(realGuides.get('x.py').status, 'parsed'); // invalid values fall back to the 5000 ms default
});

test('BM-8: a missing local target is an error unless --create is given', t => {
  const root = fixture(t); const absent = path.join(root, 'typo-dir');
  assert.equal(parseArgs(['--create', absent]).create, true); assert.equal(parseArgs([absent]).create, false);
  assert.throws(() => prepareTarget(absent, () => {}), /does not exist.*--create/s);
  assert.equal(fs.existsSync(absent), false);
  const logs = [];
  assert.equal(prepareTarget(absent, m => logs.push(m), null, { create: true }).root, absent);
  assert.ok(fs.existsSync(absent)); assert.match(logs[0], /Created empty project folder/);
  const missing = spawnSync(process.execPath, [cliPath, path.join(root, 'other-typo'), '--json'], { encoding: 'utf8', timeout: 10000 });
  assert.equal(missing.status, 1); assert.match(missing.stderr, /does not exist/); assert.equal(fs.existsSync(path.join(root, 'other-typo')), false);
  const created = spawnSync(process.execPath, [cliPath, path.join(root, 'other-typo'), '--create', '--json'], { encoding: 'utf8', timeout: 10000 });
  assert.equal(created.status, 0, created.stderr); assert.ok(fs.existsSync(path.join(root, 'other-typo')));
});

test('BM-9: concurrent map/gaps requests share one scan and unchanged trees are served from the TTL cache', async t => {
  const root = fixture(t); write(root, 'main.js', 'export const main = 1;');
  let inFlight = 0, calls = 0;
  const slowScan = async (...args) => { calls++; inFlight++; assert.equal(inFlight, 1, 'scan must not overlap'); await new Promise(r => setTimeout(r, 60)); inFlight--; return scanProject(...args); };
  const server = startServer({ root, port: 0, scan: slowScan }); await once(server, 'listening');
  t.after(() => new Promise(resolve => server.close(resolve)));
  const base = `http://127.0.0.1:${server.address().port}`;
  const [map, gaps, again] = await Promise.all([request(base, '/api/map'), request(base, '/api/gaps'), request(base, '/api/map')]);
  assert.equal(calls, 1); assert.equal(map.status, 200); assert.equal(gaps.status, 200); assert.equal(map.body, again.body);
  assert.equal(JSON.parse(gaps.body).fingerprint, JSON.parse(map.body).fingerprint);
  await request(base, '/api/map'); assert.equal(calls, 1, 'unchanged tree inside the TTL is served from cache');
  fs.writeFileSync(path.join(root, 'main.js'), 'export const main = 2;');
  const changed = JSON.parse((await request(base, '/api/map')).body);
  assert.equal(calls, 2); assert.notEqual(changed.fingerprint, JSON.parse(map.body).fingerprint);
  const health = JSON.parse((await request(base, '/api/health')).body);
  assert.equal(health.cache.ttlMs, 5000); assert.ok(['git', 'mtime'].includes(health.cache.changeSignal));
  const direct = startServer({ root, port: 0, scan: (...a) => { calls++; return scanProject(...a); }, ttlMs: 0 }); await once(direct, 'listening');
  t.after(() => new Promise(resolve => direct.close(resolve)));
  const directBase = `http://127.0.0.1:${direct.address().port}`;
  calls = 0; await request(directBase, '/api/map'); await request(directBase, '/api/map'); assert.equal(calls, 2, 'ttlMs 0 disables the cache');
});

test('BM-S1: non-loopback Host headers get 421 unless --host was explicit, and health hides the absolute root', async t => {
  const root = fixture(t); write(root, 'main.js', 'export const main = 1;');
  const server = startServer({ root, port: 0 }); await once(server, 'listening');
  t.after(() => new Promise(resolve => server.close(resolve)));
  const base = `http://127.0.0.1:${server.address().port}`;
  for (const host of ['localhost', 'localhost:4173', '127.0.0.1:9', '[::1]:4173', 'LOCALHOST']) assert.equal((await request(base, '/api/health', { host })).status, 200, host);
  for (const host of ['evil.example', 'evil.example:80', '10.0.0.5:4173', 'localhost.evil.example']) {
    const r = await request(base, '/api/map', { host }); assert.equal(r.status, 421, host); assert.match(JSON.parse(r.body).error, /Host/);
  }
  const health = JSON.parse((await request(base, '/api/health')).body);
  assert.equal(health.ok, true); assert.ok(!JSON.stringify(health).includes(root)); assert.equal(health.project, path.basename(root));
  assert.match(health.rootHash, /^[a-f0-9]{12}$/);
  const open = startServer({ root, port: 0, hostCheck: false }); await once(open, 'listening');
  t.after(() => new Promise(resolve => open.close(resolve)));
  assert.equal((await request(`http://127.0.0.1:${open.address().port}`, '/api/health', { host: 'evil.example' })).status, 200);
  assert.equal(parseArgs(['--host', '0.0.0.0', root]).hostExplicit, true); assert.equal(parseArgs([root]).hostExplicit, false);
});

test('BM-S2: --observe-python refuses to run project code unless BUILDMAP_ALLOW_OBSERVE=1', async t => {
  const root = fixture(t); write(root, 'main.py', 'print("never")\n');
  const output = path.join(root, 'run.json');
  await withEnv('BUILDMAP_ALLOW_OBSERVE', undefined, () => assert.rejects(observePython({ root, entry: 'main.py', sourceHashes: { 'main.py': 'x' }, privateKeyFile: path.join(root, 'none.pem'), collectorId: 'c', output }), /BUILDMAP_ALLOW_OBSERVE=1/));
  await withEnv('BUILDMAP_ALLOW_OBSERVE', 'yes', () => assert.rejects(observePython({ root, entry: 'main.py', sourceHashes: { 'main.py': 'x' }, privateKeyFile: path.join(root, 'none.pem'), collectorId: 'c', output }), /BUILDMAP_ALLOW_OBSERVE=1/));
  assert.equal(fs.existsSync(output), false);
  const env = { ...process.env }; delete env.BUILDMAP_ALLOW_OBSERVE;
  const cli = spawnSync(process.execPath, [cliPath, root, '--observe-python', 'main.py', '--collector-key', path.join(root, 'none.pem'), '--collector-id', 'c', '--observation-output', output], { encoding: 'utf8', env, timeout: 15000 });
  assert.equal(cli.status, 1); assert.match(cli.stderr, /BUILDMAP_ALLOW_OBSERVE=1/); assert.equal(fs.existsSync(output), false);
});
