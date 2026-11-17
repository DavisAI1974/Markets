import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import crypto from 'node:crypto';
import { pathToFileURL } from 'node:url';
import { scanProject } from '../src/scan.js';
import { snapshotHtml } from '../src/export.js';

function fixture(t) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'buildmap-outcome-'));
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  fs.mkdirSync(path.join(root, '.buildmap'));
  const write = (file, value) => fs.writeFileSync(path.join(root, file), typeof value === 'string' ? value : JSON.stringify(value));
  write('price.js', 'export function price(input) { return { total: input.quantity * input.unitPrice }; }');
  write('confirm.js', 'export function confirm(input) { return { message: `Order total: ${input.total}` }; }');
  write('support.js', 'export const check = true;');
  const plan = { id: 'order', name: 'Confirm an order', goal: 'Calculate an order total and show its confirmation.',
    supports: ['checks'], steps: [
      { id: 'price', nodeId: 'price', label: 'Calculate total', expected: 'The quantity multiplied by unit price.' },
      { id: 'confirm', nodeId: 'confirm', label: 'Show confirmation', expected: 'A confirmation containing the total.' }
    ] };
  const manifest = { mission: 'Handle orders.', components: [
    { id: 'price', files: ['price.js'] }, { id: 'confirm', files: ['confirm.js'] }, { id: 'checks', files: ['support.js'] }
  ], outcomes: [plan] };
  const save = () => write('.buildmap/project.json', manifest);
  save();
  const record = receipt => write('.buildmap/evidence.json', { outcomes: { order: receipt } });
  return { root, write, plan, manifest, save, record };
}
function receipt(map) {
  const outcome = map.outcomes[0];
  return { status: 'verified', command: 'Recorded order example check.', definitionHash: outcome.definitionHash, sourceHashes: outcome.sourceHashes,
    example: { name: 'Two items at three each', input: { quantity: 2, unitPrice: 3 }, output: { message: 'Order total: 6' }, steps: [
      { stepId: 'price', result: 'observed', input: { quantity: 2, unitPrice: 3 }, output: { total: 6 } },
      { stepId: 'confirm', result: 'observed', handoff: 'The calculated total was supplied to confirmation.', input: { total: 6 }, output: { message: 'Order total: 6' } }
    ] } };
}

test('outcome plans preserve piece proof states and source edges, while exposing missing steps and scope review', t => {
  const f = fixture(t);
  f.write('extra.js', 'export const extra = true;');
  f.plan.steps.push({ id: 'send', nodeId: 'sender', label: 'Send confirmation', expected: 'Customer receives it.' }); f.save();
  const map = scanProject(f.root);
  assert.equal(map.outcomes[0].status, 'unproved');
  assert.equal(map.outcomes[0].steps[2].state, 'missing-piece');
  assert.equal(map.outcomes[0].firstGap.id, 'price'); // Existing pieces still have no journey observation.
  assert.equal(map.edges.filter(e => e.type !== 'contributes').length, 0);
  assert.equal(map.project.counts.coded, 4);
  assert.deepEqual(map.nodes.find(n => n.id === 'checks').outcomeIds, ['order']);
  assert.ok(map.gaps.some(g => g.kind === 'unknown-outcome-piece' && g.outcomeId === 'order'));
  assert.ok(map.gaps.some(g => g.kind === 'unassigned-outcome' && g.nodeId === 'file:extra.js'));
  assert.equal(map.nodes.find(n => n.kind === 'mission').status, 'planned');
});

test('an executed example can verify its outcome without promoting participating pieces or the mission', async t => {
  const f = fixture(t);
  const map = scanProject(f.root);
  const input = { quantity: 2, unitPrice: 3 };
  // Execute only these authored fixture modules; scanning never runs target code.
  const { price } = await import(pathToFileURL(path.join(f.root, 'price.js')));
  const { confirm } = await import(pathToFileURL(path.join(f.root, 'confirm.js')));
  const priced = price(input); const confirmed = confirm(priced);
  assert.deepEqual(priced, { total: 6 }); assert.deepEqual(confirmed, { message: 'Order total: 6' });
  const proof = receipt(map);
  proof.example.input = input; proof.example.output = confirmed;
  proof.example.steps[0].input = input; proof.example.steps[0].output = priced;
  proof.example.steps[1].input = priced; proof.example.steps[1].output = confirmed;
  f.record(proof);
  const observed = scanProject(f.root);
  assert.equal(observed.outcomes[0].status, 'verified');
  assert.equal(observed.outcomes[0].firstGap, null);
  assert.deepEqual(Object.keys(observed.outcomes[0].sourceHashes).sort(), ['confirm.js', 'price.js', 'support.js']);
  assert.equal(observed.project.counts.verified, 0);
  assert.equal(observed.project.counts.coded, 3);
  assert.equal(observed.nodes.find(n => n.kind === 'mission').status, 'planned');
});

test('outcome examples stale on participating/support source, plan, and explicitly bound input changes', t => {
  const f = fixture(t);
  const before = scanProject(f.root); const proof = receipt(before);
  f.record(proof);
  assert.equal(scanProject(f.root).outcomes[0].status, 'verified');
  f.write('support.js', 'export const check = false;');
  const sourceChanged = scanProject(f.root);
  assert.equal(sourceChanged.outcomes[0].steps[0].state, 'stale-example');
  assert.equal(sourceChanged.outcomes[0].status, 'unproved');
  assert.notEqual(sourceChanged.fingerprint, before.fingerprint);
  f.write('support.js', 'export const check = true;');
  f.plan.steps[1].expected = 'A receipt with the total and customer name.'; f.save();
  assert.match(scanProject(f.root).outcomes[0].evidenceAssessment.reason, /definition.*changed/);
  f.plan.steps[1].expected = 'A confirmation containing the total.'; f.save();
  f.plan.steps[1].explanation = 'Explain the confirmation in everyday words.';
  f.plan.steps[1].example = 'This order shows the total to the customer.'; f.save();
  const explained = scanProject(f.root);
  assert.equal(explained.outcomes[0].steps[1].explanation, f.plan.steps[1].explanation);
  assert.equal(explained.outcomes[0].steps[1].example, f.plan.steps[1].example);
  assert.match(explained.outcomes[0].evidenceAssessment.reason, /definition.*changed/);
  delete f.plan.steps[1].explanation; delete f.plan.steps[1].example; f.save();
  f.write('input.json', '{"quantity":2}');
  proof.inputHashes = { 'input.json': crypto.createHash('sha256').update('{"quantity":2}').digest('hex') }; f.record(proof);
  const current = scanProject(f.root); assert.equal(current.outcomes[0].status, 'verified');
  f.write('input.json', '{"quantity":3}');
  const stale = scanProject(f.root); assert.equal(stale.outcomes[0].status, 'unproved');
  assert.notEqual(stale.fingerprint, current.fingerprint);
  assert.match(stale.outcomes[0].evidenceAssessment.reason, /input.json/);
});

test('partial, failed, missing-handoff, malformed and unsupported claims cannot prove an outcome', t => {
  const f = fixture(t); const map = scanProject(f.root);
  const cases = [
    p => { p.example.steps.pop(); },
    p => { p.example.steps[1].result = 'failed'; },
    p => { delete p.example.steps[1].handoff; },
    p => { p.example.steps.reverse(); },
    p => { p.example.steps.push(p.example.steps[0]); },
    p => { p.example.steps[1].stepId = 'unknown'; },
    p => { p.example.output = { message: 'A different result.' }; },
    p => { delete p.example.steps[0].input; },
    p => { delete p.sourceHashes; },
    p => { p.sourceHashes = { 'price.js': p.sourceHashes['price.js'] }; },
    p => { delete p.command; },
    p => { p.status = 'live'; }
  ];
  for (const change of cases) {
    const proof = receipt(map); change(proof); f.record(proof);
    const result = scanProject(f.root); assert.equal(result.outcomes[0].status, 'unproved');
    assert.equal(result.project.counts.verified, 0);
    assert.ok(result.gaps.some(g => g.kind === 'unproved-outcome' && g.outcomeId === 'order'));
  }
  const partial = receipt(map); partial.example.steps.pop(); f.record(partial);
  assert.equal(scanProject(f.root).outcomes[0].steps[0].state, 'observed');
  assert.equal(scanProject(f.root).outcomes[0].firstGap.id, 'confirm');
  fs.unlinkSync(path.join(f.root, 'price.js')); f.record(receipt(map));
  assert.equal(scanProject(f.root).outcomes[0].steps[0].state, 'missing-implementation');
});

test('invalid plans, falsy/orphan receipts and ownership conflicts stay visible without granting outcome proof', t => {
  const f = fixture(t);
  for (const value of [false, {}, [{ id: 'bad', goal: 'Goal', steps: [{ id: 's', nodeId: 'price' }] }],
    [{ ...f.plan, steps: [{ ...f.plan.steps[0], example: { invalid: true } }] }], [f.plan, f.plan]]) {
    f.manifest.outcomes = value; f.save();
    assert.ok(scanProject(f.root).gaps.some(g => g.kind === 'invalid-outcome'));
  }
  f.manifest.outcomes = [f.plan]; f.save();
  for (const value of [false, 0, '', null, []]) {
    f.record(value); const map = scanProject(f.root);
    assert.equal(map.outcomes[0].status, 'unproved');
    assert.ok(map.gaps.some(g => Object.hasOwn(g, 'evidence')));
  }
  f.write('.buildmap/evidence.json', { outcomes: { ghost: { status: 'verified', note: 'Old claim.' } } });
  assert.ok(scanProject(f.root).gaps.some(g => g.kind === 'unmapped-outcome-evidence'));
  f.write('.buildmap/evidence.json', { outcomes: [] });
  assert.ok(scanProject(f.root).gaps.some(g => g.kind === 'invalid-outcome-evidence'));
  f.manifest.components.push({ id: 'overlap', files: ['price.js'] }); f.save();
  f.record(receipt(scanProject(f.root)));
  assert.equal(scanProject(f.root).outcomes[0].status, 'unproved');
});

test('walkthrough data safely round-trips in a standalone export', t => {
  const f = fixture(t); const proof = receipt(scanProject(f.root));
  proof.example.name = '</script><img onerror=evil()> $&'; f.record(proof);
  const map = scanProject(f.root); const html = snapshotHtml(map);
  assert.doesNotMatch(html, /<img onerror/);
  const data = html.match(/<script id="buildmapSnapshot" type="application\/json">([\s\S]*?)<\/script>/)[1];
  assert.deepEqual(JSON.parse(data).outcomes, map.outcomes);
});

function completionReceipt(map) {
  return { status: 'verified', note: 'Reviewed this declared scope against the named current example.',
    definitionHash: map.project.completion.definitionHash, outcomeEvidenceHashes: map.project.completion.outcomeEvidenceHashes };
}

test('explicit completion review binds the scope and exact verified examples without promoting mission or pieces', t => {
  const f = fixture(t);
  f.manifest.completion = { label: 'MVP', outcomeIds: ['order'] }; f.save();
  const proof = receipt(scanProject(f.root)); f.record(proof);
  const before = scanProject(f.root);
  assert.equal(before.outcomes[0].status, 'verified');
  assert.equal(before.project.completion.status, 'pending'); // A goal check alone is not a completion review.
  const review = completionReceipt(before);
  const save = () => f.write('.buildmap/evidence.json', { outcomes: { order: proof }, completion: review }); save();
  const current = scanProject(f.root);
  assert.equal(current.project.completion.status, 'verified');
  assert.equal(current.nodes.find(n => n.kind === 'mission').status, 'planned');
  assert.equal(current.project.counts.verified, 0); assert.equal(current.project.counts.live, 0);
  assert.deepEqual(current.edges, before.edges);
  const html = snapshotHtml(current);
  const captured = JSON.parse(html.match(/<script id="buildmapSnapshot" type="application\/json">([\s\S]*?)<\/script>/)[1]);
  assert.deepEqual(captured.project.completion, current.project.completion);
  proof.example.name = 'A different recorded example'; save();
  assert.equal(scanProject(f.root).outcomes[0].status, 'verified');
  assert.equal(scanProject(f.root).project.completion.status, 'pending'); // Review is bound to the actual record.
  proof.example.name = 'Two items at three each'; save();
  f.manifest.completion.label = 'A larger release'; f.save();
  assert.equal(scanProject(f.root).project.completion.status, 'pending');
  f.manifest.completion.label = 'MVP'; f.save();
  f.plan.steps[1].expected = 'A more detailed confirmation'; f.save();
  assert.equal(scanProject(f.root).project.completion.status, 'pending');
  f.plan.steps[1].expected = 'A confirmation containing the total.'; f.save();
  f.write('support.js', 'export const check = false;');
  assert.equal(scanProject(f.root).project.completion.status, 'pending');
  f.write('support.js', 'export const check = true;');
  f.write('input.json', '{"quantity":2}');
  proof.inputHashes = { 'input.json': crypto.createHash('sha256').update('{"quantity":2}').digest('hex') }; f.record(proof);
  const inputReview = completionReceipt(scanProject(f.root));
  f.write('.buildmap/evidence.json', { outcomes: { order: proof }, completion: inputReview });
  assert.equal(scanProject(f.root).project.completion.status, 'verified');
  f.write('input.json', '{"quantity":3}');
  assert.equal(scanProject(f.root).project.completion.status, 'pending');
});

test('piece verification, computing or incomplete examples, invalid scopes and unsupported completion claims stay pending', t => {
  const f = fixture(t); f.manifest.completion = { label: 'MVP', outcomeIds: ['order'] }; f.save();
  const map = scanProject(f.root);
  const components = Object.fromEntries(map.nodes.filter(n => n.kind !== 'mission').map(n => [n.id, { status: 'verified', note: 'Piece check.', sourceHashes: n.sourceHashes }]));
  f.write('.buildmap/evidence.json', { components });
  const pieces = scanProject(f.root); assert.equal(pieces.project.counts.verified, 3); assert.equal(pieces.project.completion.status, 'pending');
  const proof = receipt(pieces); f.record(proof); const review = completionReceipt(scanProject(f.root));
  for (const invalid of [{ ...review, status: 'live' }, { ...review, note: '' }, { ...review, outcomeEvidenceHashes: {} }]) {
    f.write('.buildmap/evidence.json', { outcomes: { order: proof }, completion: invalid });
    assert.equal(scanProject(f.root).project.completion.status, 'pending');
  }
  for (const change of [p => { p.status = 'computing'; }, p => { p.example.steps.pop(); }, p => { p.example.steps[1].result = 'failed'; }]) {
    const partial = receipt(map); change(partial); f.record(partial);
    f.write('.buildmap/evidence.json', { outcomes: { order: partial }, completion: completionReceipt(scanProject(f.root)) });
    assert.equal(scanProject(f.root).project.completion.status, 'pending');
  }
  for (const scope of [false, { label: 'MVP', outcomeIds: [] }, { label: 'MVP', outcomeIds: ['order', 'order'] }, { label: 'MVP', outcomeIds: ['missing'] }]) {
    f.manifest.completion = scope; f.save();
    assert.equal(scanProject(f.root).project.completion.status, 'pending');
  }
  delete f.manifest.completion; f.save();
  f.write('.buildmap/evidence.json', {}); assert.equal(scanProject(f.root).project.completion, null);
});
