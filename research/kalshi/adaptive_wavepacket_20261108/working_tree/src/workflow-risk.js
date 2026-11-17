// Source facts identify review questions. They never certify a restart or size a pool.
export function inspectResources(calculations) {
  const findings = [], checkpoints = [];
  function finding(calc, fact, type, title, impact, action, tradeoff, verification) {
    findings.push({ id: `${type}:${calc.id}:${fact.line}:${fact.column}`, type, severity: 'warning',
      confidence: 'Needs runtime evidence', confidenceRationale: 'Written syntax is observed; reachability, receiver behavior and runtime impact are unmeasured.',
      calculationIds: [calc.id], sources: [fact.source], title: `${calc.name}: ${title}`, impact,
      suggestedAction: action, correctnessTradeoff: tradeoff, requiredVerification: verification, reuseCues: calc.reuseCues });
  }
  for (const calc of calculations) {
    const facts = calc.facts || [], releases = facts.filter(f => f.kind === 'collection-release');
    const saves = [...new Map(facts.filter(f => f.kind === 'persistence' || f.kind === 'checkpoint-helper')
      .map(f => [`${f.kind}:${f.line}:${f.column}:${f.operation}`, f])).values()];
    for (const fact of saves) {
      checkpoints.push({ calculationId: calc.id, ...fact,
        existenceChecks: facts.filter(f => f.kind === 'existence-check'),
        identityComparisons: facts.filter(f => f.kind === 'identity-comparison'),
        compatibility: 'unverified', ownership: 'unknown', restartCompleteness: 'unknown',
        note: 'Nearby checks are source cues, not proof they guard this operation. A matching filename or existence check cannot establish compatible state.' });
      if ((fact.kind === 'checkpoint-helper' || /checkpoint|receipt|restart|saved_state/i.test(fact.pathExpression || '')) && fact.operation !== 'save') {
        finding(calc, fact, 'checkpoint-compatibility', 'check saved-state compatibility before restart',
          'A possible saved-state load is written. Source, calculation, schema, axes, coverage and boundary state are not established by its name or nearby checks.',
          'Inspect the actual load guard, producer and receipt. Supply exact product contracts and verify current source bindings before using saved work.',
          'Never resume a partial or incompatible state silently; preserve scientific ordering and recovery semantics.',
          ['Demonstrate an interrupted/restarted small run equals an uninterrupted run.', 'Exercise stale identity, incomplete writes and incompatible coverage; confirm explicit refusal or recomputation.']);
      }
    }
    for (const fact of facts) {
      if (fact.kind === 'whole-materialization') finding(calc, fact, 'whole-result-memory', 'measure whole-result allocation',
        `Whole-value construction/read syntax: ${fact.expression}. Input size, peak memory and actual execution are unknown.`,
        'Measure peak memory and input bytes. Inspect existing chunking, streaming, memory mapping and reuse before changing allocation.',
        'Chunk boundaries can alter ordering, rolling windows, exceptions and numerical results; preserve exact values and boundary overlap.',
        ['Compare outputs including missing values and boundaries on a representative fixture.', 'Record peak memory and elapsed time under the same workload and environment.']);
      if (fact.kind === 'collection-growth' && fact.loopDepth > fact.initializationLoopDepth && !fact.bounded) {
        const release = releases.some(r => r.receiver === fact.receiver);
        finding(calc, fact, 'collection-retention', 'review collection retention across iterations',
          `${fact.receiver} is initialized outside this loop and grows here. ${release ? 'Release-call syntax is also present; effective bounds still need inspection.' : 'No local release-call syntax was recognized; helpers and guards may still bound it.'} Retained size is unknown.`,
          'Measure retained entries and peak memory; inspect existing releases and dispatch bounds before introducing a bounded buffer.',
          'Dropping pending/results entries can change completeness, ordering and restartability.',
          ['Measure collection high-water mark and prove all eligible outputs are retained or durably consumed.']);
      }
      if (fact.kind === 'execution-control' && fact.loopDepth && ['result','join','wait'].includes(fact.member)) {
        finding(calc, fact, 'sequencing-barrier', 'review a possible per-iteration wait',
          `${fact.expression} appears inside a loop. Whether it waits, serializes useful work, or intentionally bounds dispatch is unknown.`,
          'Measure active workers, CPU and I/O wait. Inspect upstream materialization and bounded scheduling before altering concurrency.',
          'Moving waits can increase memory, change exception order, race shared state or violate dependency order.',
          ['Demonstrate identical results and restart behavior; measure workers and memory under the same workload.']);
      }
    }
  }
  return { findings, checkpoints };
}
