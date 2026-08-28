# A-clean RT Native-MBO Positive Mechanically Derived Findings

## Artifact identity

This document records positive findings mechanically derived in a read-only post-freeze analysis of the intact A-clean native-MBO evidence ledger. Its authorship classification is `POST_FREEZE_NATIVE_EVIDENCE_DERIVATION`; the locked RT launcher output retains its separate first-lock identity.

The event group is the unit of analysis. Counts remain separated by source day, and every cited group is closed by F_LAST on the `ts_recv_ns` causal clock.

## Evidence coverage

| Source | Role | Native records | F_LAST-closed groups |
|---|---|---:|---:|
| `glbx-mdp3-20211004.mbo.dbn.zst` | `HELD_OUT_BLIND` | 1,994,358 | 1,506,255 |
| `glbx-mdp3-20211005.mbo.dbn.zst` | `HELD_OUT_BLIND` | 2,111,930 | 1,588,041 |

## Mechanically distinct event-group families

### 1. Single-fill/cancel lifecycle: `TFCN`

| Property | October 4 | October 5 |
|---|---:|---:|
| Groups | 38,510 | 39,766 |
| All actions at one price | 38,490 | 39,752 |
| Trade size equals fill size | 38,107 | 39,389 |
| Fill order ID followed by cancel of the same ID | 38,510 / 38,510 | 39,766 / 39,766 |
| Trade size 1 | 35,364 | 36,388 |

The exact side-sequence partition is:

| Side sequence | Action-side structure | October 4 | October 5 |
|---|---|---:|---:|
| `ABBN` | trade ask, fill bid, cancel bid, neutral close | 17,750 | 18,344 |
| `BAAN` | trade bid, fill ask, cancel ask, neutral close | 17,197 | 18,233 |
| `NNBN` | neutral trade, neutral fill, cancel bid, neutral close | 2,058 | 1,815 |
| `NNAN` | neutral trade, neutral fill, cancel ask, neutral close | 1,485 | 1,360 |
| `BBBN` | trade bid, fill bid, cancel bid, neutral close | 12 | 7 |
| `AAAN` | trade ask, fill ask, cancel ask, neutral close | 8 | 7 |

Exemplar group `1162308`, `2021-10-04T00:00:00.006001Z`:

1. `T(A, size=1, price=5.729, order=786260856050)`
2. `F(B, size=1, price=5.729, order=786260855382)`
3. `C(B, size=1, price=5.729, order=786260855382)`
4. `N(N, size=0)` with F_LAST

The fill and cancel share order ID `786260855382`. The group closed 92,797 ns after its first received component.

### 2. Two-order fill/cancel cascade: `TFFCCN`

| Property | October 4 | October 5 |
|---|---:|---:|
| Groups | 7,037 | 7,522 |
| All actions at one price | 6,554 | 7,132 |
| Trade size equals combined fill size | 6,361 | 6,955 |
| Fill IDs followed by matching cancel IDs | 14,074 / 14,074 | 15,044 / 15,044 |
| Trade size 2 | 5,464 | 5,986 |

Principal mirrored side structures:

| Side sequence | October 4 | October 5 |
|---|---:|---:|
| `BAAAAN` | 3,030 | 3,226 |
| `ABBBBN` | 3,022 | 3,403 |

Exemplar group `1162432`, `2021-10-04T00:00:51.123731Z`:

1. `T(B, size=2, price=5.734)`
2. `F(A, size=1, price=5.734, order=786260852588)`
3. `F(A, size=1, price=5.734, order=786260856527)`
4. `C(A, size=1, price=5.734, order=786260852588)`
5. `C(A, size=1, price=5.734, order=786260856527)`
6. `N` with F_LAST

The two fill IDs map exactly to the two subsequent cancel IDs. The group closed 53,384 ns after its first received component.

October 5 group `2668702`, `2021-10-05T00:01:01.120321Z`, contains a size-three bid trade split across ask fills of one and two. Each fill is followed by a cancel carrying the same order ID. The group closed 70,773 ns after its first received component.

### 3. Repeated trade/fill cascade: `TFTFCCN`

| Property | October 4 | October 5 |
|---|---:|---:|
| Groups | 819 | 832 |
| Fill IDs followed by matching cancel IDs | 1,638 / 1,638 | 1,664 / 1,664 |
| All actions at one price | 142 | 162 |
| Combined trade size equals combined fill size | 776 | 804 |
| Combined trade size 2 | 701 | 724 |

Principal mirrored side structures:

| Side sequence | October 4 | October 5 |
|---|---:|---:|
| `BABAAAN` | 358 | 340 |
| `ABABBBN` | 352 | 349 |

Exemplar group `1162484`, `2021-10-04T00:01:33.706447Z`, contains two ordered `T→F` pairs at 5.736, followed by cancels of both filled ask order IDs and neutral F_LAST close.

### 4. Fill-followed-modify lifecycle: `TFM`

| Property | October 4 | October 5 |
|---|---:|---:|
| Groups | 6,173 | 6,605 |
| All actions at one price | 6,173 | 6,605 |
| Trade size equals fill size | 6,168 | 6,603 |
| Fill order ID followed by modify of the same ID | 6,173 / 6,173 | 6,605 / 6,605 |
| Trade size 1 | 4,583 | 4,897 |

Exact side-sequence partition:

| Side sequence | Action-side structure | October 4 | October 5 |
|---|---|---:|---:|
| `BAA` | trade bid, fill ask, modify ask | 2,878 | 2,707 |
| `ABB` | trade ask, fill bid, modify bid | 2,567 | 3,310 |
| `NNB` | neutral trade, neutral fill, modify bid | 413 | 304 |
| `NNA` | neutral trade, neutral fill, modify ask | 315 | 284 |

Exemplar group `1162859`, `2021-10-04T00:03:20.924830Z`:

1. `T(A, size=1, price=5.741)`
2. `F(B, size=1, price=5.741, order=786260796228)`
3. `M(B, size=2, price=5.741, order=786260796228)` with F_LAST

The fill and modification share order ID `786260796228`. The group closed 41,768 ns after its first received component.

October 5 group `2669906`, `2021-10-05T00:02:31.506639Z`, carries the mirrored `ABB` structure at 5.842 and closes 45,709 ns after its first received component.

### 5. Fill-followed-modify with neutral close: `TFMN`

| Property | October 4 | October 5 |
|---|---:|---:|
| Groups | 1,910 | 1,833 |
| All actions at one price | 1,910 | 1,833 |
| Trade size equals fill size | 1,901 | 1,824 |
| Fill order ID followed by modify of the same ID | 1,910 / 1,910 | 1,833 / 1,833 |

Exact side-sequence partition:

| Side sequence | October 4 | October 5 |
|---|---:|---:|
| `BAAN` | 908 | 763 |
| `ABBN` | 669 | 803 |
| `NNBN` | 180 | 145 |
| `NNAN` | 149 | 114 |
| `BBBN` | 4 | 8 |

October 4 exemplar group `1166161`, `2021-10-04T00:07:51.633499Z`, contains `T(B,2)` → `F(A,2)` → `M(A,1)` on order `786260864394`, followed by neutral F_LAST close.

### 6. Trade-plus-neutral-close family: `TN`

| Property | October 4 | October 5 |
|---|---:|---:|
| Groups | 1,901 | 2,204 |
| Bid-side trade followed by neutral close | 1,032 | 1,148 |
| Ask-side trade followed by neutral close | 869 | 1,056 |
| Trade size 1 | 1,465 | 1,713 |

October 4 exemplar group `1164696`, `2021-10-04T00:06:18.302882Z`, contains `T(A, size=1, price=5.759)` followed by neutral F_LAST close.

October 5 exemplar group `2674145`, `2021-10-05T00:22:45.139786Z`, contains `T(A, size=1, price=5.850)` followed by neutral F_LAST close.

### 7. Elementary queue-mutation families

| Ordered family | October 4 | October 5 |
|---|---:|---:|
| `A` | 590,918 | 615,022 |
| `AN` | 97,879 | 105,958 |
| `C` | 516,259 | 534,916 |
| `CN` | 66,469 | 71,149 |
| `M` | 145,701 | 166,389 |
| `MN` | 12,315 | 13,980 |

Concrete October 4 exemplars:

- Group `1162309`, `2021-10-04T00:00:00.006422Z`: bid add of one at 5.728.
- Group `1162310`, `2021-10-04T00:00:00.007783Z`: bid cancel of two at 5.700.
- Group `1162340`, `2021-10-04T00:00:03.890121Z`: ask add of one at 5.731 followed by neutral close.
- Group `1162346`, `2021-10-04T00:00:03.906649Z`: ask modification to size five at 5.751.
- Group `1162347`, `2021-10-04T00:00:03.908728Z`: ask cancel of one at 5.731 followed by neutral close.

### 8. Session-boundary withdrawal families

| Group | Receive time | Ordered structure | Bid cancels | Ask cancels | Cancellation-message size |
|---:|---|---|---:|---:|---:|
| `2654677` | `2021-10-04T21:00:00.237256Z` | 430 `C` actions followed by `N` | 219 | 211 | 796 |
| `4237483` | `2021-10-05T21:00:00.228110Z` | 581 `C` actions followed by `N` | 371 | 210 | 1,179 |

Both families occur at the exact 21:00 UTC session boundary and remove resting orders across many prices and order identities before neutral F_LAST close.

## Provenance

- Artifact classification: `POST_FREEZE_NATIVE_EVIDENCE_DERIVATION`
- Source run: `frankie-a-clean-rt-33161766927-1`
- Source packet: `aclean-rtpkt-be26a48cef30ad9abe9e`
- Source manifest: `a98a454ef5a88d6f3ee1213370d6df530ab2946ec9cde47171b0d7aa19f4e2ba`
- Evidence ledger SHA-256: `b7399305906936fb89c5028fe2f32e291aefc2f9be14e421e6afc14b27acd038`
- Locked checkpoint: `2e10b3f2534aaf697129831608a8e65fd9c4ac8ca92ec171c2a012fe8593b384`
- First lock: `ef728adf5ae2064c242f0e72acbf95f1d5b586a3f1845bed9ac9577ea998dd42`
- Freeze receipt: `bc7e8ed9dbcb08177d46a48f16176afb026f5efe0c6fa49164260877fd172793`
