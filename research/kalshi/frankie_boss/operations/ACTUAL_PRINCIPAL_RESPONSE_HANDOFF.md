# Actual principal response and nineteen-cycle continuation

After each completed BOSS/Granite controller the host prepares the frozen
receiver attachment, saves `execution/cycle-NN/principal/session-request.json`,
and waits for the actual response. Its observation-only callback dispatches no
agent. The execution stack and validated prepared context remain live. A
separate `actual-host-session.lock` retains host ownership; `actual-host.lock`
is released only during this wait so the validating recorder can operate.

Root consumes that exact session request, prompt, frozen knowledge bundle,
eighteen section witnesses, actual attributed BOSS attachment and authored
feedback contract. Root performs the authorized actual Frankie analysis and
retains the real session/output provenance. No historical section calculations,
Memory A, source day, or missing market label may be invented or recomputed.
The feedback availability and labels must obey the supplied learning cutoff;
full delivered end-of-day evidence does not make it available at an earlier cutoff.

## Required response and attestation

Response JSON carries `request_sha256` (adapter canonical request digest),
`session_id`, `model_identity_as_reported_by_session`, `sections` (all eighteen
IDs to retained SHA256), `feedback`, and `lessons`. Feedback has `request_id`,
`input_hash`, `source_hash`, integer `available_ns`, and the exact session roster.
Each session has `session_id`, `timing`, `gap` (or null), and `path` labels under
the repository's FrankieFeedback schema. Do not supply principal_receipt_hash;
the adapter derives its actual receipt after the host attestation is checked.

The independent host attestation has:

- schema FRANKIE_HOST_AGENT_SESSION_ATTESTATION_V1;
- mechanism AGENT_SESSION;
- request_sha256 and response_sha256 (canonical JSON digests);
- actual session_id and model_identity_as_reported_by_session;
- host_record `{path,bytes,sha256}` referencing the root's retained real dispatch/
  output observation record. That record contains the same binding fields and a
  nonempty host_authority. It must describe actual execution; model self-claims
  alone are insufficient. The helper never manufactures provenance.

## Recording a reviewed actual response

Use the existing native-runtime Python with the inert helper at
`work/record_actual_frankie_response.py` in this continuation task. Arguments:
`--configuration PATH --configuration-sha256 SHA --cycle-index N`
`--response PATH --response-sha256 SHA --host-attestation PATH`
`--host-attestation-sha256 SHA`.

The helper requires the actual host lock, prior request, prior bound mapping,
and exact retained plan/export. It reconstructs the same adapter without any
session executor. It checks the candidate through the actual adapter recovery/
verification paths and the native learner's exact pure label validation in a
preserved candidate directory before recording the immutable final response.
STOP requires observations through session close, so a censored tail cannot
be converted to STOP. A changed existing response is refused; exact replay
is allowed. It performs no model call, source binding, receiver preparation or
training. Root still reviews policy-specific market labels before recording.

The waiting host reacquires its recorder lock and validates the recorded
response before continuing automatically, without replaying the controller or
preparing the same context again. The verified new feedback drives
one native learning checkpoint and separate lessons, then the next authored
cycle reaches its exact admission/readiness boundary. Each new admitted critic
request requires root's proper run cleanup/start/readiness operation. A pending
same-job HTTP recovery instead uses FRANKIE_ACTUAL_RESUME_JOB_V1 stdin and never
starts another Pod. Complete all nineteen cycles in order.

After a genuine host process interruption, resume the same host/config with its
retained controller and response evidence. Existing unresolved principal intent
still exits status 3 rather than dispatching another session; record that exact
request before resuming. A process crash necessarily loses its in-memory cache.

Host exit 5 and INCOMPLETE_RESPONSE_CONTEXT_EXHAUSTED mean the critic reached
the physical context limit without completing its answer. The visible alert
includes the reported limit/input counts, actual usage if supplied, and retained
partial-output evidence path. Stop before principal feedback or native learning;
never represent that partial response as a completed critic or trigger another
inference on resume.

## Host config derivation

`refresh_policy_bands=[[7186681902729,1]]` covers the exact largest remaining
session horizon in the nineteen-cycle authored contract. Its minimum actual
cutoff spacing is 8,670,252,964 ns; a 1 ns minimum interval preserves every
original invocation and creates no extra scheduled calls. The actual host now
uses `output_budget=remaining_context`: each exact prompt is tokenized once and
receives the entire physical remainder of its selected 131072-token context.
The first input is 92427 tokens, leaving 38645 output tokens until EOS or the
physical context limit. Later cycles use their own exact input count; there is
no fixed output quota. Tokenizer SHA is
51e3c30923a00f8d17cc0c6126a06d8e4911b5e83232abbed255c2abb49a438a.

`state_defects_and_gaps_reported=[]` remains empty absent actual fatal source
defects. The consumer treats this as a fatal abstention channel, so nonfatal
development caveats are retained separately in `development_limitations` and
the metadata's existing reasoning: one Sunday, same-source analytical anchors,
1.0 development numeraire, unknown timestamp noise floor, censored final tail,
uncalibrated development models, and no broker authority.
