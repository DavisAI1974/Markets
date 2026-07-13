// forecaster_month_pass.workflow.js — the S88 path-forecaster CORPUS-CHARACTERIZATION workflow.
// Coin-style fan-out (Greg S88, "like the coins"): one agent per (commodity x month) characterizes THAT
// month's continuous tape independently, blind to the others; a SYNTHESIS stage accumulates into the
// cross-season table and separates stable-vs-month-specific patterns; a VERIFY stage adversarially kills
// one-month-only patterns. This structure ENFORCES the anti-lock-in rule (a pattern is a per-regime cell,
// not a global rule, until it recurs) — FORECAST_AGENT_DIRECTIVE_S88.md sec 5 + sec 11.
//
// STAGED — do NOT fire until months are on data/nymex-ticks:nymex_cont/. Run in WAVES as the corpus fills:
//   Workflow({ scriptPath: "research/kalshi/forecaster_month_pass.workflow.js",
//              args: { items: [ {root:"CL",month:"2025-07"}, {root:"NG",month:"2025-07"}, ... ] } })
// Pass only the (root,month) pairs whose continuous tape is actually restored locally (the per-agent tool
// reads data/nymex_cont/). Per-agent tool = research/kalshi/month_characterize.py (validated, leakage-gated).

export const meta = {
  name: 'forecaster-month-pass',
  description: 'Per-(commodity,month) continuous-tape characterization -> cross-season synthesis -> adversarial cross-month verify',
  phases: [
    { title: 'Characterize', detail: 'one agent per (commodity x month), blind to the others' },
    { title: 'Synthesize', detail: 'accumulate; separate stable-across-months vs month-specific' },
    { title: 'Verify', detail: 'adversarially kill one-month-only patterns' },
  ],
}

const SCRATCH = '/tmp/claude-0/-home-user-Markets/5407c302-e681-5c10-b49e-00af8a7c0eae/scratchpad'

const MONTH_SCHEMA = {
  type: 'object', additionalProperties: false,
  required: ['root', 'month', 'n_moves', 'top_cells', 'shape_summary', 'piece_alignments', 'caveats'],
  properties: {
    root: { type: 'string' }, month: { type: 'string' }, n_moves: { type: 'integer' },
    top_cells: { type: 'array', items: { type: 'object', additionalProperties: true },
                 description: 'per-cell path distributions worth carrying (cell key, n, peak_usd p50/max, fast_capture, sustain_s, continuation)' },
    shape_summary: { type: 'string', description: 'this month regime: front-loaded vs slow-bleed, magnitude scale, per commodity' },
    piece_alignments: { type: 'array', items: { type: 'string' },
                        description: 'which pieces (imbalance/coiled/curve/temp/tod) aligned with magnitude/shape/continuation THIS month, with rough strength + n' },
    caveats: { type: 'string', description: 'tiny-n / regime / degeneracy honesty for THIS month' },
  },
}

const SYNTH_SCHEMA = {
  type: 'object', additionalProperties: false,
  required: ['cross_season_cells', 'stable_patterns', 'month_specific_patterns', 'recommendation'],
  properties: {
    cross_season_cells: { type: 'array', items: { type: 'object', additionalProperties: true } },
    stable_patterns: { type: 'array', items: { type: 'object', additionalProperties: false,
      required: ['id', 'claim', 'months_supporting', 'commodity'],
      properties: { id: { type: 'string' }, claim: { type: 'string' },
        months_supporting: { type: 'array', items: { type: 'string' } }, commodity: { type: 'string' } } } },
    month_specific_patterns: { type: 'array', items: { type: 'string' } },
    recommendation: { type: 'string', description: 'what the cross-season intraday bucket table should key on, per commodity' },
  },
}

const VERDICT_SCHEMA = {
  type: 'object', additionalProperties: false,
  required: ['id', 'holds', 'months_confirmed', 'verdict'],
  properties: { id: { type: 'string' }, holds: { type: 'boolean' },
    months_confirmed: { type: 'array', items: { type: 'string' } },
    verdict: { type: 'string', description: 'stable / month-specific / refuted, with the evidence' } },
}

const DISCIPLINE = `DISCIPLINE (non-negotiable): per-cell distributions never a pooled mean; $/contract never bps;
leakage-safe (cell features are pre/at-entry, path is forward); honest tiny-n; ANTI-LOCK-IN — a pattern in
ONE month is a per-regime observation, NOT a global rule. Do not modify any repo file; scratch only.`

function charPrompt(it) {
  return `You characterize the ${it.root} continuous NYMEX tape for the single month ${it.month}, BLIND to every
other month (anti-lock-in: this month is its own regime). Run the validated per-month tool and interpret it:
  python research/kalshi/month_characterize.py --root ${it.root} --month ${it.month} --cont-dir data/nymex_analog --out ${SCRATCH}/char_${it.root}_${it.month}.json
(--cont-dir data/nymex_analog is the RESTORE dir, separate from the live year-pull scratch data/nymex_cont.)
Read that JSON. It gives all sustained intraday moves this month, per intraday cell (tod x dir x book),
with peak_usd distribution, fast_capture (front-loaded fraction), sustain_s, continuation rate, and the
curve/temp regime mix. Interpret THIS month per ${it.root}: the curve-shape distribution (front-loaded vs
slow-bleed, magnitude scale), and which pieces (book imbalance support/oppose, coiled volume, curve regime,
temp regime, time-of-day) aligned with magnitude / shape / continuation THIS month, with rough strength and
n. Be honest about tiny-n and degeneracy. If the tape for ${it.month} is not restored locally the tool
returns NO_DATA — report that. ${DISCIPLINE} Return the structured per-month finding.`
}

function synthPrompt(findings) {
  return `You are the SYNTHESIS stage. Here are the independent per-(commodity,month) characterizations:
${JSON.stringify(findings, null, 1)}
Accumulate them into a CROSS-SEASON intraday picture PER COMMODITY. Critically (anti-lock-in, Greg S88):
separate patterns that are STABLE ACROSS MONTHS from patterns that appear in only one/few months. A pattern
is "stable" only if it recurs across multiple months of a comparable regime; keep month-specific patterns as
their own cells, never pool a June pattern onto a January day. Never pool CL and NG. Give each stable pattern
an id, the claim, the commodity, and the months supporting it. ${DISCIPLINE} Return the structured synthesis.`
}

function verifyPrompt(pat, findings) {
  return `Adversarially test this claimed-STABLE pattern. Default to skepticism — try to REFUTE it.
PATTERN ${pat.id} (${pat.commodity}): ${pat.claim}
Claimed supporting months: ${JSON.stringify(pat.months_supporting)}
Evidence (per-month findings): ${JSON.stringify(findings, null, 1)}
Does it actually hold across those months, or is it one-month-only / tiny-n / regime-confounded? A pattern
that only shows in one month is NOT stable (anti-lock-in). Report holds=true ONLY if it recurs across
multiple months with real n. ${DISCIPLINE} Return the verdict.`
}

// -------------------------------------------------------------------------------------------------------
const ITEMS = (args && args.items) || []
if (!ITEMS.length) {
  log('No items passed. Pass args.items = [{root,month},...] for months restored under data/nymex_cont/.')
  return { status: 'NO_ITEMS', note: 'staged workflow; pass (root,month) pairs whose tape is restored.' }
}

phase('Characterize')
const perMonth = (await parallel(ITEMS.map(it => () =>
  agent(charPrompt(it), { schema: MONTH_SCHEMA, label: `char:${it.root}-${it.month}`, phase: 'Characterize' })
))).filter(Boolean)

log(`characterized ${perMonth.length}/${ITEMS.length} (commodity,month) pairs`)
if (!perMonth.length) return { status: 'NO_DATA', note: 'no month had restored tape.' }

phase('Synthesize')
const synthesis = await agent(synthPrompt(perMonth), { schema: SYNTH_SCHEMA, phase: 'Synthesize' })

phase('Verify')
const verified = (await parallel((synthesis.stable_patterns || []).map(pat => () =>
  agent(verifyPrompt(pat, perMonth), { schema: VERDICT_SCHEMA, label: `verify:${pat.id}`, phase: 'Verify' })
))).filter(Boolean)

const confirmed = verified.filter(v => v.holds)
log(`stable patterns: ${confirmed.length}/${verified.length} survived adversarial cross-month verify`)
return { perMonth, synthesis, verified, confirmed_stable: confirmed }
