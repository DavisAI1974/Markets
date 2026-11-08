import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import { inspectResources } from './workflow-risk.js';
import { pythonCandidateGroups } from './imports.js';

export const WORKFLOW_LIMITS = [
  'Static Python and JavaScript syntax only; no target module is imported and no workflow runs. Actual reads, jobs, pair comparisons, memory, elapsed time and savings remain unknown.',
  'Adapter covers module bodies, top-level/nested functions, direct methods of top-level classes and comprehension axes/filters. Source-call candidates link unique undecorated functions through supported local imports; general argument/data propagation, nested classes, inheritance/dispatch, shell/YAML execution, dynamic paths and SQL remain unknown.',
  'Call links identify possible source declarations, not execution, scheduling, actual parameter values or runtime data flow. Rebindings, star imports and decorated targets are excluded conservatively; dynamic mutation, re-exports and runtime import paths remain unresolved.',
  'Eager comprehensions construct containers if reached; generator expressions defer their body, which may never be consumed. Neither syntax proves end-to-end lazy scheduling. Filters, dependent iterables and callers can change work. Generator-body I/O is not inferred.',
  'A literal filename match is only a possible shared product. Working directories, source identity, schema, axes, coverage, checkpoint compatibility and actual reuse are unverified.',
  'Nested loops describe possible fan-out, not a job or pair counter. Literal range products assume every iteration reaches the inner body; guards, breaks, exceptions and dependent bounds can change actual work. AB/BA equivalence is never assumed.',
  'Cache, lazy scheduler, FFT and checkpoint names/decorators are review cues only. Their presence does not prove effective reuse; their absence does not prove a cache or checkpoint is missing.',
  'Default analysis covers at most 64 Python files / 4 MB total. Explicit whole-project snapshots process every eligible Python file in sequential batches of at most 64 files / 4 MB. The scanner’s 1 MB per-file and parser’s per-process time limit (5 seconds by default, BUILDMAP_ANALYZER_TIMEOUT_MS) / 16 MB output limits still apply; a failed batch is bisected so one difficult file is reported alone. Missing Python, unsupported files and failures stay visible. No findings is not clearance to run.'
];

const DEFAULT_ANALYZER_TIMEOUT_MS = 5000;

// Per-process analyzer timeout. BUILDMAP_ANALYZER_TIMEOUT_MS overrides the
// 5000 ms default; anything that is not a positive integer keeps the default.
export function analyzerTimeoutMs(env = process.env) {
  const value = env.BUILDMAP_ANALYZER_TIMEOUT_MS;
  return value !== undefined && /^[1-9][0-9]{0,8}$/.test(String(value).trim()) ? Number(value) : DEFAULT_ANALYZER_TIMEOUT_MS;
}

// Source bytes came from the existing inventory/read boundary. -I/-S prevent a
// mapped project's modules/site hooks from being imported by this trusted reader.
function spawnAnalyzer(batch, timeoutMs) {
  const result = spawnSync('python3', ['-I', '-S', fileURLToPath(new URL('./python-analyzer.py', import.meta.url))], {
    input: JSON.stringify(batch.map(s => ({ source: s.source }))), encoding: 'utf8', timeout: timeoutMs, maxBuffer: 16 * 1024 * 1024
  });
  if (result.error?.code === 'ENOENT') return { failure: 'missing-runtime' };
  if (result.error?.code === 'ETIMEDOUT' || result.signal === 'SIGTERM') return { failure: 'timeout' };
  if (result.error?.code === 'ENOBUFS') return { failure: 'output-limit' };
  if (result.error || result.status !== 0) return { failure: `exit-${result.status ?? result.error?.code ?? 'unknown'}` };
  let parsed;
  try { parsed = JSON.parse(result.stdout); } catch { return { failure: 'invalid-output' }; }
  if (!Array.isArray(parsed) || parsed.length !== batch.length) return { failure: 'invalid-output' };
  return { parsed };
}

function unavailableReason(failure, timeoutMs, isolated) {
  const cause = failure === 'missing-runtime' ? 'python3 is missing'
    : failure === 'timeout' ? `the analyzer timed out after ${timeoutMs} ms (BUILDMAP_ANALYZER_TIMEOUT_MS)`
    : failure === 'output-limit' ? 'the analyzer exceeded the 16 MB parser output limit'
    : failure === 'invalid-output' ? 'the analyzer returned unusable output' : `the analyzer failed (${failure})`;
  return `Python analysis unavailable for ${isolated ? 'this file' : 'this batch'}: ${cause}. File inventory and the free map remain available.`;
}

// Batches run through the analyzer; a failed batch is bisected (in bounded
// and whole-project modes alike) so one slow or difficult file is reported on
// its own instead of flipping every file in the batch to unavailable.
export function pythonGuides(sources, guides, { all = false, runAnalyzer = null, timeoutMs = analyzerTimeoutMs() } = {}) {
  let selected = [], bytes = 0, missingRuntime = false;
  const run = runAnalyzer || (batch => spawnAnalyzer(batch, timeoutMs));
  const unavailable = (batch, failure) => { for (const s of batch) Object.assign(guides.get(s.path), { status: 'analyzer-unavailable',
    reason: unavailableReason(failure, timeoutMs, batch.length === 1) }); };
  function analyze(batch) {
    if (!batch.length) return;
    if (missingRuntime) { unavailable(batch, 'missing-runtime'); return; }
    const result = run(batch);
    if (!result.parsed) {
      const failure = result.failure || 'invalid-output';
      missingRuntime = failure === 'missing-runtime';
      if (!missingRuntime && batch.length > 1) {
        const middle = Math.floor(batch.length / 2); analyze(batch.slice(0, middle)); analyze(batch.slice(middle));
      } else unavailable(batch, failure);
      return;
    }
    batch.forEach((s, i) => Object.assign(guides.get(s.path), result.parsed[i]));
  }
  for (const source of sources) {
    const guide = guides.get(source.path);
    const size = Buffer.byteLength(source.source);
    if (all && selected.length && (selected.length >= 64 || bytes + size > 4_000_000)) { analyze(selected); selected = []; bytes = 0; }
    if (selected.length >= 64 || bytes + size > 4_000_000) {
      guide.status = 'analysis-limit'; guide.reason = 'Python analysis exceeds 64 files or 4 MB total; this file remains unreviewed.'; continue;
    }
    selected.push(source); bytes += size;
  }
  analyze(selected);
}

export function buildWorkflow(guides) {
  const calculations = [], products = new Map(), findings = [];
  const files = [...guides.values()].filter(g => g.path.toLowerCase().endsWith('.py')).map(g => ({ path: g.path, sourceHash: g.sourceHash, status: g.status, reason: g.reason }));
  const source = (file, item) => ({ path: file.path, sourceHash: file.sourceHash, line: item.line, column: item.column });
  for (const file of guides.values()) {
    if (!/\.(py|js|mjs|cjs)$/i.test(file.path) || file.status !== 'parsed') continue;
    for (const fn of file.functions) {
      const id = `${file.path}:${fn.line}:${fn.column}`;
      const at = source(file, fn);
      const calc = { id, name: fn.name, scopeKind: fn.scopeKind, sourceLinkable: fn.sourceLinkable, exported: fn.exported, generator: fn.generator, language: fn.language || 'Python', basis: 'source-syntax', source: at, inputs: fn.parameters,
        calls: fn.calls.map(c => ({ ...c, source: source(file, c) })), outputs: fn.returns, transformations: fn.transformations.map(t => ({ ...t, source: source(file, t) })),
        io: fn.io.map(io => ({ ...io, source: source(file, io) })),
        facts: (fn.facts || []).map(f => ({ ...f, source: source(file, f) })),
        loopPaths: fn.loopPaths, comprehensions: fn.comprehensions.map(c => ({ ...c, source: source(file, c) })),
        reuseCues: [...fn.reuseCues, ...fn.decorators].map(c => ({ ...c, source: source(file, c) })),
        documentation: fn.documentation || null, parameterNames: fn.parameterNames || fn.parameters, steps: (fn.steps || []).map(s => ({ ...s, source: source(file, s) })),
        fieldAccesses:(fn.fieldAccesses || []).map(s=>({...s,source:source(file,s)})),sql:(fn.sql || []).map(s=>({...s,source:source(file,s)})),
        purpose: 'Written function/module syntax; business purpose and whether this path runs need review.',
        why: 'A declaration is not proof it is called. Review entry-point wiring and runtime counters before optimizing.' };
      calculations.push(calc);
      for (const io of calc.io) {
        if (io.pathKind === 'symbolic') continue; // Same parameter spelling across scopes is not a shared product identity.
        const key = io.pathExpression;
        if (!products.has(key)) products.set(key, { id: `literal:${key}`, pathExpression: key, basis: 'possible-literal-path-match', compatibility: 'unknown', producers: [], consumers: [] });
        const product = products.get(key), site = { calculationId: id, source: io.source, call: io.call, loopDepth: io.loopDepth };
        if (io.operation.includes('write')) product.producers.push(site);
        if (io.operation.includes('read')) product.consumers.push(site);
      }
      // Keep maximal nested paths so a three-deep nest does not emit a second
      // warning for its two-deep prefix. Distinct inner branches stay separate.
      const paths = fn.loopPaths.filter(p => !fn.loopPaths.some(q => q.length > p.length && p.every((a, i) => a.line === q[i].line && a.column === q[i].column)));
      for (const axes of paths) {
        const literal = axes.every(a => a.literalRangeCount !== null);
        const potentialIterations = literal ? axes.reduce((n, a) => n * BigInt(a.literalRangeCount), 1n).toString() : null;
        findings.push({ id: `fanout:${id}:${axes.at(-1).line}:${axes.at(-1).column}`, type: 'nested-loop-fanout', severity: 'warning',
          confidence: 'Likely', confidenceRationale: 'Nested loop syntax is observed; actual execution and useful work per iteration are unknown.',
          calculationIds: [id], sources: axes.map(a => source(file, a)),
          title: `${fn.name}: review ${axes.length} nested loops before running`,
          impact: `Possible expansion: ${axes.map(a => `${a.target} in ${a.iterable}`).join(' × ')}. This is an iteration model, not a job or pair count.`,
          workload: { symbolic: axes.map(a => a.iterable).join(' × '), potentialIterations, actualJobs: null, pairComparisons: null, remainingJobs: null },
          suggestedAction: 'Measure eligible/completed/remaining jobs and directional pair comparisons separately on a small fixture. Inspect existing lazy scheduling and reuse before proposing changes.',
          correctnessTradeoff: 'Do not remove directional AB/BA work, skip observations, or replace missing values without a proven scientific equivalence.',
          requiredVerification: ['Confirm entry point and reachable loop paths, guards, early exits and actual dimension sizes.', 'Measure jobs separately from inner pair comparisons; inspect caches, saved indexes and restart receipts.'],
          reuseCues: calc.reuseCues });
      }
      for (const comp of calc.comprehensions.filter(c => c.axes.length >= 2)) {
        const literal = comp.axes.every(a => a.literalRangeCount !== null && !a.async);
        const potentialIterations = literal ? comp.axes.reduce((n, a) => n * BigInt(a.literalRangeCount), 1n).toString() : null;
        findings.push({ id: `comprehension:${id}:${comp.line}:${comp.column}`, type: 'comprehension-fanout', severity: 'warning', confidence: 'Likely',
          confidenceRationale: 'Multiple comprehension axes are observed; reachability, filter selectivity, collection size and runtime impact are unknown.',
          calculationIds: [id], sources: [comp.source], title: `${fn.name}: review ${comp.axes.length}-axis ${comp.kind} expansion`,
          impact: `${comp.evaluation === 'eager-container' ? 'An eager container is written' : 'A deferred generator expression is written'} over ${comp.axes.map(a => a.iterable).join(' × ')}. Filters and dependent iterables can change expansion. A generator may never be consumed; callers may also materialize it.`,
          workload: { symbolic: comp.axes.map(a => a.iterable).join(' × '), potentialIterations, actualJobs: null, pairComparisons: null, remainingJobs: null,
            evaluation: comp.evaluation, filters: comp.axes.flatMap(a => a.filters) },
          suggestedAction: 'Inspect the caller, existing lazy scheduler, caches and saved indexes. Measure container size, actual eligible jobs and directional pairs separately before proposing a change.',
          correctnessTradeoff: 'Changing materialization can change evaluation timing, side effects, exceptions and restart order. Preserve filters, scientific directionality and exact saved-job identity.',
          requiredVerification: ['Check dimension sizes, dependent bounds, filters and whether the expression is reached or consumed.', 'Measure allocation and job/pair counters; do not equate bounded dispatch with lazy upstream construction.'], reuseCues: calc.reuseCues });
      }
    }
  }
  for (const product of products.values()) {
    // Two source sites are not confirmed duplicate execution. A single read
    // inside a loop is reviewable too, without inventing a repeated-read count.
    if (product.consumers.length < 2 && !product.consumers.some(c => c.loopDepth > 0)) continue;
    const calculationIds = [...new Set(product.consumers.map(c => c.calculationId))];
    findings.push({ id: `reads:${product.id}`, type: 'potential-repeated-read', severity: 'warning', confidence: 'Needs runtime evidence',
      confidenceRationale: 'Literal read-call sites are observed. Branch exclusivity, path identity, library behavior and cache hits are unknown.',
      calculationIds, sources: product.consumers.map(c => c.source), productId: product.id,
      title: `Review possible repeated reads of ${product.pathExpression}`,
      impact: `${product.consumers.length} read-call site(s) use this literal path${product.consumers.some(c => c.loopDepth) ? ', including a site inside a loop' : ''}. Actual bytes, execution count and avoidable work are unknown.`,
      suggestedAction: 'Trace whether these sites run in the same workflow and resolve to the same source. Inspect shared preparation, caching and saved indexes before considering reuse.',
      correctnessTradeoff: 'Repeated reads may be intentional verification or different observations. Reuse requires matching source identity, schema, coverage, order and scientific semantics.',
      requiredVerification: ['Measure actual reads and effective cache/restart reuse on a small input.', 'Check producer/consumer paths, source identities and checkpoint compatibility.'],
      reuseCues: calculations.filter(c => calculationIds.includes(c.id)).flatMap(c => c.reuseCues) });
  }
  const links = calculationLinks(calculations, guides);
  const resources = inspectResources(calculations);
  findings.push(...resources.findings);
  const statuses = Object.fromEntries([...new Set(files.map(f => f.status))].sort().map(status => [status, files.filter(f => f.status === status).length]));
  const javascriptFiles = [...guides.values()].filter(g => /\.(js|mjs|cjs)$/i.test(g.path));
  const outsideAdapter = [...guides.values()].filter(g => !/\.(py|js|mjs|cjs)$/i.test(g.path)).map(g => ({ path: g.path,
    reason: 'Outside the Python/JavaScript calculation/risk adapters. Import inventory does not establish workflow risk coverage.' }));
  return { version: 1, basis: 'static-source-syntax', files, calculations, dataProducts: [...products.values()], ...links,
    checkpoints: resources.checkpoints,
    coverage: { inventoryFiles: guides.size, pythonFiles: files.length, parsedPythonFiles: statuses.parsed || 0,
      statuses, unreviewedPython: files.filter(f => f.status !== 'parsed'), outsideAdapter,
      javascriptFiles: javascriptFiles.length, parsedJavaScriptFiles: javascriptFiles.filter(f => f.status === 'parsed').length,
      unreviewedJavaScript: javascriptFiles.filter(f => f.status !== 'parsed').map(f => ({ path: f.path, status: f.status, reason: f.reason })),
      boundary: 'Counts cover discovered/explicitly declared inventory only. Ignored, excluded, deleted, unreadable and unlisted files may be absent. Parsing does not establish reachable execution or complete semantic coverage.' },
    findings: findings.sort((a, b) => a.type.localeCompare(b.type) || a.id.localeCompare(b.id)), limitations: WORKFLOW_LIMITS };
}

// Link declarations already read by this scanner. Never load additional target
// files, execute imports, resolve dynamic methods, or turn spelling into proof.
function calculationLinks(calculations, guides) {
  const declarations = new Map();
  for (const c of calculations.filter(c => c.sourceLinkable)) {
    const key = JSON.stringify([c.source.path, c.name]);
    if (!declarations.has(key)) declarations.set(key, []);
    declarations.get(key).push(c);
  }
  const relationships = [], unresolvedCalls = [];
  let totalCallSites = 0;
  for (const calculation of calculations) for (const call of calculation.calls) {
    totalCallSites++;
    const ref = call.bindingReference;
    if (!ref) continue;
    const modules = ref.kind === 'local-function' ? [calculation.source.path] : ref.kind === 'javascript-import'
      ? [path.posix.normalize(path.posix.join(path.posix.dirname(calculation.source.path), ref.module))].flatMap(p => /\.(js|mjs|cjs)$/.test(p) ? [p] : [p, `${p}.js`, `${p}/index.js`]).filter(p => guides.has(p))
      : moduleCandidates(calculation.source.path, ref, guides);
    const targets = modules.length === 1 ? (declarations.get(JSON.stringify([modules[0], ref.targetName])) || [])
      .filter(c => ref.kind !== 'javascript-import' || c.exported) : [];
    if (targets.length !== 1) {
      unresolvedCalls.push({ calculationId: calculation.id, target: call.target, source: call.source,
        reason: modules.length > 1 ? 'Multiple local module paths match; no target selected.'
          : 'No unique analyzed undecorated declaration. Target may be external, unselected, re-exported or unsupported.',
        candidateFiles: modules });
      continue;
    }
    const target = targets[0];
    relationships.push({ id: `${calculation.id}:call:${call.line}:${call.column}`, kind: 'candidate-source-call',
      basis: ref.kind === 'local-function' ? 'unique-same-file-declaration' : 'supported-import-and-unique-declaration',
      from: calculation.id, to: target.id, target: call.target, source: call.source, targetSource: target.source,
      ...(ref.kind === 'imported-function' ? { importSource: { path: calculation.source.path, sourceHash: calculation.source.sourceHash, line: ref.line, column: ref.column } } : {}),
      arguments: call.arguments, execution: 'unobserved', dataFlow: 'unverified' });
  }
  return { relationships, unresolvedCalls, callCoverage: { totalCallSites, linkedCallSites: relationships.length,
    unresolvedCallSites: totalCallSites - relationships.length } };
}

function moduleCandidates(importer, ref, guides) {
  // Same candidate bases and order as the map's import resolver (imports.js):
  // a relative level from the importer, or importer directory then root. The
  // map edge takes the first present file; call links stay conservative and
  // treat a file present in more than one base as ambiguous (no link).
  if (ref.level) {
    const parts = path.posix.dirname(importer).split('/').filter(p => p && p !== '.');
    if (ref.level - 1 > parts.length) return [];
  }
  const spec = `${'.'.repeat(ref.level || 0)}${ref.module}`;
  return [...new Set(pythonCandidateGroups(importer, spec).flat().filter(file => guides.has(file)))];
}
