# NG Exhaustion Exact-D1 Preserve-All Core-Eight Findings — 2026-08-18

Status: **CORE CANONICAL/LINEAGE ANALYSIS COMPLETE LOCALLY AND DURABLE MASTER LEDGER PRESENT; RAW-TAPE DIRECTIONAL/CHOP JOIN REMAINS A SEPARATE LANE. NO D1 DISCARDED. NO PLAY FROZEN. PERMANENT FRANKIE UNCHANGED.**

## Population and chronology

The current exact-D1 population contains **18,837 valid rows** from the frozen OOT lineage plus held insert week:

- D1 discovery/fitting, base weeks 18–35: **8,530**
- later Eras4–5 validation, base weeks 36–47: **5,907**
- untouched historical confirmation, base weeks 48–53: **2,991**
- held `20260329`: **1,409**

Base weeks 0–17 remain `PRELINEAGE_UNLABELED`; no in-sample D1 labels were manufactured.

The preserve-all master ledger is committed under `research/generated/ng_exhaustion_exact_d1_master_20260818/`. Profitability, duration, path shape and support grade D1s but do not define membership.

## 1. Single-link duration is much broader than previously studied

Across all 18,837 D1s:

- median elapsed origin -> descendant: **65 s**
- p90: **138 s**
- p95: **198 s**
- p99: **522.64 s (~8.7 m)**
- maximum: **101,683 s (~28.25 h)**

A train-frozen log-time Gaussian-mixture screen on the 8,530 D1-discovery instances selected five BIC components with approximate centers:

- **45.0 s**
- **63.1 s**
- **109.1 s**
- **217.7 s (~3.6 m)**
- **735.6 s (~12.3 m)** — long family

These are characterization families only, not live duration cutoffs.

Long-family replication counts are:

- discovery: **90**
- Eras4–5: **24**
- untouched confirmation: **11**
- held: **7**

Therefore exact-D1 / one-link chains can be genuinely long-lived. A chain does not need to become D2 to contain a long-duration leg.

## 2. Elapsed duration and causal remaining runway are different

The extreme 101,683-second case is a useful warning: its origin h=60 information wall occurred **102 seconds after** the descendant, so the 28-hour elapsed value is retrospective for execution purposes.

But the ordinary long-family population often retains substantial time after the origin is fully characterized:

| Block | Long D1 n | Median origin-wall -> descendant | Positive remaining rate |
|---|---:|---:|---:|
| D1 discovery | 90 | 887.5 s (~14.8 m) | 92.2% |
| Eras4–5 | 24 | 1,157.5 s (~19.3 m) | 79.2% |
| confirmation | 11 | 644 s (~10.7 m) | 72.7% |
| held | 7 | 832 s (~13.9 m) | 57.1% |

So `long elapsed D1` and `long causally harvestable runway` must remain separate concepts.

## 3. Time length conditions profitability inside the same grammar

The common comparison lens is the descendant's endpoint+5 -> endpoint+60 return, with orientation fixed from D1 discovery and later blocks scored without retuning. This is only one profit lens; it does not measure the origin->descendant leg or chop/rotation economics.

Broad pair modules with the highest repeatable validation means include:

| Pair | Total n | Orientation | Eras4–5 | Confirmation | Held | Combined validation gross | Net after 0.5 tick |
|---|---:|---|---:|---:|---:|---:|---:|
| `SS|F` | 450 | with descendant | +1.198 | +0.684 | +0.878 | **+0.979** | **+0.479** |
| `XS|S` | 331 | with descendant | +1.045 | +0.553 | +0.815 | **+0.864** | **+0.364** |
| `OO|S` | 725 | against descendant | +1.074 | +0.494 | +0.548 | **+0.856** | **+0.356** |
| `OO|F` | 1,072 | against descendant | +0.820 | +0.674 | +1.195 | **+0.843** | **+0.343** |
| `SS|S` | 941 | with descendant | +0.807 | +0.956 | +0.441 | **+0.789** | **+0.289** |

Duration-conditioned examples are materially stronger:

| Pair / duration family | Total n | Approx family center | Combined validation gross | Net 0.5 | Worst validation block gross |
|---|---:|---:|---:|---:|---:|
| `SS|S` / ~218s | 45 | ~3.6m | **+2.158** | **+1.658** | +1.167 |
| `SO|S` / ~218s | 62 | ~3.6m | **+2.143** | **+1.643** | +0.857 |
| `OO|F` / ~218s | 62 | ~3.6m | **+2.053** | **+1.553** | +0.167 |
| `OO|F` / ~109s | 138 | ~1.8m | **+1.745** | **+1.245** | +0.125 |
| `OO|S` / ~218s | 84 | ~3.6m | **+1.679** | **+1.179** | +1.333 |
| `SS|F` / ~63s | 195 | ~1.1m | **+1.593** | **+1.093** | +0.600 |

This is a major structural result: **D1 time length is an economic conditioner, not merely a descriptive timestamp.** It must still not be turned into a realized-duration live filter; causal early identification is a separate problem.

All lower-ranked pair/family cells remain preserved in the master ledger. A weak endpoint+5 -> +60 score does not prove that a D1 is unprofitable under another horizon, origin->descendant capture, or chop/rotation strategy.

## 4. Older causal ancestry sharpens D1 economics

Restoring one older causally available state materially separates some pair outcomes. Examples with at least moderate support:

- `XO|S` with older `S`: n=39, against descendant, combined validation gross **+2.00**, net0.5 **+1.50**, worst block +1.818.
- `PS|S` with older `S`: n=71, with descendant, gross **+1.781**, net0.5 **+1.281**.
- `SS|S` with older `X`: n=44, with descendant, gross **+1.579**, net0.5 **+1.079**.
- `OO|F` with older `O`: n=151, against descendant, gross **+1.231**, net0.5 **+0.731**; every later block remained positive.
- `SO|S` with older `O`: n=163, against descendant, gross **+1.208**, net0.5 **+0.708**.

This extends the Phase-2 `FLAG_AND_DECOMPOSE` lesson: older ancestry can distinguish economically different instances of the same local D1 grammar.

## 5. Pre-long prediction has signal but is not yet stable enough to authorize a long-leg trade

A fixed logistic classifier using only origin-known frozen characteristics was trained on the D1-discovery block to identify membership in the rare long-D1 family. Discovery contained 90 long D1s among 71,772 origins.

Later performance:

| Block | Long positives | AUC | Top-decile lift over base rate |
|---|---:|---:|---:|
| Eras4–5 | 24 | **0.806** | **4.17x** |
| confirmation | 11 | **0.613** | **1.82x** |
| held | 7 | **0.843** | **4.28x** |

This says origin state contains some information about future long-D1 membership, but confirmation degradation and the rarity of the target prevent a live long-duration rule from being claimed here.

## 6. Long-family grammar is heterogeneous

The 132 long-family D1s are distributed across many pair grammars rather than one dominant path. Higher-count long cells include `SS|S` (16), `SS|F` (15), `OS|F` (13), `OO|S` (13), `OO|F` (12), and `SO|S` (12). Rare long cells are retained rather than discarded.

Some long cells look attractive under the descendant reference lens (`OS|F`, `SO|S`, `OO|S`), while others do not under that particular lens. That is not a membership decision. Raw origin->descendant path economics and chop/rotation treatment remain necessary before describing the full profit route for each long D1.

## 7. Re-origin remains separate from inherited D1 lifespan

The descendant's own future lineage is treated as a new origin checkpoint, not inherited extension of the original D1. This preserves the Phase-2 rolling/re-origin doctrine.

The rare long family shows an investigator-worthy held difference: pre-held long-family instances had zero positive descendant child-depth in this particular frozen lineage measure, while held had 3/7. Sample is tiny; preserve and decompose rather than generalize or delete.

## Current interpretation

1. Exact D1 is a first-class exhaustion population, not a failed D2 population.
2. Every D1 remains in the research ledger.
3. D1 duration is strongly multi-scale, including a genuine long tail.
4. Long elapsed time must be separated from causal remaining runway.
5. Duration materially conditions economic behavior within local grammar.
6. Older ancestry further separates D1 profitability.
7. The common descendant +5 -> +60 reference lens ranks D1s but does not define whether a D1 can be profitably monetized.
8. Raw directional-vs-chop path reconstruction remains required to complete origin->descendant monetization analysis.
9. No new play is frozen and no permanent brain merge is performed.
