// Source-linked reading, shared by API, live UI and exports. No target executes.
export function explainWorkflow(workflow, nodes, review) {
  const byId = new Map(workflow.calculations.map(c => [c.id, c]));
  const incoming = new Map(), outgoing = new Map(), products = new Map(), owners = new Map();
  for (const n of nodes.filter(n => n.kind !== 'mission')) for (const p of n.files) owners.set(p, owners.has(p) ? null : n);
  for (const r of workflow.relationships) {
    if (!incoming.has(r.to)) incoming.set(r.to, []);
    if (!outgoing.has(r.from)) outgoing.set(r.from, []);
    incoming.get(r.to).push(r); outgoing.get(r.from).push(r);
    const callee = byId.get(r.to), call = byId.get(r.from)?.calls.find(c => c.source.line === r.source.line && c.source.column === r.source.column);
    const positional = call?.positionalArguments || r.arguments, keywords = call?.keywordArguments || [];
    const unsupported = positional.some(p => p.startsWith('*') || p.startsWith('...')) || keywords.some(k => !k.name);
    r.inputBindings = unsupported ? [] : (callee.parameterNames || callee.inputs).map((parameter, i) => ({ parameter,
      expression: keywords.find(k => k.name === parameter)?.expression ?? positional[i] ?? null,
      basis: 'written-call-argument; actual values and defaults unobserved' })).filter(b=>b.parameter && !b.parameter.startsWith('*'));
    r.bindingStatus = unsupported ? 'unresolved-spread-arguments' : 'source-argument-candidates'; r.resultTargets = call?.resultTargets || [];
  }
  for (const p of workflow.dataProducts) for (const s of [...p.producers, ...p.consumers]) {
    if (!products.has(s.calculationId)) products.set(s.calculationId, []);
    if (!products.get(s.calculationId).includes(p)) products.get(s.calculationId).push(p);
  }
  const stages = new Map(review.stages.filter(s => s.calculationId).map(s => [s.calculationId, s]));
  for (const c of workflow.calculations) {
    const owner = owners.get(c.source.path), stage = stages.get(c.id), documentation = c.documentation?.trim()?.split('\n\n')[0];
    const reads = c.io.filter(io => io.operation.includes('read')), writes = c.io.filter(io => io.operation.includes('write'));
    const callers = incoming.get(c.id) || [], callees = outgoing.get(c.id) || [];
    c.purpose = documentation ? `Source documentation: ${documentation}` : stage?.name ? `Declared stage: ${stage.name}. Behavior still needs checks.`
      : owner?.purpose ? `Piece purpose: ${owner.purpose} This function’s individual business role has not been documented.`
      : `This ${c.scopeKind || 'function'} ${reads.length ? `reads ${[...new Set(reads.map(r => r.pathExpression))].join(', ')}` : 'has no recognized file read'}${writes.length ? ` and writes ${[...new Set(writes.map(r => r.pathExpression))].join(', ')}` : ''}. Other effects may exist.`;
    c.why = callers.length ? `Called in analyzed source by ${[...new Set(callers.map(r => byId.get(r.from)?.name))].join(', ')}. Guards and callers determine whether it runs.`
      : 'No supported caller was found. It may be an entry point, callback or dynamic target; this does not establish unused code.';
    c.explanation = { basis: 'source-reading-with-attributed-intent', purposeSource: documentation ? 'source-docstring' : stage?.name ? 'declared-stage' : owner?.purpose ? 'piece-plan' : 'source-syntax',
      inputs: reads.map(r => ({ description: `Reads ${r.pathExpression} using ${r.call}`, source: r.source, guards: r.guards || [] })), parameters: c.inputs,
      steps: c.steps || [], outputs: c.outputs, savedOutputs: writes,
      callers: callers.map(r => ({ id: r.from, source: r.source, argumentBindings: r.inputBindings })),
      consumers: (products.get(c.id) || []).filter(p => p.producers.some(s => s.calculationId === c.id)).flatMap(p => p.consumers.map(s => ({ id: s.calculationId, product: p.pathExpression, source: s.source }))),
      calls: callees.map(r => r.id), throughCalls:callees.flatMap(r=>{
        const target=byId.get(r.to), bindings=new Map((r.inputBindings || []).filter(b=>b.expression!==null).map(b=>[b.parameter,b.expression]));
        return target.io.filter(io=>io.operation.includes('read')).map(io=>({calculationId:target.id,calculation:target.name,source:io.source,callSource:r.source,
          expression:io.operand?renderOperand(io.operand,bindings):io.pathExpression,
          basis:'one-call source argument substitution; not resolved runtime paths or observed I/O'}));
      }), unknowns: ['Branches and calls may never execute.', 'Mutable values, dynamic paths, hidden inputs and runtime ordering are not established by source syntax.'] };
    c.resources = (c.facts || []).filter(f => ['worker-pool','execution-control','bounded-read-cue','collection-release'].includes(f.kind));
    const repeated = new Map();
    for (const call of c.calls) {
      if (!call.bindingReference) continue; // Unknown receivers/libraries are not an equivalence claim.
      const ref = call.bindingReference;
      const key = JSON.stringify([call.target, ref.kind, ref.module, ref.targetName, call.positionalArguments || call.arguments, call.keywordArguments]);
      if (!repeated.has(key)) repeated.set(key, []); repeated.get(key).push(call);
    }
    for (const group of repeated.values()) if (group.length > 1) workflow.findings.push({
      id: `computation:${c.id}:${group[0].line}:${group[0].column}`, type: 'potential-repeated-computation', severity: 'warning', confidence: 'Needs runtime evidence',
      confidenceRationale: 'Repeated supported source-call syntax with the same written arguments. Mutable values, side effects and branch execution remain unknown.',
      calculationIds: [c.id], sources: group.map(call => call.source), title: `${c.name}: inspect repeated calls to ${group[0].target}`,
      impact: `${group.length} matching source call sites; this is not a repeated execution count or proof of equivalent results.`,
      suggestedAction: 'Inspect purity, argument identities, guards and existing memoization. Measure repeated execution before introducing reuse.',
      correctnessTradeoff: 'Identical syntax can read different mutable values or intentionally repeat side effects. Preserve directional argument order and every observation.',
      requiredVerification: ['Prove matching input identities and equivalent outputs, including side effects, ordering and failure behavior.', 'Measure cache hits/misses and calls on the same workload.'], reuseCues: c.reuseCues });
  }
  for (const r of workflow.relationships) {
    const caller = byId.get(r.from), callee = byId.get(r.to);
    const call = caller.calls.find(c => c.source.line === r.source.line && c.source.column === r.source.column);
    if (!call?.loopDepth) continue;
    const reads = callee.io.filter(io => io.operation.includes('read'));
    if (!reads.length) continue;
    workflow.findings.push({ id: `helper-read:${r.id}`, type: 'potential-repeated-read-through-helper', severity: 'warning', confidence: 'Needs runtime evidence',
      confidenceRationale: 'A supported source-call candidate inside a loop reaches a declaration with file-read syntax. Invocation, guards and effective caching are unobserved.',
      calculationIds: [caller.id, callee.id], sources: [r.source, ...reads.map(io => io.source)],
      title: `${caller.name}: inspect loop calls reading through ${callee.name}`,
      impact: `The loop calls a helper that contains reads of ${[...new Set(reads.map(io => io.pathExpression))].join(', ')}. Actual reads and avoidable bytes are unknown.`,
      suggestedAction: 'Measure helper calls and effective reads. Inspect existing cache and source identity before sharing an immutable prepared value.',
      correctnessTradeoff: 'A helper may observe changing files or have other side effects; moving a read outside a loop can change results.',
      requiredVerification: ['Compare exact outputs and side effects with and without shared preparation.', 'Measure actual reads/cache hits on the same source and workload.'], reuseCues: [...caller.reuseCues,...callee.reuseCues] });
  }
  for (const f of workflow.findings) {
    const affected = f.calculationIds.map(id => byId.get(id)).filter(Boolean);
    const sites = affected.flatMap(c => c.io.filter(io => f.sources.some(s => s.path === io.source.path && s.line === io.source.line)));
    const exclusive = f.type === 'potential-repeated-read' && sites.length === 2 && f.calculationIds.length === 1 &&
      (sites[0].guards || []).some(g => (sites[1].guards || []).some(h => g.line === h.line && g.column === h.column && g.branch !== h.branch));
    const related = new Set(f.calculationIds);
    for (const id of f.calculationIds) for (const r of outgoing.get(id) || []) related.add(r.to);
    const cues = [...related].flatMap(id => byId.get(id)?.reuseCues || []);
    f.reviewContext = { branchRelationship: exclusive ? 'opposite-branches-of-same-condition' : 'not-established',
      reuseStatus: cues.length ? 'existing-controls-need-validation' : 'not-established',
      explanation: exclusive ? 'These reads occupy opposite branches of one condition. They are not sequential reads in one branch; repeated calls and loops still need observation.'
        : cues.length ? 'Reuse/scheduling cues exist here or in a directly linked helper. Inspect effectiveness before adding another mechanism.' : 'No supported local reuse cue was found; reuse elsewhere remains possible.', relatedReuseCues: cues };
    f.reviewPriority = exclusive ? 'context-first' : f.workload?.potentialIterations && BigInt(f.workload.potentialIterations) >= 1_000_000n ? 'high' : 'normal';
  }
  for (const checkpoint of workflow.checkpoints) {
    const stage = stages.get(checkpoint.calculationId);
    const candidates = (stage?.checkpointProducts || []).map(id => review.products.find(p => p.id === id)).filter(p => p && p.path && p.path === checkpoint.literalPath);
    checkpoint.enclosingGuards = checkpoint.guards || [];
    checkpoint.declaredContract = candidates.length === 1 ? { stageId: stage.id, productId: candidates[0].id, contract: candidates[0].contract,
      coverageStatus: candidates[0].status, extensionStatus: candidates[0].extensionStatus, basis:'supplied-stage-and-exact-product-path; not observed restart safety' } : null;
  }
  workflow.resourcePlan = { basis:'source-cues-and-separate-reported-metrics', pools:workflow.calculations.flatMap(c=>c.resources.filter(f=>f.kind==='worker-pool').map(f=>({
    calculationId:c.id,source:f.source,workersExpression:f.workersExpression,
    literalRequestedWorkers:/^[1-9][0-9]{0,5}$/.test(f.workersExpression || '')?Number(f.workersExpression):null,
    actualWorkers:null, note:'Constructor argument only; nested pools, environment overrides, hosts and actual utilization require observations.' }))),
    waits:workflow.calculations.flatMap(c=>c.resources.filter(f=>f.kind==='execution-control' && ['result','wait','join'].includes(f.member)).map(f=>({calculationId:c.id,source:f.source,expression:f.expression,loopDepth:f.loopDepth}))),
    metrics:review.observations.map(o=>({observationId:o.id,stageId:o.stageId,metrics:o.metrics,freshness:o.freshness})),
    bottleneckVerdict:'unmeasured; correlate comparable CPU, I/O-wait, memory and elapsed observations before changing concurrency' };
  workflow.reading = { version: 1, entryCandidates: workflow.calculations.filter(c => c.scopeKind === 'module' || !incoming.has(c.id)).map(c => c.id),
    declaredStageOrder: review.stages.map(s => ({ id: s.id, name: s.name || s.id, dependsOn: s.dependsOn, calculationId: s.calculationId, inputs: s.inputs, outputs: s.outputs })),
    summary: `${workflow.calculations.length} calculations, ${workflow.relationships.length} supported call candidates and ${workflow.dataProducts.length} possible file products. Select an entry to follow source connections; source order is not execution order.`, completeRuntimeTrace: false };
  return workflow;
}

function renderOperand(node, bindings, depth=0) {
  if(depth>10) return '[expression depth limit]';
  if(node.kind==='name')return bindings.get(node.name) ?? node.name;
  if(node.kind==='literal')return JSON.stringify(node.value);
  if(node.kind==='call')return `${node.target}(${node.arguments.map(n=>renderOperand(n,bindings,depth+1)).join(', ')})`;
  return node.text || '[unresolved expression]';
}

export function traceCalculation(workflow, entryId, { limit = 200 } = {}) {
  if (!Number.isSafeInteger(limit) || limit < 1 || limit > 1000) throw Error('Trace limit must be 1–1000.');
  const byId = new Map(workflow.calculations.map(c => [c.id, c]));
  if (!byId.has(entryId)) throw Error('Choose a captured calculation.');
  const links = new Map();
  for (const r of workflow.relationships) { if (!links.has(r.from)) links.set(r.from, []); links.get(r.from).push(r); }
  const steps = [], visited = new Set(), queue = [{ id: entryId, depth: 0, via: null }];
  let i = 0;
  for (; i < queue.length && steps.length < limit; i++) {
    const s = queue[i], c = byId.get(s.id);
    if (visited.has(s.id)) { steps.push({ ...s, name: c.name, repeatedReference: true }); continue; }
    visited.add(s.id); steps.push({ ...s, name: c.name, source: c.source, explanation: c.explanation });
    for (const r of links.get(s.id) || []) queue.push({ id: r.to, depth: s.depth + 1, via: r.source });
  }
  return { basis: 'breadth-first-source-reading; not a runtime schedule', steps, truncated: i < queue.length, limit };
}
