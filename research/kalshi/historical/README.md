# Frankie historical replay state policy

Historical Frankie runs use the **current Frankie brain/schema/serving contract** against historical causal inputs. Runtime feed caches are not assumed to survive between runners or sessions.

## Required sequence

1. Rebuild every existing feed that can be reconstructed causally from its authoritative historical source.
2. Recover older causal payloads only when their historical provenance is known and re-apply the **current** blind wall. Never copy an old forecast or old agent state as authority.
3. Leave a field unavailable when its historical vintage was never captured or cannot be reconstructed safely. Never substitute realized values, zeros, or future revisions for missing vintage evidence.
4. Materialize the resulting current-contract decision state for the whole group.
5. **Commit that decision state plus an availability/provenance manifest under `research/kalshi/historical/snapshots/<group>/` before the forecast is frozen.** This committed snapshot is the durable source for reruns; runtime caches and short-lived Actions artifacts are not.
6. Freeze the forecast in a separate namespace before opening actual outcomes.
7. Score/render only after the forecast freeze.

## Why this exists

Frankie's schema and brain are persistent code, but many feed values are produced into runtime, S3, or cache stores. A clean runner can therefore know that a field exists while lacking its historical value. Sealed decision-state snapshots separate **persistent historical evidence** from **ephemeral feed materialization** and make repeated historical runs deterministic.

## Integrity rules

- No new datapoint families are introduced by hydration.
- Current A-E roles and protected spawner remain unchanged.
- Same-day or post-cutoff evidence stays hidden.
- Historical realized-weather proxies are not accepted as forecast vintages.
- Reconstructed data must carry provenance and availability status.
- If outcomes have already been exposed, any later hydrated replay is labeled post-reveal/counterfactual and is not used to teach Frankie.

G3/S130 is the first sealed snapshot implementing this policy:
`research/kalshi/historical/snapshots/g3_s130/`.
