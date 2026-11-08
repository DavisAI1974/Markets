import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { readIntent, readFinishedProduct, summarizeMarkdown } from '../src/intent.js';

test('summarizes the first useful README prose', () => {
  const text = summarizeMarkdown('# Thing\n\nThing turns raw events into a useful signal.\n\n## Install\nDo stuff.');
  assert.equal(text, 'Thing turns raw events into a useful signal.');
});

test('prefers explicit BuildMap mission over README inference', () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'buildmap-intent-'));
  fs.writeFileSync(path.join(root, 'README.md'), '# Repo\n\nREADME mission.');
  const intent = readIntent(root, { mission: 'Declared mission.' });
  assert.equal(intent.text, 'Declared mission.');
  assert.equal(intent.confidence, 'declared');
});

test('does not block when intent is missing', () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'buildmap-empty-'));
  const intent = readIntent(root, {});
  assert.equal(intent.confidence, 'unknown');
  assert.match(intent.text, /interview/i);
});

test('finished product descriptions retain attribution and fall back honestly when absent or malformed', () => {
  const intent = { text: 'A documented goal.', source: 'README.md', confidence: 'inferred' };
  const declared = readFinishedProduct({ finishedProduct: { experience: ' A simple screen. ', behavior: ' Complete the intended job. ' } }, intent);
  assert.deepEqual(declared, { experience: 'A simple screen.', behavior: 'Complete the intended job.', source: '.buildmap/project.json', confidence: 'declared' });
  for (const finishedProduct of [undefined, null, [], { behavior: '' }, { behavior: 'Goal', experience: 42 }]) {
    const diagnostics = [];
    const result = readFinishedProduct({ finishedProduct }, intent, diagnostics);
    assert.equal(result.experience, null); assert.equal(result.behavior, intent.text); assert.equal(result.confidence, 'inferred');
    assert.equal(result.source, 'README.md'); assert.equal(diagnostics.length, finishedProduct === undefined ? 0 : 1);
  }
  const unknown = readFinishedProduct({}, { text: 'Placeholder', source: null, confidence: 'unknown' });
  assert.equal(unknown.behavior, null); assert.equal(unknown.experience, null);
});
