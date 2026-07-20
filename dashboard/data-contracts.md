# Proposed frontend event contracts

The UI should consume canonical internal events rather than raw venue or vendor payloads. Vendor-native records should remain available through an inspector, but should not leak into every component.

## Initial snapshots

Suggested read endpoints:

```text
GET /api/v1/desk/snapshot
GET /api/v1/episodes/{episode_id}
GET /api/v1/opportunities?status=actionable
GET /api/v1/weather/events/{event_id}
GET /api/v1/risk/snapshot
GET /api/v1/operations/health
GET /api/v1/replay/{episode_id}/manifest
```

## Streaming envelope

```json
{
  "event_id": "01J...",
  "event_type": "episode.updated",
  "schema_version": 1,
  "emitted_at": "2026-07-20T19:17:04.119381Z",
  "source_event_at": "2026-07-20T19:17:04.077000Z",
  "trace_id": "s100-ng-0719-0042",
  "payload": {}
}
```

## Core event types

```text
system.health.updated
market.leader.updated
market.follower.updated
market.book_state.updated
decision_state.block_updated
decision_state.delta_created
perception.snapshot_created
play.invocation_created
play.invocation_updated
opportunity.created
opportunity.updated
action_intent.created
risk.decision_created
execution_plan.created
order.event_received
fill.received
episode.updated
episode.outcome_finalized
evidence.forward_updated
operations.exception_created
```

## Decision episode

```json
{
  "episode_id": "S100-NG-0719-0042",
  "status": "MANAGING",
  "commodity": "NG",
  "normalized_event_id": "event-ng-above-355-2026-07-24",
  "leader_instrument_id": "databento:GLBX.MDP3:123456",
  "follower_instruments": [
    {
      "venue": "KALSHI",
      "instrument_id": "...",
      "match_class": "EXACT",
      "rule_snapshot_id": "rule-v7"
    }
  ],
  "automation_mode": "AUTO",
  "decision_state_snapshot_id": "state-a8d1",
  "perception_snapshot_id": "perception-7f42",
  "active_play_invocations": ["play-..."],
  "action_intents": ["intent-..."],
  "orders": ["order-..."],
  "risk_budget_reserved_usd": 12600,
  "created_at": "...",
  "updated_at": "..."
}
```

## Play invocation

```json
{
  "play_invocation_id": "play-01J...",
  "episode_id": "S100-NG-0719-0042",
  "play_id": "flow_nowcast",
  "play_version": "1.9.0",
  "stage": "DIRECTION",
  "authority": "PRODUCTION",
  "evidence_state": "FORWARD_CONFIRMED",
  "scope": {
    "matched": true,
    "scope_version": "3.2",
    "dimensions": {
      "commodity": "NG",
      "session": "REGULAR",
      "regime": "PEAK_SEASON"
    }
  },
  "requirements": [
    {
      "requirement_id": "strong_signed_flow",
      "passed": true,
      "observed_value": 0.84,
      "threshold": 0.72,
      "as_of": "..."
    }
  ],
  "output": {
    "direction": "LONG",
    "strength": 0.87
  },
  "invalidation": [],
  "forward_evidence_expected": "forming_leg_side",
  "decision_state_hash": "sha256:a8d1...",
  "created_at": "..."
}
```

## Opportunity

```json
{
  "opportunity_id": "opp-...",
  "episode_id": "S100-NG-0719-0042",
  "type": "LEADER_FOLLOWER_LAG",
  "status": "ACTIONABLE",
  "urgency": "HIGH",
  "created_at": "...",
  "expires_at": "...",
  "edge_clock": {
    "leader_event_at": "...",
    "expected_reprice_start_ms": 7000,
    "expected_reprice_end_ms": 20000,
    "current_age_ms": 11200
  },
  "economics": {
    "gross_edge_usd": 3540,
    "maker_net_edge_usd": 3420,
    "taker_net_edge_usd": 3260,
    "likely_mix_net_edge_usd": 3330,
    "executable_size_usd": 9400,
    "fill_probability": 0.78
  },
  "definition_match": {
    "class": "EXACT",
    "mapping_version": "7",
    "known_basis_risks": []
  }
}
```

## Causal timestamps

Preserve these when applicable:

```text
source_event_at
source_publish_at
vendor_receive_at
internal_ingress_at
feature_ready_at
play_triggered_at
risk_approved_at
order_sent_at
venue_acknowledged_at
fill_at
follower_quote_changed_at
```

## Databento adapter boundary

The internal CME adapter should expose canonical market events and retain raw DBN references. The main UI should depend on internal identifiers and point-in-time instrument definitions, while the diagnostics inspector may show fields such as `instrument_id`, `ts_event`, `ts_recv`, schema, dataset, and source record location.

Suggested UI-facing schema selection:

```text
MBO       → futures order flow, queue and far-ladder recruitment
MBP-1     → lightweight current quote state
MBP-10    → depth visualization when order identity is not required
TBBO      → trade-response and execution analysis
Definition→ point-in-time contract and option metadata
Statistics→ settlement, open interest, session statistics
Status    → trading state, halt and session transitions
```
