# NG Exhaustion Event-Mark Clock — Open Boundary — 2026-08-19

Status: **OPEN INFRASTRUCTURE/CAUSAL-TIMING BOUNDARY. DO NOT GUESS.**

The active V3 recovery distinguishes three different things that must not be conflated:

1. frozen retrospective exhaustion onset/birth `t0`;
2. the upstream causal detector's actual live event-mark/discovery timestamp;
3. the later structural endpoint / `dynamic_endpoint.causal_confirmation_idx`.

`research/ng_exhaustion_live_clock.py` explicitly states that the live runway adapter is **not an event detector**. An upstream causal detector supplies event `t0`; only then does `mark_event` derive event polarity from roll20 at `t0` and assign frozen A/B/C family from the causal `t-60..t0` geometry.

Therefore:

- raw price direction, signed flow/roll20/dipole and book state are continuously observable and remain available at every checkpoint regardless of event-specific label availability;
- frozen target polarity is not needed to observe the market and is not a primary prediction target;
- event-specific polarity/A-B-C family may enter once the upstream detector has actually marked/discovered that event and the required causal tape window is available;
- `dynamic_endpoint.causal_confirmation_idx` is not automatically the event discovery timestamp and must not be used as a generic label-availability gate merely because it is the only confirmation field in the canonical row;
- frozen retrospective `t0` is also not automatically assumed to be a live notification timestamp.

Until the protected upstream detector's actual live mark-time contract is located/proven, V3 remains conservative for event-specific newborn labels while still exposing the complete causal market movie.

This uncertainty does **not** invalidate PRIOR continuation/depth/family prediction from already-known predecessor/root information and the live market. It does mean that post-birth H results must be labeled historical timing/economics unless and until the live event-mark clock is proven.

Do not modify or retune the protected detector to resolve this documentation gap. Locate and prove the existing detector contract instead.

Standing policy: `FLAG_AND_DECOMPOSE_NOT_AUTO_KILL`.
