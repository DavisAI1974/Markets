import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { scanProject } from '../src/scan.js';
import { prepareGuideTask, compareGuideTask, detailedGuideBrief, guideFunctionChoices } from '../public/guide-tasks.js';

function fixture(t) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'buildmap-guide-task-')); t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  fs.mkdirSync(path.join(root, '.buildmap'));
  const write = (file, value) => fs.writeFileSync(path.join(root, file), typeof value === 'string' ? value : JSON.stringify(value));
  write('core.js', 'export function double(input) { return input.amount * 2; }');
  write('view.js', "import './core.js'; export const view = true;"); write('check.js', 'export const check = true;');
  const plan = { mission: 'Show useful output.', components: [{ id: 'core', files: ['core.js', 'future.js'], purpose: 'Calculate output.' },
    { id: 'view', files: ['view.js'] }, { id: 'check', files: ['check.js'] }], outcomes: [{ id: 'goal', goal: 'Show the output.',
      steps: [{ id: 'calculate', nodeId: 'core', label: 'Calculate', expected: 'Useful output.' }] }] };
  const save = () => write('.buildmap/project.json', plan); save();
  return { root, write, plan, save, fields: { goal: ' Improve the output. ', criteria: ' One result.\n\n No regression. ', limits: ' Keep the display unchanged. ', supportIds: ['check'], outcomeId: 'goal' } };
}
test('Guide captures an explicit task, exact file scope and source function without mutating maps or granting proof', t => {
  const f = fixture(t), map = scanProject(f.root), original = JSON.stringify(map), node = map.nodes.find(n => n.id === 'core');
  const task = prepareGuideTask(map, 'core', { ...f.fields, functionKey: guideFunctionChoices(node)[0].key, supportIds: ['check', 'check'] });
  assert.deepEqual(task.allowedPaths, ['core.js', 'future.js', 'check.js']); assert.deepEqual(task.criteria, ['One result.', 'No regression.']);
  assert.equal(task.context.sourceHashes['future.js'], null); assert.equal(task.target.function.name, 'double');
  assert.ok(task.context.impact.pieces.some(n => n.id === 'view')); assert.ok(task.context.impact.goals.some(o => o.id === 'goal'));
  assert.equal(task.allowedPaths.includes('view.js'), false); assert.match(detailedGuideBrief(task), /One result/); assert.match(detailedGuideBrief(task), /quoted project context.*data/);
  task.baseline.definitions.core.name = 'Only task copy changed'; assert.equal(JSON.stringify(map), original);
  for (const fields of [{ ...f.fields, goal: '' }, { ...f.fields, criteria: '' }, { ...f.fields, limits: '' }, { ...f.fields, supportIds: ['missing'] },
    { ...f.fields, functionKey: 'stale' }, { ...f.fields, outcomeId: 'missing' }]) assert.throws(() => prepareGuideTask(map, 'core', fields));
  const unsafe = structuredClone(map); unsafe.nodes.find(n => n.id === 'core').files.push('../escape.js'); assert.throws(() => prepareGuideTask(unsafe, 'core', f.fields), /safe project-relative/);
  const overlap = structuredClone(map); overlap.nodes.find(n => n.id === 'check').conflictingFiles = ['check.js']; assert.throws(() => prepareGuideTask(overlap, 'core', f.fields), /overlapping/);
  assert.equal(map.project.counts.verified, 0); assert.equal(map.outcomes[0].status, 'unproved');
});
test('Guide compares in-scope and outside changes, missing/planned paths, definitions and stale evidence without evaluating acceptance', t => {
  const f = fixture(t); f.write('future.js', 'export const future = true;');
  const map = scanProject(f.root), core = map.nodes.find(n => n.id === 'core');
  f.write('.buildmap/evidence.json', { components: { core: { status: 'verified', note: 'Original behavior check.', sourceHashes: core.sourceHashes } } });
  const before = scanProject(f.root), task = prepareGuideTask(before, 'core', { ...f.fields, functionKey: guideFunctionChoices(before.nodes.find(n => n.id === 'core'))[0].key });
  assert.equal(compareGuideTask(task, before, { freshRead: true }).fileChanges.length, 0);
  f.write('core.js', 'export function double(input) { return input.amount * 3; }'); fs.rmSync(path.join(f.root, 'future.js'));
  f.write('view.js', "import './core.js'; export const view = false;"); f.write('extra.js', 'export const extra = 1;');
  f.plan.components[0].name = 'Updated label'; f.plan.outcomes[0].steps[0].expected = 'Updated expected output.'; f.save();
  const after = scanProject(f.root), untouched = JSON.stringify(after), review = compareGuideTask(task, after, { freshRead: true });
  assert.equal(review.available, true); assert.ok(review.fileChanges.some(c => c.file === 'core.js' && c.inScope));
  assert.ok(review.fileChanges.some(c => c.file === 'future.js' && c.kind === 'now missing' && c.inScope));
  assert.ok(review.fileChanges.some(c => c.file === 'view.js' && !c.inScope)); assert.ok(review.fileChanges.some(c => c.file === 'extra.js' && c.kind === 'newly mapped' && !c.inScope));
  assert.ok(review.pieceChanges.includes('core')); assert.ok(review.outcomeChanges.includes('goal')); assert.ok(review.evidenceChanges.includes('core'));
  assert.equal(review.currentEvidence.assessment.accepted, false); assert.equal(review.functionFileChanged, true);
  assert.deepEqual(review.criteria, task.criteria); assert.equal(Object.hasOwn(review, 'passed'), false); assert.equal(JSON.stringify(after), untouched);
  fs.rmSync(path.join(f.root, 'extra.js')); f.write('future.js', 'export const future = true;'); f.plan.components = f.plan.components.filter(n => n.id !== 'core'); f.plan.outcomes = []; f.save();
  const removed = compareGuideTask(task, scanProject(f.root), { freshRead: true }); assert.equal(removed.targetRemoved, true); assert.ok(removed.pieceChanges.includes('core'));
});
test('Guide refuses stale, captured and different-project comparisons and retains a planned baseline across later file arrival', t => {
  const f = fixture(t), map = scanProject(f.root), task = prepareGuideTask(map, 'core', f.fields), baseline = JSON.stringify(task);
  assert.equal(compareGuideTask(task, map).available, false); assert.equal(compareGuideTask(task, map, { freshRead: true, captured: true }).available, false);
  const other = structuredClone(map); other.project.root += '-other'; assert.equal(compareGuideTask(task, other, { freshRead: true }).available, false);
  const remote = structuredClone(map); remote.project.source = { kind: 'github', url: 'https://github.com/owner/repo' }; assert.equal(compareGuideTask(task, remote, { freshRead: true }).available, false);
  f.write('future.js', 'export const future = true;'); const review = compareGuideTask(task, scanProject(f.root), { freshRead: true });
  assert.ok(review.fileChanges.some(c => c.file === 'future.js' && c.kind === 'now present' && c.inScope));
  assert.equal(JSON.stringify(task), baseline); assert.ok(review.limitations.some(s => s.includes('not every repository file')));
});
