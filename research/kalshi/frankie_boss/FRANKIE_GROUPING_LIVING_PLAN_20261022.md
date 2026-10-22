# Frankie Grouping Living Plan

Decision record and handoff for Greg Davis | Started October 21 2026 | Updated October 22 2026

This document records decisions as we make them, preserves open questions and separates planning
rules from implemented changes. We are proceeding one step at a time. All material below belongs
under Entry 1; no later decision has been opened.

---

## Entry 1: Rebuild grouping from actual market meaning

**Status:** Agreed planning rule. Source changes, catalog changes, deployment and live group
removal have not been performed.

**Current order of work:** Exclude groups formed solely by equality to a literal identifier first.
Then sort the remaining groups into broad related buckets. This supersedes the earlier suggestion
to retain every group until after bucketing. No other discard or merge decision has been made.

**Preservation clarification from Greg:** Break up the ID-based calculation grouping, not the
underlying data. Keep every ID on its original records with all associated information, events,
attributes and relationships. Preserve the links needed to reconstruct histories. Nothing in this
decision deletes IDs, their associated information or the evidence they designate.

**Future use explicitly preserved:** Greg may later group the ACTUAL ORDERS carrying those IDs
with their associated member. Keep each order record and all recorded side, price, quantity,
changes, fills, cancellations, sequence, timing and lifecycle information, together with the member
and event links. This is not a list of numbers. Dissolving automatic ID-equality calculation groups
does not forbid purposeful organization of actual orders and their behavior. The ID locates the
order; the order and its history supply the information.

Greg wants the existing calculation-group scheme broken apart conceptually and reviewed from its
definitions before a replacement is chosen. Roughly 1.5 million planned groups are not an accepted
research requirement. No existing grouping is presumed valid simply because it was built. This does
not establish that every group is wrong or authorize deleting live work.

---

### 1A: An ID is only a reference

An ID only designates an event, entity, person or place. Its value supplies no behavioral meaning.
A group whose only condition is order_id = 284746, or another literal identity match, is excluded
from the revised calculation-group plan immediately. It does not go into a pending usefulness test.
The raw ID remains available to link the underlying records. This is a semantic rule about
identifiers; it does not exclude prices, quantities, durations or counts merely because they are
numbers.

Some identity-linked data may remain grouped as behavior histories. Member-specific data may help
reveal a pattern without becoming an equation. This refines the earlier blanket ungrouping wording:
remove automatic calculation eligibility while preserving useful organization. Which categories
should remain organized is open.

---

### 1B: Classify the meaning before retaining a group

The 17 field categories inventoried below require semantic classification. The rule covers true
identities stored as text, numbers, keys or lists. A field name alone cannot establish whether its
contents are an ID or a description of actual behavior.

An identity alias must not keep equation work eligible. If the same selection also has an
independently valid market condition, retain that separate justification explicitly.

Names and descriptions used only to identify or explain an object are covered. A text code
describing actual side, action or market state requires its own semantic classification; text
format alone does not make a field an identity.

---

### 1C: Preserve evidence and useful behavior histories

Keep original observations, quantities, prices, events, histories and source links. An ID may
connect one recorded member or entity across its actual actions, sizes, price changes and
responses, so its behavior can be examined. It may also bind evidence and preserve instrument
boundaries. This does not automatically authorize equations for every ID. The meaning and
persistence of member_id must be established before calling it a trader or participant identity.

---

### 1D: Implementation remains separate

Zero application-code changes and no production regrouping remain the instruction. Greg
subsequently explicitly ordered all three AWS boxes stopped; that action is complete. Keep them
stopped until he authorizes restarting. When implementation is addressed, the old identity
grouping must not reappear through saved plans, reused catalogs or downstream results. Exact
affected selection and job counts are still unmeasured.

---

## Entry 1: Field categories 1 through 9

These nine field categories came from source rules. The next section adds eight catalog categories.
These are schema roles, not market family definitions. Earlier discussion called all 17 identity
categories; that was too broad. Some fields contain behavior codes rather than arbitrary
identities. Preserve this correction and classify meaning before implementation.

| No | Identity category | Specific fields and examples |
|----|-------------------|-----------------------------|
| 1 | Order identities | order_id; order_ids; causing_order_ids; filled_order_ids; cancelled_fill_order_ids; modified_fill_order_ids; same_id_cancel_modify_order_ids; unresolved_fill_order_ids |
| 2 | Instrument and contract identities | instrument_id; symbol; raw_symbol; contract |
| 3 | Feed identities | publisher_id; channel_id |
| 4 | Member identities | member_id |
| 5 | Session identities | session_id |
| 6 | Run and request identities | run_id; request_id |
| 7 | Source identities | source_day; source_role; source_dbn_object |
| 8 | Processing references | cursor; input_cursor; input_index; input_record_indices; input_ordinal; ordinal; group_ordinal; group_index; source_member_index; legacy_row_ordinal |
| 9 | Fingerprints | hash; sha256; digest; fields ending in _hash or _sha256 |

Other source-recognized order-reference spellings include fill_order_ids, matched_order_ids,
unresolved_order_ids and any field ending in _order_ids. They belong to family 1 even when a
spelling does not appear in the current catalog.

The source also names request, run and processing references that are already filtered. Existing
exclusion is retained; the correction is to prevent identities being admitted as condition cells.
Session, source and instrument references remain usable for lawful data association and scope.

---

## Entry 1: Field categories 10 through 17

| No | Field category | Specific fields found in the catalog |
|----|----------------|--------------------------------------|
| 10 | Runway identities | runway_id |
| 11 | Family labels and references | family_id; birth_family_id; exit_family_id; candidate_family_id. The verified candidate-family label hashes a structural descriptor; it is not an arbitrary order identity. |
| 12 | Candidate identities | candidate_id |
| 13 | Structure identities | structure_id |
| 14 | Level event identities | level_event_key; level_event_key_at_exit |
| 15 | Mirror pattern keys | mirror_pair_key describes a side string and its A/B-swapped version. Observed example AAAN\|BBBN. Keep orientation separate. |
| 16 | Lineage references and recurrence codes | node_id and parent_id can refer to an order. Recurrence node, from_node and to_node encode action\|side, such as A\|A or C\|B. These are different meanings. |
| 17 | Episode attribution identities | attributed_to_episode_ids |

Keep actual behavior, geometry, event order and market properties. Retain useful linked histories.
Arbitrary identity values carry no pattern information; a verified behavior code can describe
measured conditions even if its field is called a key or node. None of these field names alone
authorizes exclusion or equation work.

**What the inventory establishes:** A completed read-only scan found 52,015,304 field/value labels
across 659,266 positional columns and 137 leaf-field names. Fourteen listed categories have
explicit fields in this catalog. Run/request references, processing references and hashes are
source-defined; no explicit matching leaf was found in this scan.

An initial field-name tally covered 51,722,237 labels, but it includes the mixed behavior-code
categories above. It must not be reported as a verified count of bad ID groups or removable
calculations. Order-reference fields alone account for 49,710,775 labels. Labels, distinct
selections, remaining jobs and comparisons are different units.

This scan inventories declared field names. Generic fields such as value, encoded references and
identities embedded in other labels require semantic tracing before completeness can be claimed.
That tracing determines whether a field is an identity; it does not reopen the decision that
identities are excluded.

**Evidence of the current rule defect:** The inspected Search source marks selected IDs and
calendar fields as context_only. It removes numeric IDs from transformed numeric signals but
retains their categorical values as condition cells. Preventing an ID from becoming a numeric
signal has therefore not prevented it from creating groups.

---

## Entry 1: Carry-forward questions

These requests remain recorded for later discussion. They are not additional approved changes, and
we are not moving past Entry 1 by listing them.

- Show exactly how an actual market condition forms a group: the field, value, full meaning,
  matching observations, nonmatching observations and why membership changes.
- Trace actual additions, modifications, cancellations, executions and book changes. Explain
  conditions concretely; timestamps, IDs and the word pattern are insufficient.
- Show how groups overlap, contain one another or occur in sequence. Distinguish co-occurrence,
  precedence, conditional relationships and causation.
- Identify the exact three things Greg meant before selecting a three-way interaction analysis.
  Their names remain unresolved; the selling, replenishment and price example was illustrative.
- Explain every calculation inside a selected context and whether it answers the intended question.
  A small number of inspected examples has not been chosen as a production limit.
- Decide whether granularity serves the research question only after seeing evidence. No arbitrary
  cap, raw-data removal, rarity penalty, averaging, smoothing or normalization is approved.
- Review calendar labels separately: Friday, holidays, dates and time changes are not market
  conditions. Retain the distinction between contextual organization and the actual behavior
  associated with it.
- Inventory other nonmarket descriptions, bookkeeping, clocks, diagnostic states and configuration
  text separately. A broader exclusion list and exact affected group counts remain open.
- Decide which identity categories should retain linked behavior histories and how those patterns
  will be inspected or recognized. Greg specifically raised member data; no behavior recognition
  algorithm or new computation has been chosen.
- Preserve all 30-day ingestion data, checkpoints and live calculations. Do not use BuildMap,
  duplicate downstream ownership or start the 30-day run from this planning discussion.

---

## Entry 1: Saved evidence for the next handoff

Historical catalog snapshot: 52,015,304 labels; 3,234,263 distinct selections; earlier assembly
plan 1,594,767 planned calculation groups. These are different units. The assembly figure is not
a current remaining workload or a count of independent market questions.

**Five earlier observed selections:**

| Selection | Observations | Saved condition |
|-----------|-------------|-----------------|
| 2290912 | 68 | Entry 2 order slot 1222 has order ID 788702063179. |
| 1696104 | 162 | Entry 18 order slot 870 has side B. This is a side condition and is not automatically excluded as an ID. |
| 2676690 | 16 | Two ask-order identity tests share the same selection: order 788703152180 at level slot 1 position 2, and order 788703152160 at level slot 4 position 13, within entry 4. |
| 2697382 | 338 | Entry 4 ask-level slot 121 first order has ID 788700657035. |
| 2021045 | 19 | Entry 2 bid-level slot 1 positions 8 and 9 contain orders 788701538298 and 788701538307. The two tests share a selection. |

Storage positions above are one-based translations of the source paths. They do not establish
exchange queue priority or best-price ordering. The original handoff retains the full paths. This
five-selection sample does not establish proportions or scientific usefulness.

**Current calculation mechanics retained as background:**
Saved scalar leaves include nested list positions. Exact field/value equality creates selections;
identical position lists share arithmetic while labels remain. An identical selection is not an
intentional conjunction of its labels. The first axis value is omitted for step alignment.

The five transformations are step direction, continuation/reversal, magnitude relative to an
earlier-change median, running-median crossing and acceleration. Transformations use the original
axis before selecting positions. Comparisons use offsets -20 through +20 selected observations,
same/opposite movement and circular-shift controls. Selected-step offsets are not fixed seconds.
Early fitting on original numeric values is a separate operation.

**Source and continuation references:**
Supporting handoff: FRANKIE_GROUP_FORMATION_INTERACTIONS_HANDOFF_20261021.md. Its technical
references remain background; Entry 1 supersedes its previous identity-group eligibility.

Read-only source inspected on October 21 2026:
/opt/frankie-box/work/source-assembly-fitting-20261021, HEAD
58fa3cf904a0c043d8b7930633da08312350cf5a. Modules: deploy/aws/box/frankie_box_experiment_search.py
and frankie_box_search_catalog.py.

Catalog: /opt/frankie-box/work/experiment-search/20231018/cycle-00/discovery.partial/recovery/indexed-v1/cells.sqlite.
Host i-035994afa8bdf66a5 in us-east-1. Recheck source HEAD before future implementation;
preserve newer work.

---

## Entry 1: Behavior definitions and predictor questions

Greg clarified that letter-coded market behavior can be important without becoming an equation.
The task is to ask what conditions produce a sequence such as AAAB, whether earlier conditions
predict it and what follows. Preserve distinct meanings and orientations rather than treating a
shared code as economic equivalence.

**Mirror pairs describe side sequences:** The pinned producer concatenates each raw message side
in order. A is the ask side and B is the bid side. It builds the mirror by swapping A with B;
N and other characters pass through unchanged. It sorts the original and mirrored strings and
joins them with a separator to form mirror_pair_key. Orientation records which half the original
occupies.

Illustration: AAAB means three ask-side messages followed by one bid-side message. Its mirror is
BBBA. The pair key is AAAB|BBBA. This says nothing by itself about whether the messages add,
cancel, modify or trade, their quantities, their price levels, or the surrounding book. It also
does not establish that both halves occurred or that they have equal effects.

Actual catalog examples include AAAN|BBBN and AAAAAAA|BBBBBBB. These are observed code values.
No predictive relationship has been established from their presence, and saved matching-observation
counts are not counts of independent trades.

**Recurrence nodes describe an action and side:** The producer constructs each recurrence node as
action|side, in original message order. A|A means an add on the ask side; C|B means a cancel on
the bid side. The two letter positions use different vocabularies: the first is action and the
second is side. node_id and parent_id in lineage records instead name particular instances. These
fields must not be collapsed into one ID category.

**Structural family labels point to defined descriptors:** candidate_family_id is ow- followed by
a hash of a structural descriptor. That descriptor includes the action sequence, side sequence,
action and side counts, terminal action and side, component count, distinct-price count,
distinct-order count and fill-disposition counts. Exact order numbers are not the descriptor. The
label identifies the descriptor; its characters have no numerical meaning.

Quantity, actual price values and the surrounding book are not included in that descriptor. Price
minimum, maximum and span are retained separately. Two groups in one structural family may
therefore have different quantities, price locations and market contexts. Structural similarity
must not silently become an assumption of equivalent market conditions.

**Research questions retained for the rebuild:**
- Which actual conditions precede AAAB, and how do they differ from conditions preceding BBBA or
  other sequences? Define the target and the comparison context explicitly.
- What follows each sequence in price, quantity, replenishment, cancellation, exhaustion and other
  applicable planes? Preserve orientation and original observation order.
- For prediction, use evidence available before the target sequence starts. Predicting completion
  after part of a sequence appears is a different question. Do not use the completed shape as a
  predictor of itself.

Definition sources: /opt/frankie-box/producers at pinned HEAD
2ebb8ce8ef4834545ad99a4ecdff50c18c5b3134; native_mirror.py, native_group_adapters.py,
native_replay_driver.py and a_memory_member_first_recalculation_20260828.py. No new scientific
calculation or recognition algorithm has been authorized.

---

## Entry 1: Keep different kinds of information separate

Greg described the problem as bananas, phone books, movies, houses and people being lumped
together as if they were the same thing. His instruction is that family groups belong in a
collection containing family groups only. This is a requirement about meaning and membership,
not merely a request to rename a mixed collection.

**A collection of families contains family definitions:** Keep each family definition distinct
within that collection. Individual event instances may be linked to a family, and observed market
conditions may describe when it occurs, but neither becomes a family definition merely by sharing
a saved position, label or observation selection. IDs remain references to the relevant records.

AAAB is specifically a side sequence in the verified mirror representation. It can describe part
of a family definition. The current structural family descriptor also includes the action sequence
and other features. Four add messages and four cancel messages can have the same side sequence
while describing different activity. A common side string alone does not establish one complete
family.

**Connections across types must be explicit research questions:** A question such as which market
conditions precede family F connects a condition to a family. It must preserve the two meanings
rather than filing both as interchangeable members of one generic group. Likewise, an event
instance, an order history, a mirror relationship, a recurrence state and a source diagnostic each
need an explicit role before they are used together.

Retain both halves of a mirror and their orientation. AAAB and BBBA may be related shapes; their
quantities, action types, price locations and consequences remain separately observable. No
symmetry, economic equivalence or predictive value follows from the mirror name alone.

**Inspect other places where meaning could be mixed:** Greg suspects this is not the only
location. Carry that concern through the rebuild. Inspect the roles carried by flattened fields,
categorical condition builders, catalog labels, shared observation selections, transformed-series
aliases, native family and mirror representations, and downstream knowledge consumers. Do not
declare those locations correct merely because a previous technical check passed.

An identical observation selection establishes shared membership. An identical transformed vector
establishes an identical arithmetic input. Neither establishes equivalent market meaning. Review
mathematical reuse separately from interpretation: valid exact reuse may retain distinct names,
types, scope and provenance. The rebuild must expose any place where those distinctions are lost.

---

## Entry 1: Current ordering and broad inventory

**Latest instruction from Greg:** Break up obvious literal-ID equality calculation groups first,
before putting remaining material into broad buckets. Keep every ID and all associated information
intact on the original records, including the connections needed for histories. Examples such as
284746 designate records and contribute no market meaning by themselves. Remove only the
calculation-group rule based on sharing that identifier. Production catalog edits remain
unperformed under the zero-code instruction.

**Broad buckets for the remaining inventory:**
These are initial organizational buckets, not merged calculation populations. Keep distinct
subtypes and member definitions visible. Sort what each item describes, using its defining source
rather than just its field name. Record ambiguity explicitly. Do not discard further groups or
combine scientific populations during this sorting step.

| Initial bucket | What belongs here |
|----------------|-------------------|
| Market conditions | Actual book, price, flow, liquidity, pressure, touch and directional states. |
| Events and sequences | Raw action sequences, side sequences, family definitions, mirror shapes, recurrence and transitions. Family definitions remain a distinct collection within this bucket. |
| Entity histories | Linked order, queue, survival, episode and lineage histories. IDs only connect the evidence. |
| Outcomes | Observed responses, completion, restoration and recognition results. Keep later outcomes distinct from earlier predictors. |
| IDs and references | Literal identifier groups are excluded from the calculation plan first. Keep the underlying references for traceability and history. |
| Time and calendar context | Absolute clocks, dates, Friday, holidays, sessions and time changes as contextual labels. Examine measured elapsed behavior separately. |
| Source and process metadata | Provenance, source locators, integrity, availability, method descriptions, formulas, configuration and progress records. |
| Needs definition | Items whose actual meaning or field role has not yet been established. Do not force them into a market category. |

**Accounting required before calling the inventory complete:** Account for every planned group
and all of its original labels. Distinguish excluded identifier groups, assigned remaining groups,
groups with mixed-role aliases and unresolved groups. Reconcile their total to the exact selected
plan. The historical 1,594,767 figure is not a current reconciled count. Field-label counts must
not be substituted for distinct group counts.

**Current access limitation:** All three AWS boxes are stopped at Greg request. Their saved
catalog files cannot currently be read through the helper NFS mounts. Do not restart the boxes
without Greg authorization. Full group-by-group classification is not complete.

---

## Entry 1: Calculation definitions used as a starting reference

The pinned native calculation contract contains 18 calculation areas: 4.0, 4.0b and 4.1 through
4.16. These are a source-grounded starting reference for the requested review of the 18 cycles;
the prior phrase has not been independently resolved as an exact name for this matrix. Treat these
definitions as evidence to inspect, not absolute truth or an automatically approved replacement
taxonomy.

| Area | Subject | What it calculates or records |
|------|---------|-------------------------------|
| 4.0 | Flow and quotes | Completed-second trades, classified buy and sell flow, usable quotes and window direction. |
| 4.0b | Detector coverage | What the detector considered, promoted, rejected or could not judge; exact reasons and parameters. |
| 4.1 | Identity and integrity | Source binding, exact records, counts, closure, continuity and reconstruction controls. |
| 4.2 | Book regime | Full-book snapshots and separately described day-level regime summaries. |
| 4.3 | Event families | Versioned structural definitions and their exact event members. |
| 4.4 | Mirrors and pairing | Side-swapped patterns, orientation, declared pairing rules and matched or unmatched instances. |
| 4.5 | Clocks and formation | Formation gaps, receive and event latency, decision delay and lawful feature availability. |
| 4.6 | Queues and survival | Order histories, volume ahead, age, priority, own fills and terminal or open status. |
| 4.7 | Replenishment | Removal followed by new adds or modifies, restoration, neighboring prices and persistence. |
| 4.8 | Absorption and pressure | Trade, depletion, replacement, withdrawal, surviving depth and price response. |
| 4.9 | Price ladder | Level births and deaths, gaps, occupied geometry and depth migration. |
| 4.10 | Exhaustion | Precursor, birth, transitions, persistence, extension, completion and open paths. |
| 4.11 | Prediction and recognition | Earliest lawful precursor, recognition at birth or later, missed calls and failed states. |
| 4.12 | Dipole | Opposing pressure, signed flow, composition, direction, persistence, reversal and price coupling. |
| 4.13 | Chains and lineages | Roots, successors, depth, parent-child links, delays, termination and open chains. |
| 4.14 | Recurrence | Homogeneous runs, gaps, bursts, alternating sequences and transition edges. |
| 4.15 | Structure discovery | Versioned discovered clusters, splits, merges, unmatched observations and exact exemplars. |
| 4.16 | Future responses | Later price, flow, book, queue, survival and completion trajectories at stated horizons. |

Source: DavisAI1974/Markets,
research/kalshi/agents/frankie_native_raw_mbo_calculation_contract_20260828.md, section 4,
pinned producer 2ebb8ce8. No new averaging is approved. The 99-layer crosswalk names producers
and carriers; it does not establish completed group classification.

---

## Entry 1: Saved task plan and source records

**Latest clarification on October 21 2026:** The machine-readable group definitions and work
records already exist on AWS. We have not exported them into a complete readable inventory. The
missing export must not be described as an absence of saved group records.

**The saved task plan reference:** The earlier
FRANKIE_SEARCH_HANDOFF_20261021_SESSION63 (1).md records this file:

    /opt/frankie-box/work/experiment-search/20231018/cycle-00/discovery.partial/recovery/factored-v2/group-tasks-finite-2-6.sqlite

That checkpoint records 1,594,763 tasks under FRANKIE_COMPLETE_TERNARY_2_6_V1, split as
main 797,382 and helper 797,381. The later assembly figure is 1,594,767; reconcile the
four-count difference and scope. The reference has been found, but the current file contents,
schema and use by the latest assembly have not been verified. Trace the current selected plan and
its group links into indexed-v1/cells.sqlite, which holds the conditions and membership.

**Where the grouping values originate:**
1. Market-by-order data supplies additions, cancellations, modifications and executions.
2. Frankie producers reconstruct the book and calculate queues, families, mirrors and recurrence.
3. Saved observations carry results alongside nested journal entries, orders and price levels.
4. Search flattens nested records into scalar fields, with separate paths for each stored list
   position.
5. Eligible field/value combinations become grouping conditions; matching positions define
   selections. Saved catalogs and task plans retain them.

Greg identified this chain as another useful place to filter by. Review source stages and
producers as classification dimensions and examine where grouping eligibility should be filtered.
This is a planning direction, not approval to discard source records or remove producers. Preserve
the already agreed literal-ID rule and all associated order information.

A verified example is journal.group.entries[1].payload.observation.orders[1221].order_id =
"788702063179": the 1,222nd stored order in the second journal entry has that identifier. Another
condition tests side B at the 870th order in the 18th entry. This automatic field/value grouping
does not establish that the selected observations share a meaningful market condition. Trace the
exact source product, producer and meaning of each field; complete source-plane coverage has not
yet been established.

**Stopped boxes and the next session:**
All three boxes are verified stopped: main i-035994afa8bdf66a5, helper i-0d17573dbce871520 and
calculation box i-031eeb577ad72b064. The helper and calculation box required forced stops after
normal shutdowns stalled. Their attached disks were retained; no claim that all in-flight work
checkpointed is established. KeepRunning is false on all three. AWS has been reconnected and all
three were again confirmed stopped. Do not restart until Greg authorizes it.

The next assistant, Codex or Claude, owns locating and extracting the current saved plan, tracing
condition provenance and producing the actual group inventory. The eight buckets are still
proposals. Continue read-only discovery while the boxes remain stopped; no usable archive copy
of the plan or cells catalog has been established. Then apply the ID-grouping rule without
deleting IDs, actual orders or associated information, and organize the remaining groups for Greg
to inspect.

---

## Entry 1: Set-aside triage — October 22 2026

**Date:** October 22 2026  
**Scope:** Paper-level classification of which group categories can be set aside without
individual inspection. No catalog edits. No box access. No implementation.  
**Authority:** Extension of the ID-exclusion rule Greg established. Groups set aside here carry
no market behavioral information by definition of their field categories.

### What "set aside" means here

A group is set aside if ALL of its defining conditions come from fields in the set-aside classes
below. Setting aside means: excluded from the calculation-group plan, moved to the "IDs and
references" bucket, underlying records preserved intact. This is not deletion.

A group is kept for sorting if ANY condition comes from a field outside these classes — even if
other conditions are from set-aside fields.

### Six set-aside field classes

| Class | Fields | Why |
|-------|--------|-----|
| Literal IDs | order_id, order_ids, causing_order_ids, filled_order_ids, cancelled_fill_order_ids, modified_fill_order_ids, same_id_cancel_modify_order_ids, unresolved_fill_order_ids, fill_order_ids, matched_order_ids, unresolved_order_ids; member_id; candidate_id; structure_id; runway_id; attributed_to_episode_ids; node_id, parent_id (when used as order or instance references) | Reference only. The value designates a record; it carries no behavioral content. Established by Greg's 1A rule. |
| Storage positions | cursor; input_cursor; input_index; input_record_indices; input_ordinal; ordinal; group_ordinal; group_index; source_member_index; legacy_row_ordinal | Where a record sits in a stored list is a storage artifact, not a market condition. "The 870th stored order in journal entry 18" is not a market description. |
| Infrastructure | publisher_id; channel_id; session_id; run_id; request_id | Technical pipeline identifiers. Describe how data was delivered, not what the market did. |
| Integrity | hash; sha256; digest; any field ending in _hash or _sha256 | Data validation records. Not observations. |
| Pure instrument scope | instrument_id; symbol; raw_symbol | These identify which market we looked at, not a condition within that market. All data in a properly scoped run is already for one instrument. NOTE: `contract` is withheld from this class — it may encode term structure (front-month vs. deferred contract) which is market context. Inspect separately. |
| Pure calendar labels | source_day (when used as a bare date equality condition); source_role; source_dbn_object | Labeling which day or data object the record came from. Not a market behavior condition. Calendar associations (Friday, holiday proximity) are contextual and belong in the time/calendar bucket. |

### Applying to the five inspected selections

All five inspected selections are set aside under these classes:

| Selection | Fields present | Set-aside classes hit | Verdict |
|-----------|----------------|----------------------|---------|
| 2290912 (68 obs): entry 2, slot 1222, order_id 788702063179 | ordinal/position (storage), order_id (literal ID) | Both | SET ASIDE |
| 1696104 (162 obs): entry 18, slot 870, side B | position (storage), side | Storage position. The condition is "the 870th stored order in entry 18 has side B" — not "bid-side activity is present." The positional qualifier makes this a storage artifact test, not a market state test. | SET ASIDE |
| 2676690 (16 obs): level slot 1/4, order_ids 788703152180/152160 | position (storage), order_id (literal ID) | Both | SET ASIDE |
| 2697382 (338 obs): entry 4, ask-level slot 121, order_id 788700657035 | position (storage), order_id (literal ID) | Both | SET ASIDE |
| 2021045 (19 obs): bid-level slot positions 8 and 9, order IDs 788701538298/307 | position (storage), order_id (literal ID) | Both | SET ASIDE |

This five-out-of-five result is consistent with the catalog's label breakdown: 49,710,775 of
52,015,304 labels (95.6%) come from order-reference fields alone. Labels are not groups, but this
ratio makes a large set-aside count probable.

### Three fields withheld from automatic set-aside pending inspection

These fields appear in the 17 categories but require individual inspection before a ruling. Do
not set them aside automatically until their content is verified.

| Field | Category | Reason for withhold |
|-------|----------|---------------------|
| contract | 2 (Instrument and contract identities) | May encode front-month vs. deferred term structure, which is market context. Verify what values appear in the catalog and what they represent. |
| level_event_key, level_event_key_at_exit | 14 (Level event identities) | Named as identities, but "level event" may encode geometric or behavioral content (a price level birth, death, or gap event). Verify the key format before ruling. |
| mirror_pair_key (when value is AAAB\|BBBA or similar) | 15 (Mirror pattern keys) | The key is a side sequence code. AAAB\|BBBA encodes behavioral content (three ask-side messages then one bid-side message). A condition "mirror_pair_key = AAAB\|BBBA" is testing for a real side sequence pattern, not an arbitrary identity. This field is NOT in the set-aside classes. Groups conditioned on mirror_pair_key values go into Events and sequences. |

### Calculation areas mapped to buckets

Using the 18 calculation areas as a starting reference, the expected bucket distribution is:

| Area | Subject | Primary bucket | Notes |
|------|---------|---------------|-------|
| 4.0 | Flow and quotes | Market conditions | Trades, flow classification, quote states |
| 4.0b | Detector coverage | Source and process metadata | What the detector did, not what the market did |
| 4.1 | Identity and integrity | Source and process metadata | Source binding, counts, reconstruction controls |
| 4.2 | Book regime | Market conditions | Book snapshots and regime states |
| 4.3 | Event families | Events and sequences (family definitions) | Keep each family definition distinct |
| 4.4 | Mirrors and pairing | Events and sequences | Side sequences, orientation; keep AAAB and BBBA as separate orientations |
| 4.5 | Clocks and formation | Time and calendar context / Needs definition | Formation gaps and latencies are elapsed-time measurements — different from absolute clock labels. Keep elapsed-time measurements separate from calendar labels. |
| 4.6 | Queues and survival | Entity histories | Order lifecycle, queue state, survival |
| 4.7 | Replenishment | Market conditions | Add/modify after removal; book restoration |
| 4.8 | Absorption and pressure | Market conditions | Trade depletion, depth response |
| 4.9 | Price ladder | Market conditions | Level geometry, occupancy |
| 4.10 | Exhaustion | Events and sequences / Market conditions | Precursor and completion states describe market events; persistence and open paths are conditions |
| 4.11 | Prediction and recognition | Outcomes / Needs definition | Recognition results are outcomes; methodology layer needs inspection before classification |
| 4.12 | Dipole | Market conditions | Flow direction and pressure states |
| 4.13 | Chains and lineages | Entity histories / Events and sequences | Chain structure describes event sequences; node_id and parent_id (as instance references) go to set-aside |
| 4.14 | Recurrence | Events and sequences | Action-side sequences, transitions, runs |
| 4.15 | Structure discovery | Needs definition | Cluster discovery is a methodology layer. The structural descriptors themselves (action sequence, component count) may belong in Events/sequences after verification. |
| 4.16 | Future responses | Outcomes | Later price, flow, book trajectories. Keep later outcomes distinct from earlier predictors. |

### What this does NOT settle

- Exact count of set-aside groups vs. remaining groups. Requires the SQLite.
- Whether elapsed-time fields in 4.5 (formation gaps, latency) are market behavior or process
  metadata. They measure time between events, which could be meaningful. Withhold classification.
- Whether structure_discovery exemplars (4.15) carry behavioral content distinct from the
  discovery methodology. Withhold classification.
- Whether any fields not in the 17 categories carry IDs embedded in other field names. The living
  plan's own note: "Generic fields such as value, encoded references and identities embedded in
  other labels require semantic tracing."
- The four-count reconciliation between 1,594,763 (SQLite checkpoint) and 1,594,767 (assembly
  figure). Requires the SQLite.
- Whether catalog entries added after the historical checkpoint are included in the task plan.

### Schema and triage status — October 22 2026

**Schema confirmed.** The triage Python script ran on the main box on October 22 2026.
Results are saved in `/tmp/codex-sqlite-triage-20261022.json` on i-035994afa8bdf66a5.
The box is now stopped. When it is next available, retrieve that file per the drop-in.

**Critical schema finding:** The tasks table stores only `(ordinal, body, pin)`. No join table
exists. Each body is a pickle of `(ordinal, (selection_id, None))`. SQL JOINs against the
tasks table cannot produce conjunctions. The Python approach is the only correct method. The
original drop-in SQL queries were architecturally wrong; the drop-in has been corrected.

**Two calendar exclusions added:** `trading_day` and `trading_weekday` were correctly identified
by Codex and added to the exclusion set. They are now in the drop-in's set-aside calendar class.

**Partial results seen before output was cut off:**
Top surviving fields by distinct_selections (from the interrupted paste):
- `native.lifecycle.queue[0].level_event_key_at_exit`: 262,119 distinct selections
- `native.lifecycle.replenishment[N].level_event_key` fields: high counts across multiple N values
- `native.lifecycle.absorption[0].family_id`, `native.member.row.family_id`,
  `structures.candidate_family_id`: 763 distinct selections each
The output was cut before the complete field list was captured.

**Interpretation note from triage script (verbatim):** "Task rows reference unique observation
masks; labels on one selection are aliases, not proof of an explicit AND hypothesis."

**What this means for the conjunctions question:** The dominant surviving fields are
level_event_key fields (positional queue identities) and family_id fields (structural family
references). Both are in the categories withheld from automatic set-aside pending inspection
(categories 14 and 11 in the living plan). The question of whether these are behavioral content
or identity-like references is not settled by the field counts alone.

**Next step when the box is available:**
1. Retrieve and paste the full `/tmp/codex-sqlite-triage-20261022.json` output (section 3 of
   the corrected drop-in). This gives the complete surviving field list, task count, and first 20
   surviving tasks with all their conditions.
2. If the file is gone (instance terminated, not stopped), re-run section 4 of the drop-in.
3. After retrieving the output, record here: total surviving tasks, total surviving selections,
   complete field list, and the conjunction patterns from the first 20 tasks.

Do not attempt SQL queries against the tasks table. Do not run any query through the NFS
mount while main is stopped.

---

## How we maintain this document

Update this same document after each substantive discussion. Give each new decision its own entry
number, date, exact scope, rationale, implementation status and remaining dependencies.
Distinguish Greg decisions from assistant suggestions. Correct superseded text visibly and
preserve unresolved requests rather than silently dropping them.

Continue on Entry 1 until Greg chooses the next step. No category becomes acceptable merely
because it already exists in source, has many observations or has saved calculation results.
