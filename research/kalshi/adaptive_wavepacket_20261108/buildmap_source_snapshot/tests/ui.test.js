import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import os from 'node:os';
import path from 'node:path';
import { scanProject } from '../src/scan.js';
import { spawnSync } from 'node:child_process';
import { clientSource } from '../src/export.js';
import { generateCollectorKey, observePython } from '../src/collected-runs.js';

// Executes the real client against a small DOM double. This covers rendering
// logic and interactions, not CSS layout or browser integration.
class Element {
  constructor(tag = 'div') {
    this.tag = tag; this.children = []; this.dataset = {}; this.style = { cssText: '' };
    this.attributes = {}; this.listeners = {}; this.clientWidth = 800; this.clientHeight = 600;
    this.classes = new Set(); this.textContent = ''; this.hidden = false; this._html = '';
    this.classList = { add: c => this.classes.add(c), remove: c => this.classes.delete(c),
      contains: c => this.classes.has(c),
      toggle: (c, on) => on ? this.classes.add(c) : this.classes.delete(c) };
  }
  set innerHTML(value) { this._html = value; this.children = []; }
  get innerHTML() { return this._html; }
  set className(value) { this.classes = new Set(value.split(' ')); }
  get className() { return [...this.classes].join(' '); }
  addEventListener(type, fn) { this.listeners[type] = fn; }
  appendChild(el) { this.children.push(el); }
  setAttribute(key, value) { this.attributes[key] = value; }
  scrollTo(options) { this.lastScroll = options; }
  scrollIntoView(options) { this.revealOptions = options; }
  focus(options) { this.focusOptions = options; this.document.activeElement = this; }
  click() { return this.listeners.click?.(); }
  select() { this.selectedText = true; }
}
function piece(id, overrides = {}) {
  return { id, name: id, kind: 'component', status: 'coded', baseStatus: 'coded', implementation: 'complete',
    purpose: 'Does useful work.', files: [`${id}.js`], presentFiles: [`${id}.js`], sourceHashes: {}, group: 'Core', source: 'manifest',
    evidenceAssessment: { accepted: false, reason: 'No explicit evidence record.' }, ...overrides };
}
function model(fingerprint, nodes = [piece('a'), piece('__mission__', { kind: 'mission' })]) {
  return { fingerprint, project: { name: 'Fixture', mode: 'brownfield', intent: { text: 'Build useful software', confidence: 'declared' }, progress: 20, counts: { coded: 1 } },
    states: ['planned', 'coded', 'connected', 'computing', 'verified', 'live'], nodes, edges: [], gaps: [] };
}
async function client(initial, offline = false, navigator = undefined) {
  const elements = new Map(); let current = initial; let failed = false;
  const document = { activeElement: null };
  const create = tag => { const el = new Element(tag); el.document = document; return el; };
  const get = id => { if (id === 'buildmapSnapshot') return offline ? { textContent: JSON.stringify(initial) } : null; if (!elements.has(id)) elements.set(id, create('div')); return elements.get(id); };
  let requests = 0, polls = 0;
  Object.assign(document, { getElementById: get, createElement: create, createElementNS: (_,tag) => create(tag),
    querySelectorAll: () => get('nodeLayer').children.filter(e => e.classes.has('node')) });
  const context = vm.createContext({ document, navigator,
    fetch: async () => { requests++; return { ok: !failed, status: failed ? 500 : 200, json: async () => current }; },
    ResizeObserver: class { observe() {} }, setInterval: () => { polls++; }, console: { error() {} } });
  const source = clientSource();
  const api = await vm.runInContext(`(async () => { ${source}\nreturn { refresh }; })()`, context);
  return { get, context, counts: () => ({ requests, polls }), setModel: m => { current = m; }, fail: value => { failed = value; },
    refresh: () => api.refresh() };
}

test('calculation reader searches and pages a large project, follows real source candidates and returns to the complete free map', async t => {
  const root=fs.mkdtempSync(path.join(os.tmpdir(),'buildmap-reader-')); t.after(()=>fs.rmSync(root,{recursive:true,force:true}));
  fs.writeFileSync(path.join(root,'work.js'), 'export function entry(x) { const result=prepare(x); return result; }\nexport function prepare(x) { return x+1; }\n'+Array.from({length:60},(_,i)=>`export function extra${i}(x) { return x; }`).join('\n'));
  const map=scanProject(root), ui=await client(map,true);
  ui.get('workflowViewButton').listeners.click();
  const detail=ui.get('detail'), results=detail.children.find(c=>c.className==='workflow-reader-results');
  assert.equal(results.children.filter(c=>c.className==='workflow-choice').length,25);
  const search=detail.children.find(c=>c.tag==='label').children[0]; search.value='entry'; search.listeners.input();
  assert.equal(results.children.filter(c=>c.className==='workflow-choice').length,1);
  results.children.find(c=>c.className==='workflow-choice').listeners.click();
  const reading=detail.children.find(c=>c.className==='workflow-reader-calculation');
  assert.match(reading.innerHTML,/What comes in.*What does it build.*What comes out/s);
  reading.children.find(c=>c.className==='workflow-follow').listeners.click();
  assert.match(reading.innerHTML,/prepare/);
  ui.get('mapViewButton').listeners.click();
  assert.equal(ui.get('workspace').classes.has('workflow-reading'),false);
  assert.equal(ui.get('nodeLayer').children.filter(c=>c.className.includes('node')).length,map.nodes.length);
  assert.equal(ui.counts().requests,0);
});

test('signed runtime routes navigate nested source offline and tampered receipts cannot elevate free evidence states',async t=>{
 const temp=fs.mkdtempSync(path.join(os.tmpdir(),'buildmap-observed-ui-'));t.after(()=>fs.rmSync(temp,{recursive:true,force:true}));
 const root=path.join(temp,'project');fs.mkdirSync(root);fs.mkdirSync(path.join(root,'.buildmap'));
 fs.writeFileSync(path.join(root,'app.py'),'def outer():\n    def inner(a,b):\n        return a-b\n    return inner(3,1)\nassert outer()==2\n');
 const privateKeyFile=path.join(temp,'key.pem');generateCollectorKey(privateKeyFile,path.join(root,'.buildmap/collectors.json'),'ui');
 const initial=scanProject(root),sourceHashes=Object.assign({},...initial.nodes.filter(n=>n.kind!=='mission').map(n=>n.sourceHashes));
 await observePython({root,entry:'app.py',sourceHashes,privateKeyFile,collectorId:'ui',output:path.join(root,'run.json')});
 fs.writeFileSync(path.join(root,'.buildmap/analysis.json'),JSON.stringify({version:1,collectedRuns:['run.json']}));
 const map=scanProject(root),ui=await client(map,true);ui.get('workflowViewButton').listeners.click();
 const section=ui.get('detail').children.find(c=>c.className==='collected-runs'),run=section.children.find(c=>c.className==='collected-run');
 assert.match(run.innerHTML,/verified-collector-current-source/);
 const observed=run.children.find(c=>c.className==='collected-calculation'&&c.innerHTML.includes('outer.inner'));
 observed.children.find(c=>c.tag==='button').listeners.click();
 const reading=ui.get('detail').children.find(c=>c.className==='workflow-reader-calculation');assert.match(reading.innerHTML,/outer.inner/);
 assert.equal(ui.counts().requests,0);assert.equal(map.project.counts.verified,0);assert.equal(map.project.counts.live,0);
 const receipt=JSON.parse(fs.readFileSync(path.join(root,'run.json')));receipt.payload.exitCode=123;fs.writeFileSync(path.join(root,'run.json'),JSON.stringify(receipt));
 assert.equal(scanProject(root).workflow.collected.runs[0].status,'refused');
});

test('empty walkthrough guidance explains local authoring, snapshot refresh and keeps the free map intact', async () => {
  for (const offline of [false, true]) {
    const input = model('empty-journey'); input.outcomes = [];
    const ui = await client(input, offline);
    assert.equal(ui.get('mapViewButton').attributes['aria-pressed'], 'true');
    ui.get('walkthroughViewButton').click();
    assert.match(ui.get('detail').innerHTML, /Describe your first walkthrough/);
    assert.match(ui.get('detail').innerHTML, /PATH --walkthrough/);
    assert.match(ui.get('detail').innerHTML, /PATH --init/);
    assert.match(ui.get('detail').innerHTML, /starts unproved/);
    assert.match(ui.get('detail').innerHTML, offline ? /create a new export/ : /next refresh/);
    assert.equal(ui.get('detail').children.at(-1).classes.has('finished-product'), true);
    if (!offline) {
      const next = model('plan-arrived');
      next.outcomes = [{ id: 'new', name: 'Our goal', status: 'unproved', steps: [] }];
      ui.setModel(next); await ui.refresh();
      assert.match(ui.get('detail').innerHTML, /Choose a goal/);
      assert.doesNotMatch(ui.get('detail').innerHTML, /PATH --walkthrough/);
      assert.equal(ui.get('outcomes').children[0].dataset.outcomeId, 'new');
    } else assert.deepEqual(ui.counts(), { requests: 0, polls: 0 });
    ui.get('mapViewButton').click();
    assert.equal(ui.get('mapShell').hidden, false); assert.equal(ui.get('fitButton').hidden, false);
    assert.ok(ui.get('nodeLayer').children.some(n => n.dataset.id === 'a'));
    assert.equal(input.project.counts.coded, 1); assert.deepEqual(input.edges, []);
  }
  const remote = model('remote'); remote.project.source = { kind: 'github', url: 'https://github.com/owner/repo', revision: 'abc', snapshot: true };
  const ui = await client(remote); ui.get('walkthroughViewButton').click();
  assert.match(ui.get('detail').innerHTML, /Work on a local checkout/);
});

test('client renders escaped claims and separate source/declared connection provenance', async () => {
  const input = model('one', [piece('a', { name: '<img onerror=evil()>', evidence: { status: 'verified', note: '<script>evil</script>' }, evidenceAssessment: { accepted: false, reason: 'Claim rejected.' } }), piece('b')]);
  input.edges = [{ from: 'a', to: 'b', type: 'code', observations: [{ importer: 'b.js', imported: 'a.js' }] }, { from: 'a', to: 'b', type: 'planned', observed: true }];
  input.gaps = [{ nodeId: 'a', priority: 'blocker', kind: 'unsupported-evidence', message: 'Claim rejected.' }];
  const ui = await client(input);
  const card = ui.get('nodeLayer').children.find(e => e.dataset.id === 'a');
  assert.match(card.innerHTML, /&lt;img/); assert.ok(card.classes.has('has-gap'));
  ui.get('gaps').children[0].click();
  assert.match(ui.get('detail').innerHTML, /Recorded claim: verified · rejected/);
  assert.match(ui.get('detail').innerHTML, /&lt;script&gt;/);
  assert.match(ui.get('detail').innerHTML, /b.js references a.js/);
  assert.match(ui.get('detail').innerHTML, /Declared · also observed/);
  assert.equal(ui.get('edgeLayer').children.length, 1);
});

test('refresh preserves selection, reports failures, recovers, and clears a removed piece', async () => {
  const ui = await client(model('one'));
  ui.get('nodeLayer').children.find(e => e.dataset.id === 'a').click();
  ui.setModel(model('two', [piece('a', { purpose: 'Updated behavior.' })])); await ui.refresh();
  assert.match(ui.get('detail').innerHTML, /Updated behavior/);
  assert.ok(ui.get('nodeLayer').children.find(e => e.dataset.id === 'a').classes.has('selected'));
  ui.fail(true); await ui.refresh(); assert.match(ui.get('refreshStatus').textContent, /showing last snapshot/);
  ui.fail(false); await ui.refresh(); assert.equal(ui.get('refreshStatus').textContent, 'Updated just now');
  ui.setModel(model('three', [])); await ui.refresh(); assert.match(ui.get('detail').innerHTML, /Piece removed/);
});

test('fit actually scales the map and search can find evidence states', async () => {
  const ui = await client(model('one', [piece('a', { status: 'verified' }), piece('b')]));
  assert.equal(ui.get('sizeButton').attributes['aria-pressed'], 'true');
  ui.get('fitButton').click(); assert.notEqual(ui.get('mapCanvas').style.transform, 'scale(1)');
  assert.equal(ui.get('fitButton').attributes['aria-pressed'], 'true');
  assert.equal(ui.get('sizeButton').attributes['aria-pressed'], 'false');
  ui.get('sizeButton').click(); assert.equal(ui.get('mapCanvas').style.transform, 'scale(1)');
  assert.equal(ui.get('fitButton').attributes['aria-pressed'], 'false');
  ui.get('search').listeners.input({ target: { value: 'verified' } });
  assert.equal(ui.get('nodeLayer').children.find(e => e.dataset.id === 'a').classes.has('filtered'), false);
  assert.equal(ui.get('nodeLayer').children.find(e => e.dataset.id === 'b').classes.has('filtered'), true);
});

test('offline snapshot renders the same client without HTTP requests or polling', async () => {
  const input = model('captured'); input.generatedAt = '2026-10-13T10:00:00Z';
  const ui = await client(input, true);
  assert.deepEqual(ui.counts(), { requests: 0, polls: 0 });
  assert.match(ui.get('refreshStatus').textContent, /^Snapshot · /);
  assert.match(ui.get('mode').textContent, /snapshot/);
  assert.ok(ui.get('nodeLayer').children.find(e => e.dataset.id === 'a'));
});

test('inspector labels architecture drift and shows file claims without granting component proof', async () => {
  const input = model('drift', [piece('a'), piece('b', { fileEvidence: [{ file: 'b.js', evidence: { status: 'verified', note: 'Only one file was checked.' }, assessment: { accepted: true, reason: 'Freshness unknown.' } }] })]);
  input.edges = [{ from: 'a', to: 'b', type: 'code', planStatus: 'undeclared', observations: [{ importer: 'b.js', imported: 'a.js' }] }];
  input.gaps = [{ kind: 'unexpected-dependency', nodeId: 'b', priority: 'warning', message: 'Outside declared plan.' }];
  const ui = await client(input); ui.get('gaps').children[0].click();
  assert.match(ui.get('detail').innerHTML, /Observed · outside declared plan/);
  assert.match(ui.get('detail').innerHTML, /File-only claim: b.js/);
  assert.match(ui.get('detail').innerHTML, /does not grant the component a higher state/);
  assert.match(ui.get('detail').innerHTML, /File claim: verified · accepted/);
});

test('project evidence findings open the mission inspector with safely escaped raw claims', async () => {
  const input = model('orphan');
  input.gaps = [{ kind: 'unmapped-evidence', nodeId: null, priority: 'blocker', message: 'Unknown evidence target.', evidence: { status: 'live', note: '<img src=x onerror=evil()>' } }];
  const ui = await client(input); ui.get('gaps').children[0].click();
  assert.match(ui.get('detail').innerHTML, /Unknown evidence target/);
  assert.match(ui.get('detail').innerHTML, /&lt;img src=x/);
  assert.doesNotMatch(ui.get('detail').innerHTML, /<img src=x/);
});

test('GitHub provenance shows ref/revision and makes clone snapshot behavior explicit', async () => {
  const input = model('github'); input.project.source = { kind: 'github', url: 'https://github.com/owner/repo', ref: 'feature/map', revision: 'a'.repeat(40), snapshot: true };
  const ui = await client(input);
  assert.match(ui.get('projectSource').textContent, /GitHub snapshot/);
  assert.match(ui.get('projectSource').textContent, /feature\/map/);
  assert.match(ui.get('projectSource').textContent, /aaaaaaaaaaaa/);
});

test('search removes filtered cards from keyboard navigation and gap selection reveals its piece', async () => {
  const input = model('search', [piece('a'), piece('b', { conflictingFiles: ['b.js'] })]);
  input.gaps = [{ nodeId: 'b', kind: 'overlapping-file', priority: 'blocker', message: 'Ownership conflict.' }];
  const ui = await client(input);
  ui.get('search').listeners.input({ target: { value: 'a.js' } });
  const card = id => ui.get('nodeLayer').children.find(e => e.dataset.id === id);
  assert.equal(card('b').tabIndex, -1); assert.equal(card('b').attributes['aria-hidden'], 'true');
  ui.get('gaps').children[0].click();
  assert.equal(card('b').classes.has('filtered'), false);
  assert.equal(card('b').tabIndex, 0); assert.equal(card('b').attributes['aria-hidden'], 'false');
  assert.match(ui.get('detail').innerHTML, /b.js · ownership conflict/);
  card('a').click(); assert.equal(card('b').tabIndex, -1);
});

test('receipt inspector shows recorded/current inputs and safely labels their limited scope', async () => {
  const file = '<img src=x onerror=evil()>.json';
  const receipt = { status: 'verified', note: 'Check recorded.', inputHashes: { [file]: '0'.repeat(64) } };
  const assessment = { accepted: false, binding: 'stale', reason: 'Input changed.', inputs: {
    binding: 'stale', currentHashes: { [file]: 'a'.repeat(64), 'gone.json': null }, issues: [{ file, reason: '<script>changed</script>' }] } };
  const input = model('inputs', [piece('a', { evidence: receipt, evidenceAssessment: assessment,
    fileEvidence: [{ file: 'a.js', evidence: receipt, assessment }] })]);
  const ui = await client(input); ui.get('nodeLayer').children.find(e => e.dataset.id === 'a').click();
  const detail = ui.get('detail').innerHTML;
  assert.match(detail, /Selected input bindings · stale/);
  assert.match(detail, /Only explicitly listed inputs are covered/);
  assert.match(detail, /Recorded input hashes/); assert.match(detail, /Current input hashes/);
  assert.match(detail, /000000000000/); assert.match(detail, /aaaaaaaaaaaa/);
  assert.match(detail, /gone.json/); assert.match(detail, /Unavailable/);
  assert.match(detail, /&lt;img/); assert.match(detail, /&lt;script&gt;/);
  assert.doesNotMatch(detail, /<img|<script>/);
  assert.match(detail, /File claim: verified · rejected/);
});

test('inspector labels HTTP path matching as source evidence and escapes endpoint/location metadata', async () => {
  const input = model('http', [piece('server'), piece('client')]);
  input.edges = [{ from:'server', to:'client', type:'code', planStatus:'matched', observations:[{
    kind:'http-source', importer:'client.js', imported:'server.js', method:'GET', endpoint:'/<img onerror=evil()>',
    importerLocation:{line:12,column:4}, providerLocation:{line:8,column:'<script>evil</script>'}, providerMethod:null
  }] }];
  const ui = await client(input); ui.get('nodeLayer').children.find(e => e.dataset.id === 'client').click();
  const detail = ui.get('detail').innerHTML;
  assert.match(detail, /Observed HTTP path match · heuristic/); assert.match(detail, /client.js:12:4 requests GET/);
  assert.match(detail, /method unresolved/); assert.match(detail, /runtime origin\/execution unproved/);
  assert.match(detail, /&lt;img/); assert.match(detail, /&lt;script&gt;/); assert.doesNotMatch(detail, /<img|<script>/);
});

test('cards preview file inventory safely and inspector lists the full declared scope', async () => {
  const files = ['src/first.js', 'src/<img onerror=evil()>.js', 'src/third.js', 'src/planned.js'];
  const ui = await client(model('files', [piece('a', { status: 'planned', files, presentFiles: [files[0], files[2]] }),
    piece('empty', { files: [], presentFiles: [] }), piece('__mission__', { kind: 'mission', files: [], presentFiles: [] })]));
  const card = id => ui.get('nodeLayer').children.find(e => e.dataset.id === id);
  assert.match(card('a').innerHTML, /4 files · 2 present · 2 missing/);
  assert.match(card('a').innerHTML, /&lt;img onerror=evil\(\)&gt;.js · missing/);
  assert.doesNotMatch(card('a').innerHTML, /<img/);
  assert.match(card('a').innerHTML, /\+2 more · select to see all/);
  assert.match(card('a').attributes['aria-label'], /2 missing/);
  assert.doesNotMatch(card('__mission__').innerHTML, /node-files/);
  card('a').click();
  for (const file of ['src/first.js', 'src/third.js', 'src/planned.js · missing']) assert.ok(ui.get('detail').innerHTML.includes(file));
  card('empty').click();
  assert.match(ui.get('detail').innerHTML, /No implementation files assigned yet/);
  assert.doesNotMatch(ui.get('detail').innerHTML, /this is the mission/);
});

test('live scanned files appear separately, move into declared components, and remain visible when missing', async t => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'buildmap-ui-files-'));
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  fs.mkdirSync(path.join(root, '.buildmap'));
  fs.mkdirSync(path.join(root, 'src'));
  const manifest = { mission: 'Track the build.', components: [{ id: 'engine', files: ['src/engine.js', 'src/planned.js'] }] };
  const saveManifest = () => fs.writeFileSync(path.join(root, '.buildmap/project.json'), JSON.stringify(manifest));
  saveManifest();
  const ui = await client(scanProject(root));
  const card = id => ui.get('nodeLayer').children.find(e => e.dataset.id === id);
  assert.match(card('engine').innerHTML, /2 files · 0 present · 2 missing/);
  fs.writeFileSync(path.join(root, 'src/engine.js'), 'export const engine = true;');
  fs.writeFileSync(path.join(root, 'src/helper.js'), 'export const helper = true;');
  ui.setModel(scanProject(root)); await ui.refresh();
  assert.match(card('engine').innerHTML, /2 files · 1 present · 1 missing/);
  card('file:src/helper.js').click();
  assert.match(ui.get('detail').innerHTML, /Discovered source file/);
  manifest.components[0].files.push('src/helper.js'); saveManifest();
  ui.setModel(scanProject(root)); await ui.refresh();
  assert.equal(card('file:src/helper.js'), undefined);
  card('engine').click();
  assert.match(ui.get('detail').innerHTML, /src\/helper.js/);
  fs.unlinkSync(path.join(root, 'src/engine.js'));
  ui.setModel(scanProject(root)); await ui.refresh();
  assert.match(card('engine').innerHTML, /3 files · 1 present · 2 missing/);
  assert.match(ui.get('detail').innerHTML, /src\/engine.js · missing/);
  assert.ok(card('engine').classes.has('planned'));
});

test('guided free builder flow creates a piece, follows file arrival and makes its declared walkthrough available without proof', async t => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'buildmap-piece-flow-'));
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  fs.writeFileSync(path.join(root, 'main.js'), 'export const main = true;');
  const run = (flag, input) => {
    const r = spawnSync(process.execPath, ['src/cli.js', root, flag], { input, encoding: 'utf8', timeout: 5000 });
    assert.equal(r.status, 0, r.stderr); return r;
  };
  run('--init', 'Our build\nHelp builders inspect their project.\nA clear map.\n\n');
  const ui = await client(scanProject(root));
  const card = id => ui.get('nodeLayer').children.find(n => n.dataset.id === id);
  card('file:main.js').click(); assert.match(ui.get('detail').innerHTML, /--piece/);
  run('--piece', 'Core\nMake useful output.\nSupports the project.\n1\nfuture.js\n\nyes\n');
  ui.setModel(scanProject(root)); await ui.refresh();
  assert.equal(card('file:main.js'), undefined); assert.match(ui.get('detail').innerHTML, /Piece removed/);
  card('core').click(); assert.match(card('core').innerHTML, /2 files · 1 present · 1 missing/);
  assert.match(ui.get('detail').innerHTML, /future.js · missing/);
  fs.writeFileSync(path.join(root, 'future.js'), "import { main } from './main.js'; export const future = main;");
  ui.setModel(scanProject(root)); await ui.refresh();
  assert.match(card('core').innerHTML, /2 files · 2 present/);
  assert.ok(card('core').classes.has('connected'));
  run('--walkthrough', 'Inspect build\nUnderstand the output.\n1\nRead the core\nUseful output is available.\n\n\n\nyes\n');
  const final = scanProject(root); ui.setModel(final); await ui.refresh();
  ui.get('outcomes').children[0].click();
  assert.match(ui.get('detail').innerHTML, /OUTCOME WALKTHROUGH/); assert.equal(ui.get('mapShell').hidden, false);
  assert.ok(ui.get('detail').children.some(e => e.classes.has('task-brief')));
  assert.equal(final.project.counts.verified, 0); assert.equal(final.project.counts.live, 0);
  assert.equal(final.outcomes[0].status, 'unproved'); assert.equal(final.outcomes[0].steps[0].state, 'unobserved');
});

test('free evidence review separates file presence, accepted claims, unknown freshness, rejected inputs and file-only proof', async t => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'buildmap-evidence-review-'));
  t.after(() => fs.rmSync(root, { recursive: true, force: true })); fs.mkdirSync(path.join(root, '.buildmap'));
  fs.writeFileSync(path.join(root, 'main.js'), 'export const main = true;'); fs.writeFileSync(path.join(root, 'data.json'), '{}');
  fs.writeFileSync(path.join(root, '.buildmap/project.json'), JSON.stringify({ components: [
    { id: 'main', files: ['main.js'] }, { id: 'planned', files: ['missing.js'] }
  ] }));
  const initial = scanProject(root), sourceHashes = initial.nodes.find(n => n.id === 'main').sourceHashes;
  const receipt = { status: 'verified', note: '<script>Recorded result</script>', sourceHashes, inputHashes: { 'data.json': sourceHashes['main.js'] } };
  const save = value => fs.writeFileSync(path.join(root, '.buildmap/evidence.json'), JSON.stringify(value));
  // Read the current input hash through the existing assessment, then bind the fixture.
  save({ components: { main: receipt } }); receipt.inputHashes = scanProject(root).nodes.find(n => n.id === 'main').evidenceAssessment.inputs.currentHashes;
  save({ components: { main: receipt } });
  const originalInputs = { ...receipt.inputHashes };
  for (const offline of [false, true]) {
    const input = scanProject(root), original = JSON.stringify(input), ui = await client(input, offline);
    const choose = id => ui.get('nodeLayer').children.find(n => n.dataset.id === id).click(); choose('main');
    assert.match(ui.get('detail').innerHTML, /1 of 1 assigned files are present/);
    assert.match(ui.get('detail').innerHTML, /accepted for this piece/); assert.match(ui.get('detail').innerHTML, /match the captured files/);
    assert.match(ui.get('detail').innerHTML, /Only the explicitly listed inputs match/);
    assert.match(ui.get('detail').innerHTML, /&lt;script&gt;Recorded result/); assert.doesNotMatch(ui.get('detail').innerHTML, /<script>/);
    assert.match(ui.get('detail').innerHTML, /does not run or authenticate/); assert.match(ui.get('detail').innerHTML, /recorded check/);
    assert.match(ui.get('detail').innerHTML, /components\[&quot;main&quot;\]/);
    choose('planned'); assert.match(ui.get('detail').innerHTML, /0 of 1 assigned files are present; implementation is incomplete/);
    assert.equal(JSON.stringify(input), original);
    if (offline) { assert.deepEqual(ui.counts(), { requests: 0, polls: 0 }); continue; }
    choose('main'); fs.writeFileSync(path.join(root, 'data.json'), '{"changed":true}'); ui.setModel(scanProject(root)); await ui.refresh();
    assert.match(ui.get('detail').innerHTML, /not accepted for this piece/); assert.match(ui.get('detail').innerHTML, /does not match the captured source, plan or selected inputs/);
    assert.match(ui.get('detail').innerHTML, /repeat the observation or check before replacing hashes/i);
    receipt.inputHashes = { 'data.json': 'invalid' }; save({ components: { main: receipt } }); ui.setModel(scanProject(root)); await ui.refresh();
    assert.match(ui.get('detail').innerHTML, /recorded binding is invalid/);
    save({ components: { main: { status: 'verified', note: 'Unbound claim.' } } }); ui.setModel(scanProject(root)); await ui.refresh();
    assert.match(ui.get('detail').innerHTML, /freshness is unknown/);
    save({ files: { 'main.js': { status: 'verified', note: 'File only.', sourceHashes } } }); ui.setModel(scanProject(root)); await ui.refresh();
    assert.match(ui.get('detail').innerHTML, /No supported piece-level behavior claim/);
    assert.match(ui.get('detail').innerHTML, /File-only claim/); assert.match(ui.get('detail').innerHTML, /cannot prove the whole component/);
    assert.equal(scanProject(root).nodes.find(n => n.id === 'main').status, 'coded');
    // Restore the captured fixture for the independent offline iteration.
    fs.writeFileSync(path.join(root, 'data.json'), '{}'); save({ components: { main: { status: 'verified', note: '<script>Recorded result</script>', sourceHashes,
      inputHashes: originalInputs } } });
  }
});

test('free walkthrough evidence review distinguishes absent, partial, failed, accepted and stale examples from piece checks', async t => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'buildmap-example-review-'));
  t.after(() => fs.rmSync(root, { recursive: true, force: true })); fs.mkdirSync(path.join(root, '.buildmap'));
  fs.writeFileSync(path.join(root, 'a.js'), 'export const a = 1;'); fs.writeFileSync(path.join(root, 'b.js'), 'export const b = 1;');
  const plan = { outcomes: [{ id: 'goal', goal: 'Show a useful result.', steps: [
    { id: 'a', nodeId: 'file:a.js', label: 'First', expected: 'An intended result.' }, { id: 'b', nodeId: 'file:b.js', label: 'Second', expected: 'A final result.' }
  ] }] };
  const planPath = path.join(root, '.buildmap/project.json'); fs.writeFileSync(planPath, JSON.stringify(plan));
  const initial = scanProject(root), outcome = initial.outcomes[0];
  const claims = { files: Object.fromEntries(initial.nodes.filter(n => n.kind === 'file').map(n => [n.files[0], { status: 'verified', note: 'Piece fixture check.', sourceHashes: n.sourceHashes }])) };
  const save = () => fs.writeFileSync(path.join(root, '.buildmap/evidence.json'), JSON.stringify(claims)); save();
  const ui = await client(scanProject(root)); ui.get('outcomes').children[0].click();
  assert.match(ui.get('detail').innerHTML, /0 of 2 are currently marked observed/);
  assert.match(ui.get('detail').innerHTML, /whole example remains unproved/);
  const receipt = { status: 'verified', note: 'Fixture example.', sourceHashes: outcome.sourceHashes, definitionHash: outcome.definitionHash,
    example: { name: 'Fixture', input: 0, output: null, steps: [{ stepId: 'a', result: 'observed', input: 0, output: false }] } };
  claims.outcomes = { goal: receipt }; save(); ui.setModel(scanProject(root)); await ui.refresh();
  assert.match(ui.get('detail').innerHTML, /1 of 2 are currently marked observed; 0 failed; 1 lack/);
  assert.match(ui.get('detail').innerHTML, /whole example remains unproved/);
  receipt.example.steps.push({ stepId: 'b', result: 'failed', handoff: 'Passed false onward.', input: false, output: 0 });
  save(); ui.setModel(scanProject(root)); await ui.refresh(); assert.match(ui.get('detail').innerHTML, /1 of 2 are currently marked observed; 1 failed; 0 lack/);
  receipt.example.steps[1].result = 'observed'; receipt.example.output = 0; save(); const accepted = scanProject(root);
  ui.setModel(accepted); await ui.refresh(); assert.match(ui.get('detail').innerHTML, /named example is accepted/);
  assert.match(ui.get('detail').innerHTML, /not every input or the mission/);
  const offline = await client(accepted, true); offline.get('outcomes').children[0].click();
  assert.match(offline.get('detail').innerHTML, /named example is accepted/); assert.deepEqual(offline.counts(), { requests: 0, polls: 0 });
  plan.outcomes[0].steps[1].expected = 'A changed intended result.'; fs.writeFileSync(planPath, JSON.stringify(plan));
  const stale = scanProject(root); ui.setModel(stale); await ui.refresh();
  assert.match(ui.get('detail').innerHTML, /0 of 2 are currently marked observed/);
  assert.match(ui.get('detail').innerHTML, /source, plan or selected inputs/);
  assert.equal(stale.project.counts.verified, 2); assert.equal(stale.outcomes[0].status, 'unproved');
});

test('search locates a piece by any assigned file, safely renders results, and supports Enter/Escape', async () => {
  const file = 'src/<img onerror=evil()>.js';
  const ui = await client(model('search-files', [piece('engine', { name: '<script>Engine</script>',
    files: ['src/first.js', 'src/second.js', file], presentFiles: ['src/first.js', 'src/second.js', file] }), piece('other')]));
  const input = value => ui.get('search').listeners.input({ target: { value } });
  const key = key => { let prevented = false; ui.get('search').listeners.keydown({ key, preventDefault: () => { prevented = true; } }); return prevented; };
  assert.equal(ui.get('searchPanel').hidden, true);
  input('<img');
  assert.match(ui.get('searchStatus').textContent, /^1 match/);
  const result = ui.get('searchResults').children[0];
  assert.equal(result.children[0].textContent, '<script>Engine</script>');
  assert.equal(result.children[1].textContent, `coded · ${file}`);
  assert.equal(key('Enter'), true);
  const card = ui.get('nodeLayer').children.find(e => e.dataset.id === 'engine');
  assert.equal(card.attributes['aria-pressed'], 'true');
  assert.equal(ui.context.document.activeElement, card);
  assert.equal(card.focusOptions.preventScroll, true);
  assert.equal(card.revealOptions.block, 'nearest');
  assert.match(ui.get('detail').innerHTML, /&lt;img/);
  input('no-such-piece');
  assert.match(ui.get('searchStatus').textContent, /No matching pieces/);
  assert.equal(ui.get('searchResults').children.length, 0);
  assert.equal(key('Enter'), false);
  assert.equal(key('Escape'), true);
  assert.equal(ui.get('search').value, '');
  assert.equal(ui.get('searchPanel').hidden, true);
  assert.ok(ui.get('nodeLayer').children.filter(e => e.dataset.id).every(e => e.tabIndex === 0));
});

test('search results disclose all matches, follow edits, and behave the same offline', async () => {
  const nodes = Array.from({ length: 25 }, (_, i) => piece(`p${i}`, { files: [`src/p${i}.js`], presentFiles: [`src/p${i}.js`] }));
  for (const offline of [false, true]) {
    const ui = await client(model('many', nodes), offline);
    ui.get('search').listeners.input({ target: { value: 'src/' } });
    assert.match(ui.get('searchStatus').textContent, /^25 matches/);
    assert.equal(ui.get('searchResults').children.length, 12);
    assert.equal(ui.get('moreResults').hidden, false);
    ui.get('moreResults').click();
    assert.equal(ui.get('searchResults').children.length, 25);
    ui.get('searchResults').children[24].click();
    assert.match(ui.get('detail').innerHTML, /src\/p24.js/);
    assert.ok(ui.get('mapViewport').lastScroll.top > 1000);
    ui.get('fitButton').click();
    ui.get('searchResults').children[24].click();
    assert.equal(ui.get('mapViewport').lastScroll.top, 0); // Fit geometry is scaled.
    ui.get('sizeButton').click();
    if (!offline) {
      ui.setModel(model('edited', nodes.slice(0, 24))); await ui.refresh();
      assert.match(ui.get('searchStatus').textContent, /^24 matches/);
      assert.equal(ui.get('searchResults').children.length, 24);
      assert.match(ui.get('detail').innerHTML, /Piece removed/);
      assert.equal(ui.context.document.activeElement, ui.get('search'));
    } else assert.deepEqual(ui.counts(), { requests: 0, polls: 0 });
  }
});

test('gap navigation reaches a distant card and refresh retains keyboard focus without stealing it', async () => {
  const nodes = Array.from({ length: 30 }, (_, i) => piece(`p${String(i).padStart(2, '0')}`));
  const initial = model('navigation', nodes);
  initial.gaps = [{ nodeId: 'p29', priority: 'warning', kind: 'unproved', message: 'Record useful behavior.' }];
  const ui = await client(initial);
  ui.get('gaps').children[0].click();
  assert.ok(ui.get('mapViewport').lastScroll.top > 6000);
  let card = ui.get('nodeLayer').children.find(e => e.dataset.id === 'p29');
  assert.equal(ui.context.document.activeElement, card);
  ui.setModel(model('next', nodes)); await ui.refresh();
  card = ui.get('nodeLayer').children.find(e => e.dataset.id === 'p29');
  assert.equal(ui.context.document.activeElement, card);
  ui.get('search').focus();
  ui.get('search').listeners.input({ target: { value: 'p00' } });
  ui.setModel(model('third', nodes)); await ui.refresh();
  assert.equal(ui.context.document.activeElement, ui.get('search'));
  ui.get('searchResults').children[0].focus();
  ui.setModel(model('fourth', nodes)); await ui.refresh();
  assert.equal(ui.context.document.activeElement, ui.get('searchResults').children[0]);
  ui.setModel(model('fifth', nodes.slice(1))); await ui.refresh();
  assert.equal(ui.context.document.activeElement, ui.get('search'));
  assert.match(ui.get('searchStatus').textContent, /No matching pieces/);
});

test('scanned outcome walkthroughs show real sample data, navigate pieces, and stale when the goal changes', async t => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'buildmap-ui-outcome-'));
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  fs.mkdirSync(path.join(root, '.buildmap'));
  fs.writeFileSync(path.join(root, 'main.js'), 'export const main = 1;');
  fs.writeFileSync(path.join(root, 'extra.js'), 'export const extra = 1;');
  const plan = { outcomes: [{ id: 'demo', name: '<img onerror=evil()>', goal: 'Display a value.', steps: [
    { id: 'display', nodeId: 'file:main.js', label: 'Display', expected: 'An escaped value.', explanation: 'Show the person the result.', example: 'A project-specific <img onerror=evil()> illustration.' }
  ] }] };
  const save = () => fs.writeFileSync(path.join(root, '.buildmap/project.json'), JSON.stringify(plan));
  save(); const initial = scanProject(root); const outcome = initial.outcomes[0];
  const proof = { status: 'computing', note: 'Recorded a sample.', sourceHashes: outcome.sourceHashes, definitionHash: outcome.definitionHash,
    example: { name: 'Unsafe text displayed safely', input: 0, output: '<script>example</script>', steps: [
      { stepId: 'display', result: 'observed', input: 0, output: '<script>example</script>' }
    ] } };
  fs.writeFileSync(path.join(root, '.buildmap/evidence.json'), JSON.stringify({ outcomes: { demo: proof } }));
  const ui = await client(scanProject(root));
  ui.get('walkthroughViewButton').click();
  assert.match(ui.get('outcomes').children[0].innerHTML, /&lt;img/);
  ui.get('search').listeners.input({ target: { value: 'extra.js' } });
  ui.get('outcomes').children[0].click();
  assert.match(ui.get('detail').innerHTML, /OUTCOME WALKTHROUGH/);
  assert.match(ui.get('detail').innerHTML, /Observed example/);
  const steps = ui.get('detail').children[0];
  assert.match(steps.children[0].innerHTML, /&lt;script&gt;example/);
  assert.match(steps.children[0].innerHTML, /In plain English/);
  assert.match(steps.children[0].innerHTML, /Show the person the result/);
  assert.match(steps.children[0].innerHTML, /Example for this project · illustration/);
  assert.match(steps.children[0].innerHTML, /project-specific &lt;img/);
  assert.doesNotMatch(steps.children[0].innerHTML, /<script>/);
  const card = id => ui.get('nodeLayer').children.find(n => n.dataset.id === id);
  assert.ok(card('file:main.js').classes.has('in-outcome'));
  assert.equal(card('file:main.js').tabIndex, 0); // The active outcome remains visible through search.
  assert.ok(card('file:extra.js').classes.has('outside-outcome'));
  steps.children[0].children[0].click();
  assert.match(ui.get('detail').innerHTML, /PIECE INSPECTOR/);
  ui.get('detail').children.find(e => e.classes.has('return-outcome')).click();
  assert.match(ui.get('detail').innerHTML, /OUTCOME WALKTHROUGH/);
  plan.outcomes[0].goal = 'A changed goal.'; save(); ui.setModel(scanProject(root)); await ui.refresh();
  assert.match(ui.get('detail').innerHTML, /A changed goal/);
  assert.match(ui.get('detail').children[0].children[0].innerHTML, /Example out of date/);
  assert.equal(ui.context.document.activeElement, ui.get('outcomes').children[0]);
  plan.outcomes = []; save(); ui.setModel(scanProject(root)); await ui.refresh();
  assert.match(ui.get('detail').innerHTML, /Outcome removed/);
  assert.equal(ui.context.document.activeElement, ui.get('walkthroughViewButton'));
});

test('outcome gaps open the walkthrough and shared offline navigation makes no requests', async () => {
  const input = model('outcome', [piece('a'), piece('b')]);
  input.outcomes = [{ id: 'goal', name: 'Useful result', goal: 'Produce a useful result.', status: 'unproved', nodeIds: ['a'], supports: [],
    steps: [{ id: 'first', nodeId: 'a', label: 'Do work', expected: 'Useful output.', pieceName: 'a', pieceStatus: 'coded', state: 'unobserved', observation: null }],
    firstGap: { label: 'Do work', state: 'unobserved' }, evidence: null, evidenceAssessment: { accepted: false, reason: 'No recorded example.' }, sourceHashes: {}, definitionHash: 'a'.repeat(64) }];
  input.gaps = [{ id: 'outcome-gap', kind: 'unproved-outcome', outcomeId: 'goal', nodeId: null, priority: 'info', message: 'Record an example.' },
    { id: 'piece-gap', kind: 'unproved', nodeId: 'b', priority: 'warning', message: 'Observe this piece.' }];
  for (const offline of [false, true]) {
    const ui = await client(input, offline);
    assert.equal(ui.get('gaps').children.length, 1);
    ui.get('gaps').children[0].click();
    assert.match(ui.get('detail').innerHTML, /PIECE INSPECTOR/);
    assert.equal(ui.get('gaps').children[0].attributes['aria-pressed'], 'true');
    if (!offline) { ui.setModel({ ...input, fingerprint: 'refreshed' }); await ui.refresh();
      assert.equal(ui.get('gaps').children[0].attributes['aria-pressed'], 'true'); }
    ui.get('walkthroughViewButton').click();
    assert.equal(ui.get('gaps').children.length, 1);
    ui.get('gaps').children[0].click();
    assert.match(ui.get('detail').innerHTML, /OUTCOME WALKTHROUGH/);
    assert.match(ui.get('detail').innerHTML, /Do work · No observation recorded/);
    assert.equal(ui.get('gaps').children[0].attributes['aria-pressed'], 'true');
    assert.equal(ui.get('clearOutcome').hidden, false);
    ui.get('clearOutcome').click();
    assert.equal(ui.get('clearOutcome').hidden, true);
    assert.equal(ui.get('gaps').children[0].attributes['aria-pressed'], 'true'); // Free-map selection is retained.
    assert.ok(ui.get('nodeLayer').children.filter(n => n.dataset.id).every(n => !n.classes.has('outside-outcome')));
    if (offline) assert.deepEqual(ui.counts(), { requests: 0, polls: 0 });
  }
});

test('the free map and free walkthrough are reading views over unchanged evidence, with preserved navigation', async () => {
  const input = model('views', [piece('a'), piece('b')]);
  input.outcomes = [{ id: 'goal', name: 'Useful result', goal: 'Produce a useful result.', status: 'unproved', nodeIds: ['b'], supports: [],
    steps: [{ id: 'first', nodeId: 'b', label: 'Do work', expected: 'Useful output.', pieceName: 'b', pieceStatus: 'coded', state: 'unobserved', observation: null }],
    firstGap: { label: 'Do work', state: 'unobserved' }, evidence: null, evidenceAssessment: { accepted: false, reason: 'No recorded example.' }, sourceHashes: {}, definitionHash: 'a'.repeat(64) }];
  input.gaps = [{ id: 'source-a', kind: 'unproved', nodeId: 'a', priority: 'warning', message: 'Observe a.' },
    { id: 'source-b', kind: 'no-observed-connection', nodeId: 'b', priority: 'warning', message: 'Review b wiring.' },
    { id: 'goal-gap', kind: 'unproved-outcome', outcomeId: 'goal', nodeId: null, scope: 'outcome', priority: 'info', message: 'Record this journey.' },
    { id: 'scope-gap', kind: 'unassigned-outcome', nodeId: 'a', scope: 'outcome', priority: 'info', message: 'Review outcome assignment.' },
    { id: 'orphan', kind: 'unmapped-outcome-evidence', nodeId: null, scope: 'outcome', priority: 'warning', message: 'Unknown outcome receipt.', evidence: { note: '<script>old claim</script>' } }];
  const original = JSON.stringify(input);
  for (const offline of [false, true]) {
    const ui = await client(input, offline);
    const card = id => ui.get('nodeLayer').children.find(n => n.dataset.id === id);
    assert.equal(ui.get('mapViewButton').attributes['aria-pressed'], 'true');
    assert.equal(ui.get('outcomesPanel').hidden, false);
    assert.equal(ui.get('mapShell').hidden, false);
    assert.equal(ui.get('gaps').children.length, 2);
    card('a').click(); ui.get('fitButton').click();
    ui.get('search').listeners.input({ target: { value: 'a.js' } });
    const index = ui.get('progressText').textContent;
    ui.get('walkthroughViewButton').click();
    assert.equal(ui.get('mapShell').hidden, true);
    assert.equal(ui.get('missionPanel').hidden, true);
    assert.equal(ui.get('outcomesPanel').hidden, false);
    assert.equal(ui.get('fitButton').hidden, true);
    assert.equal(ui.get('gaps').children.length, 3);
    assert.match(ui.get('detail').innerHTML, /Choose a goal/);
    ui.get('gaps').children[2].click();
    assert.match(ui.get('detail').innerHTML, /Unknown outcome receipt/);
    assert.match(ui.get('detail').innerHTML, /&lt;script&gt;old claim/);
    ui.get('outcomes').children[0].click();
    assert.match(ui.get('detail').innerHTML, /OUTCOME WALKTHROUGH/);
    ui.get('clearOutcome').click();
    assert.equal(ui.get('mapShell').hidden, false);
    assert.equal(ui.get('missionPanel').hidden, false);
    assert.equal(ui.get('progressText').textContent, index);
    assert.match(ui.get('detail').innerHTML, /PIECE INSPECTOR/);
    assert.ok(card('a').classes.has('selected'));
    assert.ok(card('b').classes.has('filtered'));
    assert.equal(ui.get('fitButton').attributes['aria-pressed'], 'true');
    assert.equal(ui.get('gaps').children.length, 2);
    ui.get('walkthroughViewButton').click();
    assert.match(ui.get('detail').innerHTML, /OUTCOME WALKTHROUGH/);
    ui.get('detail').children[0].children[0].children[0].click();
    assert.equal(ui.get('mapShell').hidden, false);
    assert.match(ui.get('detail').innerHTML, /<h2>b<\/h2>/);
    assert.equal(card('b').tabIndex, 0);
    ui.get('detail').children.find(e => e.classes.has('return-outcome')).click();
    assert.match(ui.get('detail').innerHTML, /OUTCOME WALKTHROUGH/);
    assert.equal(JSON.stringify(input), original);
    if (offline) assert.deepEqual(ui.counts(), { requests: 0, polls: 0 });
  }
});

test('map goals open a free walkthrough beside the graph with bounded briefs, refresh and clear-focus navigation', async t => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'buildmap-free-goals-'));
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  fs.mkdirSync(path.join(root, '.buildmap'));
  fs.writeFileSync(path.join(root, 'main.js'), 'export const value = 7;');
  fs.writeFileSync(path.join(root, 'other.js'), 'export const other = 3;');
  const plan = { mission: 'Help this builder.', outcomes: [{ id: 'goal', name: '<Our goal>', goal: 'Produce useful output.',
    steps: [{ id: 'first', nodeId: 'file:main.js', label: 'Read this build', expected: 'Useful output.' }] }] };
  const save = () => fs.writeFileSync(path.join(root, '.buildmap/project.json'), JSON.stringify(plan)); save();
  for (const offline of [false, true]) {
    const input = scanProject(root), original = JSON.stringify(input), ui = await client(input, offline);
    const card = id => ui.get('nodeLayer').children.find(n => n.dataset.id === id);
    ui.get('fitButton').click(); ui.get('search').listeners.input({ target: { value: 'other.js' } });
    ui.get('outcomes').children[0].click();
    assert.equal(ui.get('mapViewButton').attributes['aria-pressed'], 'true');
    for (const id of ['mapShell', 'missionPanel', 'mapSidebar', 'fitButton']) assert.equal(ui.get(id).hidden, false);
    assert.match(ui.get('detail').innerHTML, /OUTCOME WALKTHROUGH/);
    assert.match(ui.get('detail').innerHTML, /&lt;Our goal&gt;/);
    assert.ok(card('file:main.js').classes.has('in-outcome')); assert.equal(card('file:main.js').tabIndex, 0);
    assert.equal(ui.get('clearOutcome').textContent, 'Clear goal focus');
    const brief = () => ui.get('detail').children.find(e => e.classes.has('task-brief'));
    assert.equal(brief().children[0].textContent, 'Keep your agent focused');
    assert.match(brief().children[2].children[1].value, /"goal": "Produce useful output."/);
    assert.match(brief().children[2].children[1].value, /Avoid unrelated features, dependencies, and refactors/);
    await brief().children[3].click(); assert.equal(brief().children[2].open, true);
    if (!offline) {
      const active = ui.get('outcomes').children[0]; active.focus();
      plan.outcomes[0].steps[0].expected = 'Updated useful output.'; save();
      ui.setModel(scanProject(root)); await ui.refresh();
      assert.match(ui.get('detail').children[0].children[0].innerHTML, /Updated useful output/);
      assert.equal(ui.context.document.activeElement, ui.get('outcomes').children[0]);
    }
    ui.get('clearOutcome').click();
    assert.equal(card('file:main.js').classes.has('in-outcome'), false);
    assert.equal(card('file:main.js').tabIndex, -1); // The original search still applies.
    assert.equal(ui.get('fitButton').attributes['aria-pressed'], 'true');
    ui.get('outcomes').children[0].click();
    ui.get('detail').children[0].children[0].children[0].click();
    assert.match(ui.get('detail').innerHTML, /PIECE INSPECTOR/);
    assert.equal(ui.get('mapShell').hidden, false);
    ui.get('detail').children.find(e => e.classes.has('return-outcome')).click();
    assert.match(ui.get('detail').innerHTML, /OUTCOME WALKTHROUGH/);
    if (!offline) {
      ui.get('mapViewButton').click(); ui.get('outcomes').children[0].click();
      plan.outcomes = []; save(); ui.setModel(scanProject(root)); await ui.refresh();
      assert.match(ui.get('detail').innerHTML, /Outcome removed/);
      assert.equal(ui.context.document.activeElement, ui.get('mapViewButton'));
      plan.outcomes = [{ id: 'goal', name: '<Our goal>', goal: 'Produce useful output.', steps: [{ id: 'first', nodeId: 'file:main.js', label: 'Read this build', expected: 'Useful output.' }] }]; save();
    } else assert.deepEqual(ui.counts(), { requests: 0, polls: 0 });
    assert.equal(JSON.stringify(input), original); assert.equal(input.outcomes[0].status, 'unproved');
    assert.equal(input.project.counts.verified, 0); assert.equal(input.project.counts.live, 0);
  }
});

test('Guide code preview reads scanned functions safely, follows refresh and returns to the full free inspector offline or live', async t => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'buildmap-code-preview-'));
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  fs.mkdirSync(path.join(root, '.buildmap'));
  const file = path.join(root, 'main.js');
  const initial = `export function first(input) { return service['<img onerror=evil()>'](input); }`;
  fs.writeFileSync(file, initial);
  for (const offline of [false, true]) {
    fs.writeFileSync(file, initial);
    const input = scanProject(root), original = JSON.stringify(input), ui = await client(input, offline);
    const card = () => ui.get('nodeLayer').children.find(n => n.dataset.id === 'file:main.js');
    card().click(); ui.get('fitButton').click();
    const open = () => ui.get('detail').children.find(e => e.classes.has('guide-open'));
    assert.ok(ui.get('detail').children.some(e => e.classes.has('task-brief')));
    open().click(); assert.match(ui.get('detail').innerHTML, /BUILDMAP GUIDE · CODE PREVIEW/);
    assert.equal(ui.get('mapShell').hidden, false);
    const source = () => ui.get('detail').children.find(e => e.classes.has('code-guide'));
    assert.match(source().children[0].innerHTML, /first/);
    assert.match(source().children[0].innerHTML, /&lt;img onerror/);
    assert.doesNotMatch(source().children[0].innerHTML, /<img|<script>/);
    assert.match(source().children[0].innerHTML, /target not resolved/);
    assert.match(source().innerHTML, /SHA-256/);
    assert.equal(ui.get('detail').children.at(-1).classes.has('finished-product'), true);
    if (!offline) {
      fs.writeFileSync(file, 'export function second(value) { return { output: value + 1 }; }');
      ui.setModel(scanProject(root)); await ui.refresh();
      assert.match(ui.get('detail').innerHTML, /CODE PREVIEW/); assert.match(source().children[0].innerHTML, /second/);
      assert.doesNotMatch(source().children[0].innerHTML, /first/);
    } else assert.deepEqual(ui.counts(), { requests: 0, polls: 0 });
    ui.get('detail').children.find(e => e.classes.has('guide-back')).click();
    assert.match(ui.get('detail').innerHTML, /PIECE INSPECTOR/);
    assert.ok(ui.get('detail').children.some(e => e.classes.has('task-brief')));
    assert.equal(ui.get('fitButton').attributes['aria-pressed'], 'true');
    assert.ok(card().classes.has('selected')); assert.equal(JSON.stringify(input), original);
    assert.equal(input.project.counts.verified, 0); assert.equal(input.project.counts.live, 0);
    if (!offline) {
      open().click(); fs.rmSync(file); ui.setModel(scanProject(root)); await ui.refresh();
      assert.match(ui.get('detail').innerHTML, /Piece removed/);
    }
  }
});

test('Guide follows resolved same-file calls, keeps current reading focus, and discards stale function controls', async t => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'buildmap-code-navigation-'));
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  const sourcePath = path.join(root, 'core.js');
  fs.writeFileSync(sourcePath, 'export function result(input) { return twice(input.amount); }\nfunction twice(value) { return value * 2; }');
  for (const offline of [false, true]) {
    const input = scanProject(root), original = JSON.stringify(input), ui = await client(input, offline);
    ui.get('nodeLayer').children.find(n => n.dataset.id === 'file:core.js').click();
    ui.get('detail').children.find(e => e.classes.has('guide-open')).click();
    assert.equal(ui.context.document.activeElement.classList.contains('guide-back'), true);
    const cards = () => ui.get('detail').children.find(e => e.classes.has('code-guide')).children;
    assert.match(cards()[0].innerHTML, /the value at input.amount/);
    const jump = cards()[0].children.find(e => e.classes.has('guide-call'));
    assert.equal(jump.textContent, 'Read called function: twice'); jump.click();
    assert.equal(cards()[1].open, true); assert.equal(ui.context.document.activeElement, cards()[1]);
    assert.equal(cards()[1].revealOptions.block, 'nearest');
    if (!offline) {
      const oldTarget = cards()[1]; fs.writeFileSync(path.join(root, 'support.js'), 'export const support = 1;');
      ui.setModel(scanProject(root)); await ui.refresh();
      assert.equal(cards()[1].open, true); assert.equal(ui.context.document.activeElement, cards()[1]);
      oldTarget.open = false; jump.click(); assert.equal(oldTarget.open, false);
      fs.writeFileSync(sourcePath, 'export function result(input) { return twice(input.amount); }\nfunction twice(value) { return value * 3; }');
      ui.setModel(scanProject(root)); await ui.refresh();
      assert.equal(cards()[1].open, false); assert.equal(ui.context.document.activeElement.classList.contains('guide-back'), true);
      cards()[1].open = true; cards()[1].listeners.toggle();
      fs.writeFileSync(path.join(root, 'support.js'), 'export const support = 2;'); ui.setModel(scanProject(root)); await ui.refresh();
      assert.equal(cards()[1].open, true);
    } else {
      assert.match(ui.get('detail').innerHTML, /snapshot does not follow later edits/);
      assert.deepEqual(ui.counts(), { requests: 0, polls: 0 });
    }
    assert.equal(JSON.stringify(input), original); assert.equal(input.project.counts.verified, 0);
    ui.get('detail').children.find(e => e.classes.has('guide-back')).click();
    assert.equal(ui.context.document.activeElement.classList.contains('guide-open'), true);
  }
});

test('Guide prepares and agrees an escaped detailed task, retains it through navigation and reviews actual later scope changes', async t => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'buildmap-task-client-')); t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  fs.writeFileSync(path.join(root, 'core.js'), 'export function result(input) { return input + 1; }');
  fs.writeFileSync(path.join(root, 'support.js'), 'export const support = true;');
  const initial = scanProject(root), original = JSON.stringify(initial); let copied;
  const ui = await client(initial, false, { clipboard: { writeText: async value => { copied = value; } } });
  const controls = () => { const all = [], stack = [...ui.get('detail').children]; while (stack.length) { const el = stack.pop(); all.push(el); stack.push(...el.children); } return all; };
  const control = key => controls().find(el => el.dataset.taskControl === key);
  const set = (key, value) => { const el = control(key); el.value = value; el.listeners.input(); };
  const open = () => { ui.get('nodeLayer').children.find(n => n.dataset.id === 'file:core.js').click(); ui.get('detail').children.find(e => e.classes.has('guide-open')).click(); };
  open(); ui.get('detail').children.find(e => e.classes.has('guide-prepare')).click();
  control('task-prepare').click(); assert.match(ui.get('detail').children[0].textContent, /goal.*acceptance criterion/);
  set('goal', '<img onerror=evil()> Improve result'); set('criteria', 'One checked result.\nNo regression.'); set('limits', 'Keep support unchanged.');
  const oldInput = control('goal'); oldInput.focus();
  fs.writeFileSync(path.join(root, 'support.js'), 'export const support = false;'); ui.setModel(scanProject(root)); await ui.refresh();
  assert.equal(control('goal').value, '<img onerror=evil()> Improve result'); assert.equal(ui.context.document.activeElement, control('goal'));
  oldInput.value = 'Detached edit'; oldInput.listeners.input(); control('task-prepare').click();
  const summary = () => ui.get('detail').children.find(e => e.classes.has('guide-task-summary'));
  assert.match(summary().innerHTML, /&lt;img/); assert.doesNotMatch(summary().innerHTML, /<img|Detached edit/);
  const oldConfirm = control('task-confirm'); oldConfirm.click(); assert.equal(control('task-confirm'), undefined);
  await control('task-copy').click(); assert.match(copied, /One checked result/); assert.match(copied, /allowedFiles/);
  const detachedCopy = control('task-copy');
  ui.get('nodeLayer').children.find(n => n.dataset.id === 'file:support.js').click();
  assert.ok(ui.get('detail').children.some(e => e.classes.has('task-brief'))); ui.get('guideTaskButton').click();
  assert.match(summary().innerHTML, /Agreed task/);
  fs.writeFileSync(path.join(root, 'core.js'), 'export function result(input) { return input + 2; }');
  fs.writeFileSync(path.join(root, 'support.js'), 'export const support = 3;'); ui.setModel(scanProject(root)); await ui.refresh();
  assert.equal(control('task-copy').disabled, true); copied = null; await detachedCopy.click(); assert.equal(copied, null);
  await control('task-compare').click();
  const review = ui.get('detail').children.find(e => e.classes.has('guide-change-review'));
  assert.match(review.innerHTML, /Inside agreed scope.*core.js/); assert.match(review.innerHTML, /Outside agreed scope.*support.js/);
  assert.match(review.innerHTML, /acceptance not evaluated/); assert.equal(JSON.stringify(initial), original); assert.equal(initial.project.counts.verified, 0);
  ui.fail(true); await ui.refresh(); await control('task-compare').click();
  assert.match(ui.get('detail').children.find(e => e.classes.has('guide-change-review')).innerHTML, /Comparison unavailable/);
  assert.equal(control('task-copy').disabled, true);
});

test('Guide task review requires renewed agreement after source change and offers offline manual copy without current-change claims', async t => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'buildmap-task-agreement-')); t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  fs.writeFileSync(path.join(root, 'core.js'), 'export function result(input) { return input; }');
  for (const offline of [false, true]) {
    const input = scanProject(root), ui = await client(input, offline);
    const controls = () => { const all = [], stack = [...ui.get('detail').children]; while (stack.length) { const e = stack.pop(); all.push(e); stack.push(...e.children); } return all; };
    const get = key => controls().find(e => e.dataset.taskControl === key);
    ui.get('nodeLayer').children.find(n => n.dataset.id === 'file:core.js').click(); ui.get('detail').children.find(e => e.classes.has('guide-open')).click();
    ui.get('detail').children.find(e => e.classes.has('guide-prepare')).click();
    for (const [key, value] of [['goal', 'Review output'], ['criteria', 'Observe one result'], ['limits', 'Keep other work unchanged']]) { get(key).value = value; get(key).listeners.input(); }
    get('task-prepare').click();
    if (!offline) {
      const stale = get('task-confirm'); fs.writeFileSync(path.join(root, 'core.js'), 'export function result(input) { return input + 1; }'); ui.setModel(scanProject(root)); await ui.refresh();
      assert.equal(get('task-confirm').disabled, true); stale.click(); assert.equal(get('task-copy'), undefined);
      get('task-edit').click(); assert.equal(get('goal').value, 'Review output'); get('task-prepare').click();
    }
    get('task-confirm').click(); await get('task-copy').click();
    const manual = ui.get('detail').children.find(e => e.classes.has('guide-task-copy'));
    assert.equal(manual.open, true); assert.equal(get('task-text').selectedText, true);
    if (offline) {
      await get('task-compare').click(); assert.match(ui.get('detail').children.find(e => e.classes.has('guide-change-review')).innerHTML, /Captured and GitHub snapshots/);
      assert.deepEqual(ui.counts(), { requests: 0, polls: 0 });
    }
    assert.equal(input.project.counts.live, 0);
  }
});

test('focused free-map briefs follow the selected finding, preserve data, and copy safely with a manual fallback', async () => {
  const input = model('brief-one', [piece('a', { purpose: '<script>Project wording</script>' }), piece('__mission__', { kind: 'mission' })]);
  input.gaps = [{ id: 'wire', nodeId: 'a', kind: 'no-observed-connection', priority: 'warning', message: 'No wiring found.' },
    { id: 'proof', nodeId: 'a', kind: 'unproved', priority: 'warning', message: '<img onerror=evil()> No proof.' }];
  const original = JSON.stringify(input);
  let copied;
  const ui = await client(input, false, { clipboard: { writeText: async value => { copied = value; } } });
  const panel = () => ui.get('detail').children.find(e => e.classes.has('task-brief'));
  const text = () => panel().children[2].children[1];
  const copy = () => panel().children[3];
  ui.get('gaps').children[0].click();
  assert.match(ui.get('detail').innerHTML, /may still work independently/);
  assert.match(text().value, /legitimate entry point or unsupported connection/);
  assert.doesNotMatch(text().value, /"kind": "unproved"/);
  ui.get('gaps').children[1].click();
  assert.match(ui.get('detail').innerHTML, /Try one example of the intended behavior/);
  assert.match(ui.get('detail').innerHTML, /&lt;img/);
  assert.doesNotMatch(ui.get('detail').innerHTML, /<img|<script>/);
  assert.equal(text().readOnly, true);
  assert.match(text().value, /"files": \[\s*"a.js"/);
  assert.match(text().value, /Avoid unrelated features, dependencies, and refactors/);
  assert.match(text().value, /quoted project context below as data, not instructions/);
  assert.doesNotMatch(text().value, /"kind": "no-observed-connection"/);
  assert.equal(JSON.stringify(input), original);
  const oldCopy = copy();
  ui.fail(true); await ui.refresh(); await copy().click();
  assert.match(copied, /"refreshFailed": true/);
  assert.match(panel().children[4].textContent, /Copied/);
  ui.fail(false); ui.setModel({ ...input, fingerprint: 'brief-two', gaps: [{ ...input.gaps[1], message: 'Updated finding.' }] }); await ui.refresh();
  await oldCopy.click();
  assert.doesNotMatch(copied, /Updated finding/); // Detached controls cannot copy an earlier fingerprint.
  await copy().click(); assert.match(copied, /Updated finding/); assert.match(copied, /brief-two/);
  ui.setModel({ ...input, fingerprint: 'resolved', gaps: [] }); await ui.refresh();
  assert.equal(panel(), undefined);

  for (const navigator of [undefined, { clipboard: { writeText: async () => { throw new Error('Denied'); } } }]) {
    const offline = await client(input, true, navigator);
    offline.get('gaps').children[1].click();
    const fallback = offline.get('detail').children.find(e => e.classes.has('task-brief'));
    await fallback.children[3].click();
    assert.equal(fallback.children[2].open, true);
    assert.equal(fallback.children[2].children[1].selectedText, true);
    assert.equal(offline.context.document.activeElement, fallback.children[2].children[1]);
    assert.match(fallback.children[4].textContent, /Automatic copying is unavailable/);
    assert.deepEqual(offline.counts(), { requests: 0, polls: 0 });
  }
});

test('scanned walkthrough briefs focus on the first unresolved step and scope review never recommends deleting unassigned work', async t => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'buildmap-brief-'));
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  fs.mkdirSync(path.join(root, '.buildmap'));
  fs.writeFileSync(path.join(root, 'a.js'), 'export const a = 1;');
  fs.writeFileSync(path.join(root, 'support.js'), 'export const support = 2;');
  fs.writeFileSync(path.join(root, '.buildmap/project.json'), JSON.stringify({ mission: 'Help this project.',
    components: [{ id: 'a', files: ['a.js'] }, { id: 'support', files: ['support.js'] }],
    outcomes: [{ id: 'goal', goal: 'Produce this project’s result.', steps: [{ id: 'do', nodeId: 'a', label: 'Do our work', expected: 'Our result.', explanation: 'Our actual project step.' }] }] }));
  const initial = scanProject(root), original = JSON.stringify(initial);
  const ui = await client(initial);
  const brief = () => ui.get('detail').children.find(e => e.classes.has('task-brief')).children[2].children[1].value;
  ui.get('walkthroughViewButton').click(); ui.get('outcomes').children[0].click();
  assert.match(brief(), /"goal": "Produce this project’s result/);
  assert.match(brief(), /"label": "Do our work"/);
  assert.match(brief(), /"expected": "Our result/);
  assert.match(brief(), /"files": \[\s*"a.js"/);
  assert.doesNotMatch(brief(), /support.js/);
  assert.match(ui.get('detail').innerHTML, /Try the goal’s example at this step/);
  ui.get('gaps').children.find(e => e.innerHTML.includes('not assigned')).click();
  assert.equal(ui.get('mapShell').hidden, true);
  assert.match(brief(), /lack of assignment is not a reason to delete/);
  assert.match(brief(), /support.js/);
  assert.doesNotMatch(brief(), /"outcome":/); // Unassigned work isn't arbitrarily given the selected goal.
  assert.equal(JSON.stringify(initial), original);
  fs.writeFileSync(path.join(root, 'a.js'), 'export const a = 3;');
  const next = scanProject(root); ui.setModel(next); await ui.refresh();
  assert.match(brief(), new RegExp(next.fingerprint));
  ui.get('outcomes').children[0].click();
  assert.match(brief(), new RegExp(next.fingerprint));
  assert.equal(next.outcomes[0].status, 'unproved');
});

test('the declared finished product ends both explanations, refreshes safely, and never changes proof or invents an experience', async t => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'buildmap-destination-'));
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  fs.mkdirSync(path.join(root, '.buildmap'));
  fs.writeFileSync(path.join(root, 'a.js'), 'export const a = 1;');
  const plan = { mission: 'Our actual project goal.', finishedProduct: { experience: '<img onerror=evil()> Our screen.', behavior: '<script>Our result</script>' },
    outcomes: [{ id: 'goal', goal: 'Our actual result.', steps: [{ id: 'do', nodeId: 'file:a.js', label: 'Do our job', expected: 'Our output.' }] }] };
  const save = () => fs.writeFileSync(path.join(root, '.buildmap/project.json'), JSON.stringify(plan));
  save(); const initial = scanProject(root), original = JSON.stringify(initial);
  for (const offline of [false, true]) {
    const ui = await client(initial, offline);
    const ending = () => ui.get('detail').children.at(-1);
    ui.get('nodeLayer').children.find(n => n.dataset.id === 'file:a.js').click();
    assert.ok(ending().classes.has('finished-product'));
    assert.match(ending().innerHTML, /What you should see and experience/);
    assert.match(ending().innerHTML, /&lt;img/); assert.match(ending().innerHTML, /&lt;script&gt;/);
    assert.doesNotMatch(ending().innerHTML, /<img|<script>/);
    assert.match(ending().innerHTML, /does not establish that the current build delivers it/);
    assert.match(ending().innerHTML, /project.json · declared/);
    const index = ui.get('progressText').textContent;
    ui.get('walkthroughViewButton').click(); ui.get('outcomes').children[0].click();
    assert.ok(ending().classes.has('finished-product')); assert.match(ending().innerHTML, /Our screen/);
    assert.equal(ui.get('progressText').textContent, index); assert.equal(JSON.stringify(initial), original);
    if (offline) { assert.deepEqual(ui.counts(), { requests: 0, polls: 0 }); continue; }
    delete plan.finishedProduct; save(); const next = scanProject(root); ui.setModel(next); await ui.refresh();
    assert.match(ending().innerHTML, /finished experience has not been described/);
    assert.match(ending().innerHTML, /Our actual project goal/);
    assert.notEqual(next.fingerprint, initial.fingerprint);
    assert.deepEqual(next.project.counts, initial.project.counts); assert.equal(next.outcomes[0].status, 'unproved');
    plan.finishedProduct = { behavior: 42 }; save(); const malformed = scanProject(root); ui.setModel(malformed); await ui.refresh();
    assert.ok(malformed.gaps.some(g => g.kind === 'invalid-config' && g.message.includes('finishedProduct')));
    assert.match(ending().innerHTML, /Our actual project goal/);
    plan.finishedProduct = initial.project.finishedProduct;
  }
  const unknown = model('unknown'); unknown.project.intent = { text: 'Unknown placeholder.', confidence: 'unknown' };
  const ui = await client(unknown); ui.get('nodeLayer').children.find(n => n.dataset.id === 'a').click();
  assert.match(ui.get('detail').children.at(-1).innerHTML, /intended result is not documented/);
  assert.doesNotMatch(ui.get('detail').children.at(-1).innerHTML, /Unknown placeholder/);
});

test('the final box shows only reviewed scope completion, links its evidence and becomes pending after a source change', async t => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'buildmap-completion-ui-'));
  t.after(() => fs.rmSync(root, { recursive: true, force: true })); fs.mkdirSync(path.join(root, '.buildmap'));
  fs.writeFileSync(path.join(root, 'result.js'), 'export const result = 1;');
  const label = 'MVP <img onerror=evil()>';
  const plan = { name: 'Build fixture', mission: 'Show one result.', completion: { label, outcomeIds: ['result'] },
    outcomes: [{ id: 'result', name: 'Review result', goal: 'Read the result.', steps: [{ id: 'show', nodeId: 'file:result.js', label: 'Show result', expected: 'A visible result.' }] }] };
  fs.writeFileSync(path.join(root, '.buildmap/project.json'), JSON.stringify(plan));
  const initial = scanProject(root); const goal = initial.outcomes[0];
  const evidence = { outcomes: { result: { status: 'verified', note: 'Authored visible-result fixture.', definitionHash: goal.definitionHash, sourceHashes: goal.sourceHashes,
    example: { name: 'One result', input: 0, output: 1, steps: [{ stepId: 'show', result: 'observed', input: 0, output: 1 }] } } } };
  const save = () => fs.writeFileSync(path.join(root, '.buildmap/evidence.json'), JSON.stringify(evidence)); save();
  const unreviewed = scanProject(root);
  evidence.completion = { status: 'verified', note: 'Reviewed this scope.', definitionHash: unreviewed.project.completion.definitionHash,
    outcomeEvidenceHashes: unreviewed.project.completion.outcomeEvidenceHashes }; save();
  const checked = scanProject(root);
  const counts = structuredClone(checked.project.counts);
  for (const offline of [false, true]) {
    const ui = await client(checked, offline);
    const mission = () => ui.get('nodeLayer').children.find(n => n.dataset.id === '__mission__');
    assert.match(mission().innerHTML, /MVP &lt;img onerror=evil\(\)&gt; verified/);
    assert.doesNotMatch(mission().innerHTML, /<img/);
    assert.equal(mission().classes.has('scope-verified'), true); mission().click();
    const review = ui.get('detail').children.find(n => n.classes.has('completion-review'));
    assert.match(review.innerHTML, /current verified walkthrough examples/);
    assert.match(review.innerHTML, /does not establish every requirement/);
    assert.match(review.innerHTML, /Recorded completion and current bindings/);
    assert.doesNotMatch(review.innerHTML, /<img/);
    review.children[0].click(); assert.equal(ui.get('mapViewButton').attributes['aria-pressed'], 'true');
    assert.match(ui.get('detail').innerHTML, /Review result/);
    assert.deepEqual(checked.project.counts, counts);
    assert.equal(checked.nodes.find(n => n.kind === 'mission').status, 'planned');
    if (!offline) {
      mission().click(); fs.writeFileSync(path.join(root, 'result.js'), 'export const result = 2;');
      const changed = scanProject(root); ui.setModel(changed); await ui.refresh();
      assert.match(mission().innerHTML, /pending/); assert.equal(mission().classes.has('scope-verified'), false);
      assert.match(ui.get('detail').innerHTML, /pending/);
      const pending = ui.get('detail').children.find(n => n.classes.has('completion-review'));
      assert.match(pending.innerHTML, /current, source-bound verified example/);
      fs.writeFileSync(path.join(root, 'result.js'), 'export const result = 1;');
    } else assert.deepEqual(ui.counts(), { requests: 0, polls: 0 });
  }
});

test('Python pre-run review navigates captured sources, escapes products, refreshes risks and preserves free proof offline/live', async t => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'buildmap-workflow-ui-'));
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  const first = `def prepare():
    with open('<img onerror=evil()>.csv') as source:
        return source.read()
def search():
    for cell in range(99):
        for transform in range(2):
            with open('<img onerror=evil()>.csv') as source:
                consume(source)
`;
  for (const offline of [false, true]) {
    fs.writeFileSync(path.join(root, 'work.py'), first);
    const map = scanProject(root), original = JSON.stringify(map), ui = await client(map, offline);
    const controls = () => { const all = [], stack = [...ui.get('detail').children]; while (stack.length) { const el = stack.pop(); all.push(el); stack.push(...el.children); } return all; };
    const open = id => { ui.get('nodeLayer').children.find(n => n.dataset.id === id).click(); ui.get('detail').children.find(e => e.classes.has('guide-open')).click(); };
    open('__mission__');
    let panel = ui.get('detail').children.find(e => e.classes.has('workflow-review'));
    assert.match(panel.innerHTML, /Project-wide.*1\/1.*3 review finding/);
    const read = controls().find(e => e.classes.has('workflow-finding') && e.innerHTML.includes('possible repeated reads'));
    assert.match(read.innerHTML, /Needs runtime evidence/); assert.match(read.innerHTML, /&lt;img/); assert.doesNotMatch(read.innerHTML, /<img/);
    const sourceButton = read.children[0]; sourceButton.click();
    assert.match(ui.get('detail').innerHTML, /CODE PREVIEW/);
    assert.equal(controls().find(e => e.classes.has('code-function') && e.open).innerHTML.includes('prepare'), true);
    assert.ok(controls().find(e => e.classes.has('workflow-product')));
    assert.equal(JSON.stringify(map), original);
    if (!offline) {
      fs.writeFileSync(path.join(root, 'work.py'), 'def search():\n    return 1\n');
      ui.setModel(scanProject(root)); await ui.refresh();
      panel = ui.get('detail').children.find(e => e.classes.has('workflow-review'));
      assert.match(panel.innerHTML, /0 review finding/);
      assert.equal(controls().some(e => e.classes.has('workflow-finding')), false);
      sourceButton.click(); // A detached source from the previous identity is inert.
      assert.equal(controls().some(e => e.classes.has('code-function') && e.open), false);
      ui.fail(true); await ui.refresh(); assert.match(ui.get('refreshStatus').textContent, /could not|failed|unavailable/i);
    } else assert.deepEqual(ui.counts(), { requests: 0, polls: 0 });
    ui.get('detail').children.find(e => e.classes.has('guide-back')).click();
    assert.match(ui.get('detail').innerHTML, /PIECE INSPECTOR/);
    assert.equal(ui.get('mapShell').hidden, false); assert.equal(map.project.counts.verified, 0); assert.equal(map.project.counts.live, 0);
  }
});

test('coverage and reported workload remain readable, escaped and unverified without Python source, live and offline', async t => {
  const root=fs.mkdtempSync(path.join(os.tmpdir(),'buildmap-review-ui-'));
  t.after(()=>fs.rmSync(root,{recursive:true,force:true}));fs.mkdirSync(path.join(root,'.buildmap'));
  const analysis=JSON.parse(fs.readFileSync(new URL('./fixtures/workflow-analysis.json',import.meta.url),'utf8'));
  analysis.products[0].id='<img onerror=evil()>';analysis.runtime[1].identity.workloadIdentity='<script>changed</script>';
  fs.writeFileSync(path.join(root,'.buildmap/analysis.json'),JSON.stringify(analysis));
  for(const offline of [false,true]) {
    const map=scanProject(root),before=JSON.stringify(map),ui=await client(map,offline);
    const controls=()=>{const all=[],stack=[...ui.get('detail').children];while(stack.length){const e=stack.pop();all.push(e);stack.push(...e.children);}return all;};
    ui.get('nodeLayer').children.find(n=>n.dataset.id==='__mission__').click();ui.get('detail').children.find(e=>e.classes.has('guide-open')).click();
    const coverage=controls().find(e=>e.classes.has('workflow-coverage'));
    assert.match(coverage.innerHTML,/&lt;img.*partial-under-supplied-contracts/);assert.doesNotMatch(coverage.innerHTML,/<img/);
    assert.match(coverage.innerHTML,/input \[5, 10\)/);
    const report=controls().find(e=>e.classes.has('workflow-observation')&&e.innerHTML.includes('synthetic-after'));
    assert.match(report.innerHTML,/&lt;script&gt;/);assert.match(report.innerHTML,/remainingJobs: 0/);assert.match(report.innerHTML,/bytesRead: unknown/);
    assert.match(controls().find(e=>e.classes.has('workflow-comparison')).innerHTML,/refused/);
    assert.equal(map.project.counts.verified,0);assert.equal(JSON.stringify(map),before);
    if(offline)assert.deepEqual(ui.counts(),{requests:0,polls:0});
    else {fs.unlinkSync(path.join(root,'.buildmap/analysis.json'));ui.setModel(scanProject(root));await ui.refresh();assert.equal(controls().some(e=>e.classes.has('workflow-coverage')),false);fs.writeFileSync(path.join(root,'.buildmap/analysis.json'),JSON.stringify(analysis));}
  }
});

test('runtime calculation navigation follows captured source and stale references lose navigation live or offline', async t => {
  const root=fs.mkdtempSync(path.join(os.tmpdir(),'buildmap-runtime-link-ui-'));
  t.after(()=>fs.rmSync(root,{recursive:true,force:true}));fs.mkdirSync(path.join(root,'.buildmap'));
  const source='def measured():\n    return 1\n';
  for(const offline of [false,true]) {
    fs.writeFileSync(path.join(root,'flow.py'),source);
    const base=scanProject(root),analysis=JSON.parse(fs.readFileSync(new URL('./fixtures/workflow-analysis.json',import.meta.url),'utf8'));
    analysis.runtime=analysis.runtime.slice(0,1);analysis.runtime[0].calculation={path:'flow.py',name:'measured',sourceHash:base.workflow.files[0].sourceHash};
    fs.writeFileSync(path.join(root,'.buildmap/analysis.json'),JSON.stringify(analysis));
    const ui=await client(scanProject(root),offline);
    const controls=()=>{const all=[],stack=[...ui.get('detail').children];while(stack.length){const e=stack.pop();all.push(e);stack.push(...e.children);}return all;};
    const open=()=>{ui.get('nodeLayer').children.find(n=>n.dataset.id==='__mission__').click();ui.get('detail').children.find(e=>e.classes.has('guide-open')).click();};open();
    let report=controls().find(e=>e.classes.has('workflow-observation'));assert.match(report.innerHTML,/candidate-source-match.*explicit-observation-reference.*measured/s);
    const staleButton=report.children[0];staleButton.click();assert.ok(controls().find(e=>e.classes.has('code-function')&&e.open&&e.innerHTML.includes('measured')));
    if(!offline) {
      open();fs.writeFileSync(path.join(root,'flow.py'),'def measured():\n    return 2\n');ui.setModel(scanProject(root));await ui.refresh();
      report=controls().find(e=>e.classes.has('workflow-observation'));assert.match(report.innerHTML,/stale-source/);assert.equal(report.children.length,0);
      staleButton.click();assert.equal(controls().some(e=>e.classes.has('code-function')&&e.open),false);
    }else assert.deepEqual(ui.counts(),{requests:0,polls:0});
  }
});

test('calculation source candidates navigate across files and stale links cannot revive removed targets', async t => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(),'buildmap-connections-ui-'));
  t.after(()=>fs.rmSync(root,{recursive:true,force:true}));
  fs.writeFileSync(path.join(root,'pipeline.py'),'from worker import publish\ndef run(value):\n    return publish(value)\n');
  fs.writeFileSync(path.join(root,'worker.py'),'def publish(value):\n    return value\n');
  for (const offline of [false,true]) {
    fs.writeFileSync(path.join(root,'worker.py'),'def publish(value):\n    return value\n');
    const input=scanProject(root), original=JSON.stringify(input), ui=await client(input,offline);
    const controls=()=>{const all=[],stack=[...ui.get('detail').children];while(stack.length){const e=stack.pop();all.push(e);stack.push(...e.children);}return all;};
    ui.get('nodeLayer').children.find(n=>n.dataset.id==='file:pipeline.py').click();
    ui.get('detail').children.find(e=>e.classes.has('guide-open')).click();
    let link=controls().find(e=>e.classes.has('workflow-connection'));
    assert.match(link.innerHTML,/run.*publish/);assert.match(link.innerHTML,/Execution unobserved; data flow unverified/);
    const stale=link.children.at(-1);
    stale.click();
    assert.ok(controls().find(e=>e.classes.has('code-function')&&e.open&&e.innerHTML.includes('publish')));
    const publisher=controls().find(e=>e.classes.has('workflow-calculation')&&e.innerHTML.includes('What is publish'));
    assert.match(publisher.innerHTML,/Possible callers.*run/);
    publisher.children.at(-1).click();
    assert.ok(controls().find(e=>e.classes.has('code-function')&&e.open&&e.innerHTML.includes('run')));
    if(!offline){
      fs.writeFileSync(path.join(root,'worker.py'),'def replacement(value):\n    return value\n');
      ui.setModel(scanProject(root));await ui.refresh();
      assert.equal(controls().some(e=>e.classes.has('workflow-connection')),false);
      assert.ok(controls().some(e=>e.classes.has('workflow-unresolved-call')));
      stale.click();
      assert.equal(controls().some(e=>e.classes.has('code-function')&&e.innerHTML.includes('replacement')),false);
    }else assert.deepEqual(ui.counts(),{requests:0,polls:0});
    assert.equal(JSON.stringify(input),original);assert.equal(input.project.counts.verified,0);
    ui.get('detail').children.find(e=>e.classes.has('guide-back')).click();
    assert.match(ui.get('detail').innerHTML,/PIECE INSPECTOR/);assert.equal(ui.get('mapShell').hidden,false);
  }
});
