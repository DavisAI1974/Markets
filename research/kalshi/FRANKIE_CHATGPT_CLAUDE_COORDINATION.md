# Frankie ChatGPT <-> Claude Coordination Ledger

This file is for operational coordination between ChatGPT and Claude on the Frankie build.

It is not canonical truth. `research/kalshi/OPEN_ITEMS.md` and the registered project state remain authoritative.

## Protocol

- Append only. Do not rewrite another party's block.
- ChatGPT blocks use `CHATGPT -> CLAUDE`.
- Claude blocks use `CLAUDE -> CHATGPT`.
- Each exchange uses a unique `C2C-###` ID.
- Claude executes only the latest unresolved ChatGPT block and stops when its stated stop condition is reached.
- Large outputs should be stored as repository artifacts and referenced here by path and hash.
- `research/kalshi/spawn.py` remains protected unless Greg explicitly authorizes a reviewed change.
- Canonical brain changes continue to follow the project's proposal, adjudication, and merge discipline.

## Block template

```text
## CHATGPT -> CLAUDE | ID: C2C-### | STATUS: OPEN
purpose: ...
required state: ...
actions: ...
stop conditions: ...
return: ...
```

```text
## CLAUDE -> CHATGPT | ID: C2C-### | STATUS: COMPLETE|STOPPED
executed state: ...
result: ...
outputs: ...
stop/failure: ...
```

## Initial state

- Branch: `chatgpt/agent-frankie-s117`
- PR: #8
- Previous operational pin: `908fdeb839713f3d66333e43bf078ed87e2fa223`
- Clean G18/G19 validation is not yet complete.
- Current objective is one valid clean canary, then only G18/G19, then paper-trading work unless a real mechanical defect appears.

---

No coordination task is open yet.
