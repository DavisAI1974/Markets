import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { spawnSync } from 'node:child_process';
import { readIntent, readFinishedProduct } from './intent.js';
import { sourceReferences, resolveImport } from './imports.js';
import { buildOutcomes, buildCompletion } from './outcomes.js';
import { CODE_GUIDE_LIMITS } from './code-guide.js';
import { pythonGuides, buildWorkflow, WORKFLOW_LIMITS } from './workflow.js';
import { explainWorkflow } from './workflow-explain.js';
import { readAnalysis } from './review-evidence.js';
import { readCollectedRuns, observedReuseGroups } from './collected-runs.js';

const CODE_EXT = new Set(['.js','.mjs','.cjs','.jsx','.ts','.tsx','.py','.go','.rs','.java','.kt','.kts','.rb','.php','.cs','.c','.cc','.cpp','.h','.hpp','.swift','.scala','.sh','.html','.htm','.css','.yaml','.yml','.toml','.service','.timer']);
const SPECIAL_CODE = new Set(['Dockerfile','Makefile']);
const IGNORE_DIRS = new Set(['.git','node_modules','dist','build','coverage','.next','.cache','.venv','venv','__pycache__','target','vendor']);
const STATES = ['planned','coded','connected','computing','verified','live'];
const WEIGHTS = { planned: 0, coded: 20, connected: 45, computing: 65, verified: 85, live: 100 };

export function scanProject(root, { source = null, workflowFiles = null, workflowAll = false } = {}) {
  if (typeof workflowAll !== 'boolean') throw new TypeError('workflowAll must be a boolean.');
  if (workflowFiles !== null && (!Array.isArray(workflowFiles) || workflowFiles.some(f => typeof f !== 'string'))) {
    throw new TypeError('workflowFiles must be an array of exact project-relative Python paths.');
  }
  root = path.resolve(root);
  const diagnostics = [];
  const manifest = readJson(root, '.buildmap/project.json', diagnostics);
  const rawEvidence = readJson(root, '.buildmap/evidence.json', diagnostics);
  const evidence = evidenceCollections(rawEvidence, diagnostics);
  const components = validComponents(manifest.components, diagnostics);
  const inventory = inventoryFiles(root, diagnostics);
  const files = inventory.files;
  const fileSet = new Set(files.map(f => f.path));
  // Declared implementation can include assets/configuration outside discovered
  // extensions. Never follow a manifest path or symlink out of the project.
  for (const component of components) {
    for (const rel of normalizeFiles(component.files || component.file || [])) {
      if (fileSet.has(rel)) continue;
      try {
        if (!safeFile(root, rel)) continue;
        const buffer = fs.readFileSync(path.join(root, rel));
        files.push({ path: rel, size: buffer.length, hash: hash(buffer) });
        fileSet.add(rel);
      } catch { /* Missing files remain planned. */ }
    }
  }
  files.sort((a,b) => a.path.localeCompare(b.path));
  const discovery = discoverImports(root, files, fileSet, diagnostics, workflowFiles === null ? null : new Set(workflowFiles), workflowAll);
  const importEdges = discovery.edges;
  const fileHashes = new Map(files.map(f => [f.path, f.hash]));
  const inputCache = new Map();
  function readInputHash(rel) {
    if (inputCache.has(rel)) return inputCache.get(rel);
    let result;
    if (!rel || rel.includes('\\') || rel.includes('\0') || path.posix.isAbsolute(rel) ||
      /^[A-Za-z]:/.test(rel) || path.posix.normalize(rel) !== rel || rel === '..' || rel.startsWith('../')) {
      result = { hash: null, reason: 'Use an exact project-relative file path.' };
    } else {
      try {
        result = safeFile(root, rel)
          ? { hash: fileHashes.get(rel) || hash(fs.readFileSync(path.join(root, rel))) }
          : { hash: null, reason: 'Not a regular file inside the mapped root.' };
      } catch {
        result = { hash: null, reason: 'File is missing, unreadable, or outside the mapped root.' };
      }
    }
    inputCache.set(rel, result);
    return result;
  }
  let intent;
  try { intent = readIntent(root, manifest); }
  catch (err) {
    diagnostics.push({ code: 'unreadable-intent', message: `Could not read intent documents: ${err.code || err.message}.` });
    intent = { text: 'Project intent could not be read. Check the documents and permissions.', source: null, confidence: 'unknown' };
  }
  const finishedProduct = readFinishedProduct(manifest, intent, diagnostics);
  const assignedFiles = new Set();
  const fileOwners = new Map();
  for (const component of components) {
    const componentFiles = normalizeFiles(component.files || component.file || []);
    const id = component.id || slug(component.name || componentFiles[0] || 'component');
    for (const file of componentFiles) {
      if (!fileOwners.has(file)) fileOwners.set(file, []);
      fileOwners.get(file).push(id);
    }
  }
  const nodes = [];

  function makeNode(fields, receipt) {
    const present = fields.files.filter(f => fileSet.has(f));
    const complete = fields.files.length > 0 && present.length === fields.files.length;
    const wired = importEdges.some(e => present.includes(e.from) || present.includes(e.to));
    const base = complete ? (wired ? 'connected' : 'coded') : 'planned';
    const sourceHashes = Object.fromEntries(present.map(f => [f, fileHashes.get(f)]));
    const conflictingFiles = fields.files.filter(f => (fileOwners.get(f)?.length || 0) > 1);
    const assessment = receipt && conflictingFiles.length
      ? { accepted: false, reason: 'Implementation ownership is ambiguous. Resolve overlapping component file assignments before claiming component behavior.' }
      : assessEvidence(receipt, complete, sourceHashes, readInputHash);
    return { ...fields, presentFiles: present, missingFiles: fields.files.filter(f => !fileSet.has(f)),
      conflictingFiles,
      implementation: complete ? 'complete' : present.length ? 'partial' : 'missing',
      baseStatus: base, status: resolveStatus({ base, evidence: assessment.accepted ? receipt.status : null }),
      evidence: receipt || null, evidenceAssessment: assessment, sourceHashes,
      codeGuide: { basis: 'source-syntax', limitations: [...CODE_GUIDE_LIMITS.map(s => `JavaScript adapter: ${s}`), ...WORKFLOW_LIMITS], files: fields.files.map(file =>
        discovery.guides.get(file) || { path: file, status: 'missing', reason: 'No readable implementation file is present.', sourceHash: null, functions: [] }) } };
  }

  for (const component of components) {
    const componentFiles = normalizeFiles(component.files || component.file || []);
    const id = component.id || slug(component.name || componentFiles[0] || 'component');
    for (const f of componentFiles) {
      assignedFiles.add(f);
      if (fileOwners.get(f).length > 1) diagnostics.push({ code: 'overlapping-file', nodeId: id, priority: 'blocker',
        message: `${f} is declared by multiple components (${fileOwners.get(f).join(', ')}). Resolve ownership; the declaration is retained but cannot grant component proof or cross-piece wiring.` });
    }
    if (component.status) diagnostics.push({ code: 'manifest-status', nodeId: id, message: `Manifest status ${component.status} is descriptive only; proof requires an evidence record.` });
    nodes.push(makeNode({ id, name: component.name || titleFromFile(componentFiles[0] || id), kind: 'component',
      group: component.group || inferGroup(componentFiles[0]), files: componentFiles,
      purpose: component.purpose || component.description || inferPurpose(componentFiles),
      contributes: component.contributes || component.goal || '', visual: normalizeVisual(component.visual, component),
      plannedDependencies: Array.isArray(component.dependsOn) ? [...new Set(component.dependsOn)] : [],
      dependencyIntent: Object.hasOwn(component, 'dependsOn') ? 'declared' : 'unspecified', source: 'manifest'
    }, Object.hasOwn(evidence.components || {}, id) ? evidence.components[id] : undefined));
  }

  for (const file of files) {
    if (assignedFiles.has(file.path)) continue;
    nodes.push(makeNode({ id: `file:${file.path}`, name: titleFromFile(file.path), kind: 'file', group: inferGroup(file.path),
      files: [file.path], purpose: inferFilePurpose(root, file.path), contributes: '', visual: inferVisual(file.path),
      plannedDependencies: [], dependencyIntent: 'unspecified', source: 'discovered'
    }, Object.hasOwn(evidence.files || {}, file.path) ? evidence.files[file.path] : undefined));
  }
  auditEvidenceTargets(evidence, nodes, diagnostics, readInputHash);
  const edges = buildComponentEdges(nodes, importEdges);
  const outcomeMap = buildOutcomes(manifest.outcomes, rawEvidence.outcomes, nodes,
    (receipt, complete, hashes) => assessEvidence(receipt, complete, hashes, readInputHash));
  diagnostics.push(...outcomeMap.diagnostics);
  const completionMap = buildCompletion(manifest.completion, rawEvidence.completion, outcomeMap.outcomes);
  diagnostics.push(...completionMap.diagnostics);
  const counts = Object.fromEntries(STATES.map(s => [s, nodes.filter(n => n.status === s).length]));
  const progress = nodes.length ? Math.round(nodes.reduce((sum,n) => sum + WEIGHTS[n.status], 0) / nodes.length) : 0;
  const gaps = findGaps(nodes, edges, diagnostics, intent);
  const missingPlanned = nodes.filter(n => n.implementation !== 'complete').length;
  const mode = ['greenfield', 'brownfield'].includes(manifest.mode) ? manifest.mode
    : (!files.length || missingPlanned > Math.max(1, Math.floor(nodes.length / 3)) ? 'greenfield' : 'brownfield');
  // The mission is an intent target, not an independently tested runtime piece.
  nodes.push({ id: '__mission__', name: manifest.name || source?.repoName || path.basename(root), kind: 'mission', group: 'Mission',
    files: [], presentFiles: [], missingFiles: [], status: 'planned', purpose: intent.text, contributes: '',
    visual: { kind: 'goal', label: 'Intended outcome' }, plannedDependencies: [], evidence: null, source: intent.source || 'interview-needed' });
  for (const node of nodes) if (node.contributes) edges.push({ from: node.id, to: '__mission__', type: 'contributes' });
  const result = { project: { name: manifest.name || source?.repoName || path.basename(root), root, source: source || { kind: 'local', snapshot: false }, mode, intent, finishedProduct, completion: completionMap.completion, progress,
    progressLabel: 'Evidence index', counts, uncertainty: intent.confidence === 'unknown' ? ['Intent is unknown; interview recommended.'] : [] },
    states: STATES, nodes, edges: uniqueEdges(edges), outcomes: outcomeMap.outcomes, gaps, diagnostics,
    workflow: buildWorkflow(discovery.guides),
    scan: { inventoryMode: inventory.mode, fileCount: files.length, importCount: discovery.importCount, httpReferenceCount: discovery.httpCount,
      dependencyLanguages: ['JavaScript', 'TypeScript', 'Python', 'HTML', 'CSS'], javascriptParser: 'acorn', httpAdapter: 'literal-fetch/node-http-path', heuristic: true },
    generatedAt: new Date().toISOString() };
  result.workflow.scope = { mode: workflowFiles === null ? workflowAll ? 'whole-python-inventory' : 'bounded-inventory' : 'selected-files',
    batching: workflowAll ? 'all-eligible-files' : 'first-bounded-batch',
    requestedFiles: workflowFiles === null ? null : [...new Set(workflowFiles)].sort(),
    unavailableFiles: workflowFiles === null ? [] : [...new Set(workflowFiles)].filter(f => !fileSet.has(f) || path.extname(f).toLowerCase() !== '.py').sort() };
  result.workflow.review = readAnalysis(root, result.workflow.calculations);
  explainWorkflow(result.workflow, nodes, result.workflow.review);
  result.workflow.collected = readCollectedRuns(root,Object.fromEntries(fileHashes),result.workflow.calculations);
  for(const run of result.workflow.collected.runs)run.reuseGroups=observedReuseGroups(run);
  const observedIndex=new Map();
  for(const run of result.workflow.collected.runs.filter(r=>r.eligibleForComparison))for(const c of run.calculations){if(!c.calculationId)continue;if(!observedIndex.has(c.calculationId))observedIndex.set(c.calculationId,[]);observedIndex.get(c.calculationId).push({runId:run.runId,collectorId:run.collectorId,calculationId:c.calculationId,observedEntries:c.calls,resumable:c.resumable});}
  for(const finding of result.workflow.findings)finding.observationContext=finding.calculationIds.flatMap(id=>observedIndex.get(id)||[]);
  result.workflow.coverage.inventoryMode = inventory.mode;
  result.fingerprint = fingerprint({ ...result, generatedAt: undefined, manifest, evidence: rawEvidence });
  return result;
}

export function resolveStatus({ base = 'planned', evidence }) {
  const baseIndex = Math.max(0, STATES.indexOf(base));
  const evidenceIndex = STATES.indexOf(evidence);
  return STATES[Math.max(baseIndex, evidenceIndex >= 0 ? evidenceIndex : 0)];
}

function assessEvidence(receipt, complete, hashes, readInputHash) {
  if (!receipt) return { accepted: false, reason: 'No explicit evidence record.' };
  if (typeof receipt !== 'object' || Array.isArray(receipt) || !STATES.includes(receipt.status)) return { accepted: false, reason: 'Invalid evidence record or status.' };
  if (!complete) return { accepted: false, reason: 'Implementation is incomplete; this claim cannot describe the current piece.' };
  if (STATES.indexOf(receipt.status) >= 3 && !['note', 'command', 'proof'].some(k => typeof receipt[k] === 'string' && receipt[k].trim())) {
    return { accepted: false, reason: 'A status alone is not evidence; describe the observation or check.' };
  }
  let assessment;
  if (receipt.sourceHashes !== undefined) {
    const binding = receipt.sourceHashes;
    if (!binding || typeof binding !== 'object' || Array.isArray(binding) ||
      Object.keys(hashes).some(f => binding[f] !== hashes[f]) || Object.keys(binding).some(f => !Object.hasOwn(hashes, f))) {
      assessment = { accepted: false, binding: 'stale', reason: 'Source hashes no longer match all implementation files. Rerun the observation or check.' };
    } else assessment = { accepted: true, binding: 'current', reason: 'Recorded evidence matches the current implementation files; BuildMap does not execute or authenticate it.' };
  } else assessment = { accepted: true, binding: 'unbound', reason: 'User-recorded evidence; freshness is unknown because it has no source hashes.' };
  if (receipt.inputHashes === undefined) return assessment;
  const inputs = assessInputs(receipt.inputHashes, readInputHash);
  if (inputs.binding !== 'current') {
    const failures = inputs.issues.map(i => `${i.file}: ${i.reason}`).join('; ');
    return { ...assessment, accepted: false, binding: inputs.binding, inputs,
      reason: `${assessment.accepted ? '' : assessment.reason + ' '}Input binding rejected: ${inputs.reason || failures} Rerun the observation or check before recording new hashes.` };
  }
  return { ...assessment, inputs, reason: `${assessment.reason} Selected input hashes match; unlisted files and environments are not covered.` };
}

function assessInputs(binding, readInputHash) {
  const inputs = { binding: 'current', currentHashes: {}, issues: [] };
  if (!binding || typeof binding !== 'object' || Array.isArray(binding) || !Object.keys(binding).length) {
    return { ...inputs, binding: 'invalid', reason: 'inputHashes must be a nonempty object keyed by selected project-relative file paths.' };
  }
  const current = [];
  for (const [file, recorded] of Object.entries(binding)) {
    const observed = readInputHash(file);
    current.push([file, observed.hash]);
    const validDigest = typeof recorded === 'string' && /^[a-f0-9]{64}$/.test(recorded);
    if (!validDigest) {
      inputs.binding = 'invalid'; inputs.issues.push({ file, reason: 'Expected a lowercase 64-character SHA-256.' });
    }
    if (observed.reason || (validDigest && observed.hash !== recorded)) {
      if (inputs.binding !== 'invalid') inputs.binding = 'stale';
      inputs.issues.push({ file, reason: observed.reason || 'Contents changed since the recorded check.' });
    }
  }
  inputs.currentHashes = Object.fromEntries(current);
  return inputs;
}

function findGaps(nodes, edges, diagnostics, intent) {
  const gaps = [];
  const add = (kind, nodeId, message, priority = 'warning', detail = {}) => gaps.push({ id: `${kind}:${nodeId || 'project'}:${gaps.length}`, kind, nodeId, message, priority, ...detail });
  if (intent.confidence === 'unknown') add('missing-intent', null, 'Add a mission or README to explain what the build should achieve.');
  for (const n of nodes) {
    if (n.implementation !== 'complete') add('missing-implementation', n.id, n.missingFiles.length ? `Missing implementation: ${n.missingFiles.join(', ')}.` : 'Declare implementation files for this planned piece.', 'blocker');
    if (n.evidence && !n.evidenceAssessment.accepted) add('unsupported-evidence', n.id, n.evidenceAssessment.reason, 'blocker');
    if (n.evidenceAssessment.accepted && n.evidenceAssessment.binding === 'unbound' && STATES.indexOf(n.status) >= 3) add('unbound-evidence', n.id, 'Evidence is recorded but its freshness is unknown. Bind it to the current source hashes.', 'info');
    if (n.implementation === 'complete' && !edges.some(e => e.type === 'code' && (e.from === n.id || e.to === n.id))) add('no-observed-connection', n.id, 'No cross-piece source connection found. This may be an entry point or use wiring the scanner cannot see.');
    if (n.implementation === 'complete' && STATES.indexOf(n.status) < 3) add('unproved', n.id, 'Observe useful work or record a behavior check before claiming computing or verified.');
    for (const edge of edges.filter(e => e.type === 'code' && e.to === n.id && e.planStatus === 'undeclared')) {
      add('unexpected-dependency', n.id, `Observed dependency on ${edge.from} is outside this piece’s explicit dependsOn plan. Review the plan or the wiring.`, 'warning', { dependencyId: edge.from, observations: edge.observations });
    }
    for (const dep of n.plannedDependencies) {
      if (!nodes.some(x => x.id === dep)) add('unknown-dependency', n.id, `Declared dependency ${dep} has no piece on the map.`, 'blocker');
      else if (!edges.some(e => e.type === 'code' && e.from === dep && e.to === n.id)) add('unobserved-dependency', n.id, `Declared dependency on ${dep} has no matching source connection. Confirm its wiring; discovery is heuristic.`);
    }
  }
  for (const d of diagnostics) add(d.code, d.nodeId || null, d.message, d.priority || (d.code === 'invalid-config' ? 'blocker' : 'warning'), {
    ...(d.scope ? { scope: d.scope } : {}),
    ...(d.outcomeId ? { outcomeId: d.outcomeId } : {}), ...(Object.hasOwn(d, 'evidence') ? { evidence: d.evidence } : {}) });
  const order = { blocker: 0, warning: 1, info: 2 };
  return gaps.sort((a,b) => order[a.priority] - order[b.priority]);
}

function evidenceCollections(raw, diagnostics) {
  const result = {};
  for (const scope of ['components', 'files']) {
    const collection = raw[scope];
    if (collection === undefined) continue;
    if (!collection || typeof collection !== 'object' || Array.isArray(collection)) {
      diagnostics.push({ code: 'invalid-config', evidence: collection, message: `.buildmap/evidence.json ${scope} must be an object keyed by target ids/paths.` });
      continue;
    }
    result[scope] = collection;
  }
  return result;
}

function auditEvidenceTargets(evidence, nodes, diagnostics, readInputHash) {
  const componentById = new Map(nodes.filter(n => n.kind === 'component').map(n => [n.id, n]));
  const ownerByFile = unambiguousOwners(nodes);
  for (const scope of ['components', 'files']) for (const [target, receipt] of Object.entries(evidence[scope] || {})) {
    if (scope === 'files' && ownerByFile.has(target) && !ownerByFile.get(target)) {
      diagnostics.push({ code: 'ambiguous-evidence-target', priority: 'blocker', evidence: receipt,
        message: `Evidence files.${target} refers to overlapping component assignments; resolve ownership before attaching this file claim.` });
      continue;
    }
    const owner = scope === 'components' ? componentById.get(target) : ownerByFile.get(target);
    if (!owner) {
      diagnostics.push({ code: 'unmapped-evidence', priority: 'blocker', evidence: receipt,
        message: `Evidence ${scope}.${target} has no mapped target; it cannot advance any piece.` });
      continue;
    }
    if (scope === 'files' && owner.kind === 'component') {
      const present = owner.presentFiles.includes(target);
      const assessment = assessEvidence(receipt, present, present ? { [target]: owner.sourceHashes[target] } : {}, readInputHash);
      owner.fileEvidence ??= [];
      owner.fileEvidence.push({ file: target, evidence: receipt, assessment });
      diagnostics.push({ code: 'file-evidence-in-component', nodeId: owner.id,
        priority: assessment.accepted ? 'info' : 'blocker', evidence: receipt,
        message: `File claim for ${target} is retained in ${owner.id}'s inspector. It does not establish component behavior; use a component-level receipt for that claim.${assessment.accepted ? '' : ` File claim rejected: ${assessment.reason}`}` });
    } else if (!receipt) {
      // Falsy records would otherwise look like absent evidence on the node.
      diagnostics.push({ code: 'invalid-evidence-record', nodeId: owner.id, priority: 'blocker', evidence: receipt,
        message: `Evidence ${scope}.${target} is not a valid record. Describe the observation or check in an object.` });
    }
  }
}

function validComponents(value, diagnostics) {
  if (value === undefined) return [];
  if (!Array.isArray(value)) { diagnostics.push({ code: 'invalid-config', message: 'Manifest components must be an array.' }); return []; }
  const ids = new Set(['__mission__']);
  return value.filter(c => {
    if (!c || typeof c !== 'object' || Array.isArray(c)) { diagnostics.push({ code: 'invalid-config', message: 'Each component must be an object.' }); return false; }
    const stringFields = ['id', 'name', 'group', 'purpose', 'description', 'contributes', 'goal', 'action', 'status'];
    const listValue = c.files ?? c.file;
    const invalidStrings = stringFields.some(k => c[k] !== undefined && typeof c[k] !== 'string');
    const invalidFiles = listValue !== undefined && typeof listValue !== 'string' && (!Array.isArray(listValue) || listValue.some(f => typeof f !== 'string'));
    const invalidDependencies = c.dependsOn !== undefined && (!Array.isArray(c.dependsOn) || c.dependsOn.some(d => typeof d !== 'string'));
    const invalidVisual = c.visual !== undefined && typeof c.visual !== 'string' && (!c.visual || typeof c.visual !== 'object' || Array.isArray(c.visual) || ['kind', 'label'].some(k => c.visual[k] !== undefined && typeof c.visual[k] !== 'string'));
    if (invalidStrings || invalidFiles || invalidDependencies || invalidVisual) { diagnostics.push({ code: 'invalid-config', message: 'Invalid component fields: descriptions must be strings, files strings or arrays, dependencies an array of ids, and visuals strings or objects.' }); return false; }
    const id = c.id || slug(c.name || normalizeFiles(c.files || c.file || [])[0] || 'component');
    if (typeof id !== 'string' || id.startsWith('file:') || ids.has(id)) { diagnostics.push({ code: 'invalid-config', message: `Duplicate or reserved component id: ${id}.` }); return false; }
    ids.add(id); return true;
  });
}

function safeFile(root, rel) {
  if (!rel || path.isAbsolute(rel) || rel === '..' || rel.startsWith('../')) return false;
  const full = path.join(root, rel);
  const real = fs.realpathSync(full);
  const relative = path.relative(fs.realpathSync(root), real);
  return !relative.startsWith(`..${path.sep}`) && relative !== '..' && !path.isAbsolute(relative) && fs.statSync(full).isFile();
}

function inventoryFiles(root, diagnostics) {
  // Git's own ignore semantics handle negation, nested rules, and tracked files.
  // Disable fsmonitor so reading an unfamiliar repository cannot run its hook.
  const args = ['-c', 'core.fsmonitor=false', '-C', root, 'ls-files', '--cached', '--others', '--exclude-standard', '-z',
    ...[...IGNORE_DIRS].filter(d => d !== '.git').map(d => `--exclude=${d}/`)];
  const result = spawnSync('git', args, { encoding: 'utf8', timeout: 5000, maxBuffer: 16 * 1024 * 1024, env: { ...process.env, LC_ALL: 'C' } });
  if (result.status !== 0) {
    if (result.error?.code !== 'ENOENT' && !result.stderr?.includes('not a git repository')) diagnostics.push({ code: 'git-inventory-unavailable', message: 'Git inventory failed; using filesystem discovery with default directory exclusions.' });
    return { files: walkFiles(root, diagnostics), mode: 'filesystem' };
  }
  const files = [];
  for (const rel of new Set(result.stdout.split('\0').filter(Boolean))) {
    if (rel.startsWith('.buildmap/') || (!CODE_EXT.has(path.extname(rel).toLowerCase()) && !SPECIAL_CODE.has(path.basename(rel)))) continue;
    try {
      // Git can list deleted tracked files and symlinks; neither establishes a
      // present implementation. Paths are relative to the requested subtree.
      if (!fs.lstatSync(path.join(root, rel)).isFile() || !safeFile(root, rel)) continue;
      const buffer = fs.readFileSync(path.join(root, rel));
      files.push({ path: rel, size: buffer.length, hash: hash(buffer) });
    } catch (err) {
      if (err.code !== 'ENOENT') diagnostics.push({ code: 'unreadable-file', message: `Could not read ${rel}: ${err.code}.` });
    }
  }
  return { files, mode: 'git' };
}

function walkFiles(root, diagnostics) {
  const out = [];
  const stack = [''];
  while (stack.length) {
    const relDir = stack.pop();
    let entries;
    try { entries = fs.readdirSync(path.join(root, relDir), { withFileTypes: true }); }
    catch (err) { diagnostics.push({ code: 'unreadable-directory', message: `Could not scan ${relDir || '.'}: ${err.code}.` }); continue; }
    for (const entry of entries) {
      const rel = slash(path.join(relDir, entry.name));
      if (entry.isDirectory()) {
        if (IGNORE_DIRS.has(entry.name) || entry.name.startsWith('.')) continue;
        stack.push(rel); continue;
      }
      if (!entry.isFile() || (!CODE_EXT.has(path.extname(rel).toLowerCase()) && !SPECIAL_CODE.has(entry.name))) continue;
      try { const buffer = fs.readFileSync(path.join(root, rel)); out.push({ path: rel, size: buffer.length, hash: hash(buffer) }); }
      catch (err) { diagnostics.push({ code: 'unreadable-file', message: `Could not read ${rel}: ${err.code}.` }); }
    }
  }
  return out;
}

function discoverImports(root, files, fileSet, diagnostics, workflowFiles, workflowAll) {
  const edges = [], requests = [], providers = [], guides = new Map(), pythonSources = [];
  for (const file of files) {
    const ext = path.extname(file.path).toLowerCase();
    const supported = ['.js', '.mjs', '.cjs', '.py'].includes(ext);
    const guide = { path: file.path, status: supported ? 'unreadable' : 'unsupported', sourceHash: file.hash, functions: [],
      reason: supported ? 'Source could not be read for this explanation.' : 'Function explanations support JavaScript .js, .mjs, .cjs and optional Python .py.' };
    guides.set(file.path, guide);
    if (supported && file.size > 1_000_000) { guide.status = 'size-limit'; guide.reason = 'Source explanation is skipped above the existing 1 MB discovery limit.'; }
    if (file.size > 1_000_000) { diagnostics.push({ code: 'large-file', message: `${file.path} is present but import discovery is skipped above 1 MB.` }); continue; }
    try {
      const bytes = fs.readFileSync(path.join(root, file.path));
      const references = sourceReferences(bytes.toString('utf8'), ext);
      if (supported) {
        if (hash(bytes) !== file.hash) { guide.status = 'changed-during-scan'; guide.reason = 'Source changed while being scanned. Refresh before inspecting its functions.'; }
        else if (references.error) { guide.status = 'parse-error'; guide.reason = references.error; }
        else if (ext === '.py') {
          if (workflowFiles && !workflowFiles.has(file.path)) {
            guide.status = 'not-selected'; guide.reason = 'Outside the explicitly selected Python analysis files; free inventory and source imports are retained.';
          } else pythonSources.push({ path: file.path, source: bytes.toString('utf8') });
        }
        else { guide.status = 'parsed'; guide.reason = 'Parsed source declarations; no code was executed.'; guide.functions = references.functions; }
      }
      if (references.error) diagnostics.push({ code: 'javascript-parse-failed', message: `${file.path}: ${references.error}` });
      requests.push(...references.requests.map(r => ({ ...r, file: file.path })));
      providers.push(...references.providers.map(p => ({ ...p, file: file.path })));
      for (const spec of references.imports) {
        const target = resolveImport(file.path, spec, fileSet, ext);
        if (target && target !== file.path) edges.push({ from: file.path, to: target, type: 'import' });
        else if (!target && ext !== '.py' && spec.startsWith('.')) diagnostics.push({ code: 'unresolved-import', message: `${file.path} references ${spec}, but no supported local file resolves.` });
      }
    } catch (err) { diagnostics.push({ code: 'unreadable-file', message: `Source reference discovery failed for ${file.path}: ${err.code || err.name}.` }); }
  }
  pythonGuides(pythonSources, guides, { all: workflowAll });
  const importCount = uniqueEdges(edges).length;
  for (const request of requests) {
    const matches = providers.filter(p => (p.raw ? p.endpoint === request.rawPath : p.endpoint === request.path) && (!p.method || p.method === request.method));
    if (matches.length !== 1) {
      diagnostics.push({ code: matches.length ? 'ambiguous-http-reference' : 'unresolved-http-reference',
        message: `${request.file}:${request.line} requests ${request.method} ${request.endpoint}, but ${matches.length ? 'multiple supported handler conditions match' : 'no supported local handler condition matches'}. HTTP source wiring remains unresolved.` });
    } else if (matches[0].file !== request.file) {
      const provider = matches[0];
      edges.push({ from: request.file, to: provider.file, type: 'http', endpoint: request.endpoint, method: request.method,
        importerLocation: { line: request.line, column: request.column }, providerLocation: { line: provider.line, column: provider.column },
        providerMethod: provider.method });
    }
  }
  const unique = uniqueEdges(edges);
  return { edges: unique, importCount, httpCount: unique.filter(e => e.type === 'http').length, guides };
}

function buildComponentEdges(nodes, importEdges) {
  const owner = unambiguousOwners(nodes);
  const edges = [];
  for (const e of importEdges) {
    // Consistent arrow direction: dependency -> dependent. The original file
    // relationship stays available as evidence, never as a runtime-flow claim.
    const from = owner.get(e.to)?.id, to = owner.get(e.from)?.id;
    if (!from || !to || from === to) continue;
    let edge = edges.find(x => x.from === from && x.to === to && x.type === 'code');
    if (!edge) { edge = { from, to, type: 'code', observations: [] }; edges.push(edge); }
    edge.observations.push({ importer: e.from, imported: e.to, ...(e.type === 'http' ? {
      kind: 'http-source', endpoint: e.endpoint, method: e.method, importerLocation: e.importerLocation,
      providerLocation: e.providerLocation, providerMethod: e.providerMethod, heuristic: true } : {}) });
  }
  for (const edge of edges) {
    const dependent = nodes.find(n => n.id === edge.to);
    edge.planStatus = dependent.dependencyIntent === 'declared' ? (dependent.plannedDependencies.includes(edge.from) ? 'matched' : 'undeclared') : 'unspecified';
  }
  for (const node of nodes) for (const dep of node.plannedDependencies) {
    if (nodes.some(n => n.id === dep)) edges.push({ from: dep, to: node.id, type: 'planned', observed: edges.some(e => e.from === dep && e.to === node.id && e.type === 'code') });
  }
  return edges;
}

function unambiguousOwners(nodes) {
  const owners = new Map();
  for (const node of nodes) for (const file of node.files) {
    owners.set(file, owners.has(file) ? null : node);
  }
  return owners;
}

function readJson(root, rel, diagnostics) {
  try {
    const value = JSON.parse(fs.readFileSync(path.join(root, rel), 'utf8'));
    if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error('expected an object');
    return value;
  } catch (err) {
    if (err.code !== 'ENOENT') diagnostics.push({ code: 'invalid-config', message: `${rel}: ${err.message}` });
    return {};
  }
}
function hash(value) { return crypto.createHash('sha256').update(value).digest('hex'); }
function inferFilePurpose(root, rel) {
  try {
    const text = fs.readFileSync(path.join(root, rel), 'utf8').slice(0, 5000);
    const doc = text.match(/^\s*(?:\/\*\*?\s*|\/\/\s*|#\s*|'''\s*|\"\"\"\s*)([^\n*]{12,180})/m)?.[1];
    if (doc) return doc.trim();
    const exported = [...text.matchAll(/\b(?:export\s+)?(?:async\s+)?function\s+(\w+)|\bexport\s+class\s+(\w+)/g)]
      .map(m => m[1] || m[2]).filter(Boolean).slice(0, 4);
    if (exported.length) return `Defines ${exported.join(', ')}.`;
  } catch {}
  return inferPurpose([rel]);
}

function inferPurpose(files) {
  if (!files.length) return 'Planned capability.';
  const rel = files[0].toLowerCase();
  if (rel.includes('scan')) return 'Discovers the project pieces and their code relationships.';
  if (rel.includes('server')) return 'Serves the living map and current project state.';
  if (rel.includes('cli')) return 'Turns BuildMap into a command you can point at a project.';
  if (rel.includes('test')) return 'Provides verification evidence for behavior.';
  if (rel.includes('intent') || rel.includes('readme')) return 'Recovers the project’s intended outcome from available documentation.';
  if (rel.includes('ui') || rel.includes('app') || rel.includes('public')) return 'Makes the system understandable through an interactive visual interface.';
  return `Implements ${titleFromFile(files[0])}.`;
}

function inferVisual(rel) {
  const p = rel.toLowerCase();
  if (p.includes('scan')) return { kind: 'scanner', label: 'Discover' };
  if (p.includes('server')) return { kind: 'flow', label: 'Serve' };
  if (p.includes('test')) return { kind: 'proof', label: 'Prove' };
  if (p.includes('intent') || p.includes('readme')) return { kind: 'lens', label: 'Understand' };
  if (p.includes('app') || p.includes('ui') || p.includes('public')) return { kind: 'graph', label: 'Visualize' };
  return { kind: 'flow', label: 'Transform' };
}

function normalizeVisual(visual, component) {
  if (typeof visual === 'string') return { kind: visual, label: component.action || visual };
  return { kind: visual?.kind || 'flow', label: visual?.label || component.action || 'Work' };
}

function normalizeFiles(value) {
  const arr = Array.isArray(value) ? value : [value];
  return [...new Set(arr.filter(v => typeof v === 'string' && v.trim()).map(v => path.posix.normalize(v.replaceAll('\\', '/').replace(/^\.\//, ''))))];
}

function inferGroup(rel = '') {
  const parts = slash(rel || '').split('/').filter(Boolean);
  if (!parts.length) return 'Core';
  if (parts[0] === 'src' && parts[1]) return title(parts[1].replace(/\.[^.]+$/,''));
  return title(parts[0].replace(/\.[^.]+$/,''));
}

function titleFromFile(rel) {
  const base = path.basename(rel || 'component').replace(/\.[^.]+$/,'');
  return title(base);
}

function title(value) {
  return String(value).replace(/[-_]+/g,' ').replace(/\b\w/g, c => c.toUpperCase());
}

function slug(value) {
  return String(value).toLowerCase().replace(/[^a-z0-9]+/g,'-').replace(/^-|-$/g,'') || 'component';
}

function uniqueEdges(edges) {
  const seen = new Set();
  return edges.filter(e => {
    const k = JSON.stringify([e.from, e.to, e.type, e.endpoint, e.method, e.importerLocation]);
    if (seen.has(k)) return false;
    seen.add(k); return true;
  });
}

function fingerprint(value) {
  return crypto.createHash('sha1').update(JSON.stringify(value)).digest('hex').slice(0, 12);
}

function slash(value) { return value.split(path.sep).join('/'); }
