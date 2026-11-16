import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { snapshotHtml } from '../src/export.js';
import { scanProject } from '../src/scan.js';

function fixture(t) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'buildmap-export-'));
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  return root;
}

test('export embeds assets and safely round-trips untrusted project data', t => {
  const root = fixture(t);
  fs.mkdirSync(path.join(root, '.buildmap'));
  fs.writeFileSync(path.join(root, '.buildmap/project.json'), JSON.stringify({ mission: '</script><img src=x onerror=evil()> $&' }));
  const map = scanProject(root);
  const html = snapshotHtml(map);
  assert.doesNotMatch(html, /src="\.\/app.js"|href="\.\/styles.css"/);
  assert.doesNotMatch(html, /<img src=x/);
  const data = html.match(/<script id="buildmapSnapshot" type="application\/json">([\s\S]*?)<\/script>/)[1];
  assert.deepEqual(JSON.parse(data), map);
  assert.match(html, /<script type="module">/); assert.match(html, /<style>/);
  assert.match(html, /Walkthrough <span>Free<\/span>/);
  assert.doesNotMatch(html, /PAID PREVIEW|Walkthrough <span>Paid<\/span>/);
  assert.doesNotMatch(html, /from '\.\/guide-tasks\.js'/); assert.match(html, /function prepareGuideTask/);
});

test('CLI HTML export exits, writes one file, and refuses to overwrite existing work', t => {
  const root = fixture(t);
  const output = path.join(root, 'map.html');
  const invoke = () => spawnSync(process.execPath, ['src/cli.js', root, '--html', output], { encoding: 'utf8', timeout: 5000 });
  const result = invoke(); assert.equal(result.status, 0, result.stderr);
  const html = fs.readFileSync(output, 'utf8'); assert.match(html, /buildmapSnapshot/);
  const second = invoke(); assert.equal(second.status, 1);
  assert.equal(fs.readFileSync(output, 'utf8'), html);
});
