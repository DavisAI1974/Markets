import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import crypto from 'node:crypto';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';
import { scanProject } from '../src/scan.js';

const repo = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const digest = value => crypto.createHash('sha256').update(value).digest('hex');

test('BuildMap optional scratch inspection adds visible lineage/gaps without false scientific acceptance', t => {
  const generated = spawnSync('python3', ['-m', 'adaptive_locality.buildmap_trial'], {
    cwd: repo, encoding: 'utf8', timeout: 5000,
    env: { ...process.env, PYTHONDONTWRITEBYTECODE: '1' },
  });
  assert.equal(generated.status, 0, generated.stderr);
  const { manifest, comparison_contract: contract } = JSON.parse(generated.stdout);
  assert.equal(contract.mode, 'STATIC_SOURCE_INSPECTION_ONLY');
  assert.equal(contract.scientific_jobs_eliminated, 0);
  assert.equal(contract.scientific_predictive_improvement_claimed, false);
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'adaptive-buildmap-trial-'));
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  fs.mkdirSync(path.join(root, '.buildmap'));
  fs.writeFileSync(path.join(root, '.buildmap', 'project.json'), JSON.stringify(manifest));
  fs.writeFileSync(path.join(root, 'README.md'),
    '# Research-only scratch map\nNo real sources, scientific calculations or production wiring execute.\n');
  const before = new Map();
  for (const comp of manifest.components) for (const file of comp.files) {
    const absolute = path.join(repo, file);
    if (!fs.existsSync(absolute)) continue; // Explicitly declared missing acceptance gate.
    const contents = fs.readFileSync(absolute);
    before.set(file, digest(contents));
    const destination = path.join(root, file);
    fs.mkdirSync(path.dirname(destination), { recursive: true });
    fs.copyFileSync(absolute, destination);
  }
  const map = scanProject(root);
  const ids = new Set(manifest.components.map(c => c.id));
  const observed = map.edges.filter(e => e.observed && ids.has(e.from) && ids.has(e.to));
  const missing = contract.known_scientific_gates.map(id => map.nodes.find(n => n.id === id));
  assert.ok(observed.length >= 1,
    'Native scanner must add at least one observed import edge beyond a static geometric report');
  assert.ok(missing.every(n => n?.status === 'planned' && n.missingFiles.length > 0),
    'No missing science gate may appear completed');
  assert.ok(map.nodes.filter(n => ids.has(n.id))
    .every(n => !['verified', 'live'].includes(n.status)));
  assert.ok(map.project.counts.verified === 0 && map.project.counts.live === 0);
  for (const [file, sha] of before) {
    assert.equal(digest(fs.readFileSync(path.join(repo, file))), sha);
    assert.equal(digest(fs.readFileSync(path.join(root, file))), sha);
  }
  // Measured gain is ONLY review navigability of actual source dependencies
  // and missing gates, not predictive accuracy or scientific equivalence.
  const comparison = {
    baselineNativeSourceEdges: 0, // standalone numerical report has no source-call graph
    trialNativeSourceEdges: observed.length,
    declaredUnverifiedScienceGates: missing.length,
    falsifiedVerificationClaims: map.nodes.filter(n => ids.has(n.id) &&
      ['verified','live'].includes(n.status)).length,
    changedSourceFiles: 0,
    scientificJobsEliminated: 0,
  };
  assert.ok(comparison.trialNativeSourceEdges > comparison.baselineNativeSourceEdges);
  assert.equal(comparison.falsifiedVerificationClaims, 0);
  assert.equal(comparison.changedSourceFiles, 0);
  process.stdout.write('BuildMap trial inspection-only comparison: ' +
    JSON.stringify(comparison) + '\n');
});
