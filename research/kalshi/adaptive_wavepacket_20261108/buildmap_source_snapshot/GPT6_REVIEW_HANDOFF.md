# GPT-6 Sol Review Handoff — BuildMap v0.1

Repo: `DavisAI1974/BuildMap`  
Branch: `feat/buildmap-v1-living-map`  
PR: #1 — Build the first living BuildMap proof  
Current tip: `e271b6148f3397ea751ee8a16dc38b48d063b582`

## Product intent

BuildMap is **not** a static architecture diagrammer and should not drift into becoming one.

The product idea is a **living visual representation of software being built**:

- planned pieces may appear before their files exist;
- as files are created, the corresponding pieces appear or light up;
- as code is actually wired together, connections appear;
- a piece should visually explain **what the file/component does**, not merely show a box and an arrow;
- the map should show how that piece gets the project closer to its intended outcome;
- missing pieces, dead ends, disconnected code, and unsupported claims should be visually obvious while the build is happening;
- the map should help the builder/agent stay ultrafocused on the intended system.

The inspiration may borrow spatial language from workflow maps, but **only the spatial language**. This is not meant to become a workflow editor.

A useful conceptual zoom hierarchy for later versions is:

`File → Mechanism → Capability → Subsystem → Mission`

v0.1 does not need to fully implement all five levels yet.

## Greenfield / brownfield rule

Start with whatever evidence exists. Do **not** require ceremony before mapping can begin.

### Greenfield
May begin from:
- README,
- BuildMap manifest,
- both,
- or neither.

If intent is unclear, an interview can be used. Planned pieces should be able to exist as ghosted components before implementation lands.

### Brownfield
Use an intent ladder before interviewing:
1. read `.buildmap/project.json` if present;
2. read README and obvious architecture/design/spec docs;
3. inspect/map the actual repository;
4. compare stated intent vs code reality;
5. interview only where intent remains missing, ambiguous, or contradictory.

This direction came from the greenfield/brownfield and interview ideas in `addyosmani/agent-skills`, but BuildMap should adopt the useful behavior, not mechanically reproduce that project.

## Core contract — DO NOT WEAKEN

The most important rule in BuildMap is:

**Existence, connection, computation, verification, and live use are different things.**

Current evidence ladder:

`planned → coded → connected → computing → verified → live`

The first three may be inferred from source/manifest evidence.

The upper three must **not** be granted merely because a file exists or imports resolve. They require explicit evidence.

Do not make the UI prettier by erasing this distinction.

## What v0.1 currently contains

- zero-dependency Node 20+ app;
- local project-path mode;
- optional public GitHub URL mode using shallow clone;
- intent recovery from manifest/README/docs/SPEC;
- repository scanner;
- relative JS/TS/Python import discovery;
- planned components from `.buildmap/project.json`;
- explicit evidence from `.buildmap/evidence.json`;
- proof-state calculation;
- live HTTP server;
- interactive SVG/HTML visual map;
- per-piece mini visual mechanisms;
- piece inspector showing purpose, files, connections, evidence, and contribution;
- BuildMap dogfoods itself via its own manifest;
- tests covering the core evidence and intent behavior.

## Current verification state

Known good from the v0.1 build session:

- `npm test`: 7/7 passing;
- JS syntax checks passed;
- local-path runtime/server smoke passed;
- BuildMap mapping itself reported ~77% proof, with 3 verified pieces and 2 computing pieces.

Known limitation:

- direct public GitHub-URL cloning is implemented but was **not runtime-verified** in the build sandbox because outbound DNS was blocked.
- Keep that limitation explicit until you actually exercise it.

## Your job

Treat v0.1 as a real first specimen, not sacred code.

1. Read this file, `README.md`, `.buildmap/project.json`, `.buildmap/evidence.json`, and the source/tests.
2. Run the current tests and smoke the app before changing anything.
3. Review the product model, data model, scanner logic, state semantics, UI, and developer experience.
4. Identify the highest-leverage changes that make the product **more truthful, more visually explanatory, and more useful during an actual build**.
5. Improve it in focused commits.
6. Add/adjust tests for claims you strengthen.
7. Keep README and evidence honest.
8. Do not mark anything verified/live without corresponding evidence.
9. Avoid framework churn unless it materially improves the product. The current zero-dependency approach is intentional but not immutable.
10. Prefer making the map better at spotting gaps over adding decorative features.

## Areas worth challenging

These are opportunities, not directives:

- whether file/import discovery is robust enough for real brownfield repos;
- whether inferred intent should show uncertainty more explicitly;
- whether planned-vs-actual architecture drift should be first-class;
- whether Git history should animate when a piece “arrived”;
- whether CI/test receipts can automatically earn `verified`;
- whether runtime/deployment evidence can automatically earn `computing` / `live`;
- whether the little mechanism visuals can become more meaningfully tied to source behavior;
- whether zoom levels above file/component would improve large repositories;
- whether BuildMap should expose a small machine-readable API for coding agents to ask “what is missing next?”;
- whether the map can distinguish “exists but unused,” “wired but unproved,” and “proved but not live” more clearly.

## What success looks like

After your pass, a developer should be able to point BuildMap at a project and answer, visually:

- What are we trying to build?
- What pieces exist?
- What is still only planned?
- What is actually connected?
- What is doing real work?
- What has been proved?
- What is live?
- What does this particular piece actually do?
- Why does this piece matter?
- Where is the next meaningful gap?

The README should remain strong enough that another capable model or engineer can understand the product without access to the original chat.
