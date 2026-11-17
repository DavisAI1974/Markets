import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { evaluateAnalysis } from './review-evidence.js';

// Import deliberately documented structured logs; never execute the project or
// infer identities from a stage name, log timestamp or machine address.
export function importMeasurements(root, input, base = { version: 1 }) {
  const fd = fs.openSync(input, fs.constants.O_RDONLY | (fs.constants.O_NOFOLLOW || 0));
  let bytes;
  try {
    const stat = fs.fstatSync(fd);
    if (!stat.isFile() || stat.size > 1_000_000) throw Error('Measurement input must be a regular file no larger than 1 MB.');
    bytes = Buffer.alloc(1_000_001); let size = 0, n;
    do { n = fs.readSync(fd, bytes, size, bytes.length - size, null); size += n; } while (n && size < bytes.length);
    if (size > 1_000_000) throw Error('Measurement input grew beyond 1 MB.'); bytes = bytes.subarray(0, size);
  } finally { fs.closeSync(fd); }
  if (!base || base.version !== 1) throw Error('The base analysis must use version 1.');
  const result = JSON.parse(JSON.stringify(base));
  for (const key of ['products','stages','runtime','workloads','events']) if (!Array.isArray(result[key] ?? [])) throw Error(`Invalid base ${key}.`); else result[key] ||= [];
  const text = bytes.toString('utf8').trim(); let imported;
  try { const doc = JSON.parse(text); if (doc.version !== 1 || !(Array.isArray(doc.runtime) || Array.isArray(doc.events))) throw Error('Expected version: 1 and runtime or events array.'); imported = { ...doc, runtime: doc.runtime || [] }; }
  catch (error) {
    const lines = text.split(/\r?\n/).filter(l => l.trim());
    if (lines.length > 100) throw Error('At most 100 structured log records can be imported.');
    imported = { version: 1, runtime: [], products: [], stages: [], events: [] };
    for (const [i, line] of lines.entries()) {
      let record;
      try { record = JSON.parse(line); } catch { throw Error(`Invalid JSON on log line ${i + 1}.`); }
      if(record.version===1 && record.type==='buildmap-stage-event' && record.event) imported.events.push(record.event);
      else if (record.type !== 'buildmap-measurement' || record.version !== 1 || !record.observation) throw Error(`Log line ${i + 1} must be a version 1 buildmap-measurement or buildmap-stage-event.`);
      else imported.runtime.push(record.observation);
    }
  }
  const rootPath = fs.realpathSync(root), realInput = fs.realpathSync(input), relative = path.relative(rootPath, realInput).split(path.sep).join('/');
  const inside = relative && relative !== '..' && !relative.startsWith('../') && !path.isAbsolute(relative);
  const digest = crypto.createHash('sha256').update(bytes).digest('hex');
  for (const section of ['products','stages','runtime','workloads','events']) {
    if (!Array.isArray(imported[section] ?? [])) throw Error(`Imported ${section} must be an array.`);
    for (const entry of imported[section] || []) {
      if (result[section].some(e => e.id === entry.id)) throw Error(`Conflicting ${section} id ${entry.id}; review and choose which record to retain.`);
      const copy = JSON.parse(JSON.stringify(entry));
      if (['runtime','events'].includes(section) && inside) copy.bindings = { ...copy.bindings, [relative]: digest };
      result[section].push(copy);
    }
  }
  const assessed = evaluateAnalysis(result);
  const invalid = assessed.diagnostics.filter(d => /Missing or duplicate|require|must|invalid|Expected|Unsupported|exceed|does not match/i.test(d.message));
  if (invalid.length) throw Error(invalid.map(d => `${d.section} ${d.id || ''}: ${d.message}`).join('\n'));
  return { document: result, imported: imported.runtime.length, importedEvents: (imported.events || []).length,
    input: { path: relative, sourceHash: digest, bound: Boolean(inside) },
    note: inside ? 'Imported records are bound to these log bytes; source provenance still requires explicit source bindings/identity. Review before adopting.'
      : 'Input is outside the project; observations remain unbound unless they already provide project-relative bindings.' };
}
