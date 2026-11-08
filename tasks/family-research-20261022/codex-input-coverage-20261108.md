# Input coverage and reviewer comparability — November 8, 2026

Snapshot for the current Codex stack pass. CCODE owns the missing-data changes
(user instruction in this chat); Codex does not duplicate that repair or rerun
producers. Recheck this snapshot against CCODE's final saved source manifest.

| Analysis | Actual input coverage | Interpretation |
| --- | --- | --- |
| Initial 375/391 raw-message extract | October 18 UTC member; 2,819 retained messages around the two named cases | Deliberately bounded case extract; not the source for a claim of whole-session order-level coverage |
| 749 family-start tables | Saved October 18 session group export, 583,688 completed groups | 749 retained starts; original four-arm model has 437 common-input rows, with missing cases preserved |
| 980 aggression-to-rest paths | Both October 17 and October 18 UTC members, 771,787 relevant raw records, linked to the saved session export | Later Codex order-path study is not restricted to the October 18 UTC member |
| 863 dipoles and current stack | Same saved October 18 session export and pinned candidate reconstruction | All 863 retained; companion quote-classified flow is distinct from action-time detector operands |
| October 2 and 17 | Previously saved partial-date ROOT/Native arrays; final standalone exports not yet verified | Preserve partial status; do not substitute another date's data or claim fully comparable final inputs |
| October 3 | Final comparable standalone inputs not yet verified by this analysis | Pending application, not a negative research result |

## Exact pins and references

- Raw tape commit: `1d15dc6f1b5bbb1fabb6389d18e8bedba2b77202`.
- Under `data/nymex_mbo/ng_v0_oct2023/`, that commit lists October 2, 3, 17 and
  18 UTC members. It lists neither October 1 nor October 16 in that directory.
  A full October 17 trading session needs its preceding UTC segment; that segment
  is not supplied by merely checking out the named October 17 member. CCODE is
  addressing the missing-data question; this snapshot does not claim that no
  other repository/location can hold the missing source.
- October 17 member blob: `56046c713e2a55ea57d1bac031c87b067fba0ce7`.
- October 18 member blob: `e006625ba9e3f5806fe3a297ea66ab5b4aac9185`.
- Saved group/candidate evidence: `b5f28bd57de5ed4ff889335edb9a33216b67eb6a`.
- Group path: `research/kalshi/adaptive_wavepacket_20261108/markets_bridge/tasks/root-bounded-replay/retained/october18-standalone-inputs/groups.jsonl.gz`.
- The two-member mapping is in `research_atlas.py:raw_records`: October 17 raw
  index minus 841,601; October 18 raw index plus 17,375; retain session cursor >=0.
- See `flow-book-discovery-v1/original-message-source.json`,
  `flow-book-discovery-v1/method.json`, and `research-atlas-v2/mechanism-method.json`.

## Desktop files are on the shared branch

Codex's original work was published in `f0bd88e17`, `fa802b0f2`, `1a67579b5`, and
`5272de5cf31646d2ce7c45bfd0adc8dbecba3d9a`. The shared branch is
`codex/ng-shadow-discovery-20261108`. These include the independent
`codex-flow-book-discovery-20261108.md`, code and tables under
`flow-book-discovery-v1/` and `research-atlas-v2/`, and durable
`codex-research-memory.md`. A stale or sparse checkout can hide files that are
already committed. Inspect the commit/path rather than inferring absence from
the working-directory listing. Neither absence from a checkout nor a missing
local partial-clone blob proves that the remote source never existed.

## Completion is separate from source coverage

At this chat's most recent monitor read, all three Native passes were advancing
and standalone touch/print exports remained queued. The monitor chat is
`01a1bbce-3522-72b2-b759-803546fb687d`, snapshot cursor
`8fe7ebcb-9189-402c-b89e-ce45726f18c9:6`. This is a dated snapshot, not live status.
Both processing steps, preserved outputs, and shutdown verification remain the
completion sequence. A completed job can still have partial source coverage;
a complete source collection does not mean the job finished. Check both.

When CCODE saves the repair, record its exact source revision and coverage before
reusing the same analysis definitions. Keep earlier partial results and identify
which rows/input definitions change; do not silently replace their provenance.
