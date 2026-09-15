# Explicit stacked V1 critic route

The operational host selects `context_encoding=stacked_v1` and `service_context=131072` explicitly. This is a new candidate: its prompt, parser, configuration and runtime identities differ from retained compact/4096 evidence. It becomes usable only after exact full-body tokenizer admission and separately verified current service startup.

The wrapper applies the stacked codec to the complete reduced native value, restores the accepted native field paths/scalar views, and verifies the original native hash and exact text. All output references are checked against that restored native context. The output snapshot hash identifies the actual stacked envelope. Codec bytes, grammar, wrapper and native/compact inverse code enter the parser identity.

The host passes its independently verified source scope and an optional explicit per-cycle preceding prefix seed. The codec derives packet hashes only with complete contiguous source coverage and exact equality to every original hash. Missing earlier seeds or intervening rows keep the literal vector. There is no source lookup, inferred seed, truncation, paging or native-model embedding substitution.

Preparation, Sunday request plans, controller configuration and snapshot encoding carry identical explicit options. Retained preparation from another encoding is rejected. Controller replay reconstructs the native context and reproduces the configured stacked encoding before accepting its stored prompt. A checkpoint change still invalidates preparation/cache reuse. Legacy encodings keep their default behavior; derivation options are rejected outside stacked V1.

Local tokenizer capacity must equal the explicitly selected service context. Fresh startup, model files, service configuration and identity remain independently verified. This route adds no runtime deadline or retry behavior. The existing durable same-attempt transport remains responsible for open-ended inference.

Validation: two new synthetic exact-inverse/output-reference/tamper checks passed; one separate new preflight identity/options check passed. These perform no provider call, source recovery or training. Actual production-wrapper capacity measurement belongs to the launch agent and is recorded separately.
