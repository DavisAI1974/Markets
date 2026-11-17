import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { scanProject } from '../src/scan.js';

function fixture(t) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'buildmap-git-'));
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  const git = (...args) => {
    const r = spawnSync('git', ['-C', root, ...args], { encoding: 'utf8' });
    assert.equal(r.status, 0, r.stderr); return r.stdout;
  };
  git('init', '--quiet');
  const write = (rel, text = '') => { fs.mkdirSync(path.dirname(path.join(root, rel)), { recursive: true }); fs.writeFileSync(path.join(root, rel), text); };
  return { root, git, write };
}

test('Git inventory respects nested ignore rules/negation without dropping tracked source', t => {
  const { root, git, write } = fixture(t);
  write('.gitignore', '*.generated.js\ncache/\nbuild/\n');
  write('src/.gitignore', 'skip*.js\n!skip-keep.js\n');
  write('src/skip.js'); write('src/skip-keep.js'); write('src/new.js'); write('src/output.generated.js');
  write('build/tracked.js'); write('build/generated.js'); write('node_modules/dependency.js'); write('cache/derived.js');
  git('add', '-f', 'build/tracked.js');
  const map = scanProject(root);
  assert.equal(map.scan.inventoryMode, 'git');
  assert.deepEqual(map.nodes.flatMap(n => n.files).sort(), ['build/tracked.js', 'src/new.js', 'src/skip-keep.js']);
});

test('mapping a Git subtree does not pull in siblings or deleted tracked files', t => {
  const { root, git, write } = fixture(t);
  write('outer.js'); write('packages/app/main.js'); write('packages/app/deleted.js');
  git('add', '.'); fs.unlinkSync(path.join(root, 'packages/app/deleted.js'));
  const map = scanProject(path.join(root, 'packages/app'));
  assert.deepEqual(map.nodes.flatMap(n => n.files), ['main.js']);
  assert.equal(map.diagnostics.length, 0);
});

test('explicit manifest files may override ignores; Git fsmonitor hooks are disabled', t => {
  const { root, git, write } = fixture(t);
  write('.gitignore', 'config.js\n'); write('config.js', 'export const config = 1;');
  write('.buildmap/project.json', JSON.stringify({ components: [{ id: 'config', files: ['config.js'] }] }));
  write('hook.sh', `#!/bin/sh\ntouch "${root}/hook-ran"\n`); fs.chmodSync(path.join(root, 'hook.sh'), 0o755);
  git('config', 'core.fsmonitor', path.join(root, 'hook.sh'));
  const map = scanProject(root);
  assert.equal(map.nodes.find(n => n.id === 'config').implementation, 'complete');
  assert.equal(fs.existsSync(path.join(root, 'hook-ran')), false);
});

test('a symlink to the project root preserves declared assets without escaping containment', t => {
  const { root, write } = fixture(t);
  write('settings.json', '{}');
  write('.buildmap/project.json', JSON.stringify({ components: [{ id: 'settings', files: ['settings.json'] }] }));
  const parent = fs.mkdtempSync(path.join(os.tmpdir(), 'buildmap-link-'));
  t.after(() => fs.rmSync(parent, { recursive: true, force: true }));
  const alias = path.join(parent, 'project'); fs.symlinkSync(root, alias, 'dir');
  const map = scanProject(alias);
  assert.equal(map.project.root, alias);
  assert.equal(map.nodes.find(n => n.id === 'settings').implementation, 'complete');
});
