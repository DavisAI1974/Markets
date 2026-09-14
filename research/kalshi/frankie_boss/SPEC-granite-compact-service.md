# Explicit compact context through Granite and the controller

Owner requested the remaining full build and real Granite integration. The compact
codec exists but is not service-wired. This slice carries that exact representation
through the existing transport and durable controller, without another launcher.

Add an explicit `context_encoding` choice to FrankieForecastController, defaulting
to native_v1 for compatibility. compact_v1 requires the distinct compact identity
and critique_compact method. Unknown encodings reject. Never select a codec by
size or silently truncate a request. B1 input, forecast production and category-free
records remain unchanged; encoding changes the critic request/configuration identity.

One small context-route module resolves the existing native/compact mapper, parser,
prompt and scorer consistently for shared serving and journal replay. Native V1
and compact prompt bytes remain unchanged. Code identity changes are explicit;
old prompt hashes are not presented as proof of unchanged parser source bytes.

Add critique_compact to both existing AWS services, reusing their exact SDK request,
timeout, single-call ownership and response retention. Controller converts its
validated native snapshot to compact, verifies the exact inverse, records the route
and supporting code in its intent, and scores the compact-hash response. Restore
uses the recorded route, reconstructs native source bindings, and rejects altered
route/snapshot/response. Older journal intents without a route mean native_v1.

Acceptance: exact compact prompt through a real boto3 Stubber; wrong prompt/parser
pins and oversized request refuse before transport; compact and V1 forecasts match;
completed retry and trusted controller-journal restore make no new calls; altered
encoding or foreign native/compact snapshot cannot reuse a request. Existing native
service/controller tests remain green. An actual deployed model run still follows
artifact/runtime/capacity preparation; Stubber is software evidence only.

## Implemented software verification (2026-09-14)

`granite_context_route.py` resolves the two explicit encodings. The existing
Bedrock and SageMaker services now expose `critique_compact`; they retain their
SDK body, timeout, single-call ownership and raw response retention. Controller
configuration pins the chosen encoding and route/codec source, and critic intents
record both the encoded snapshot hash and the exact inverse native snapshot hash.
Journal admission and replay validate the recorded route, prompt and native source
bindings before accepting completion. B1 and forecast production are unchanged.

The dedicated compact service/controller suites verify both real boto3 Stubber
request shapes, prompt/parser and byte-capacity refusal before SDK construction,
identical category-free forecast records, completion reuse/restart without calls,
explicit unknown-call recovery, foreign snapshot refusal, and altered route/source
rejection. Package and standalone route imports are covered. Existing native tests
continue to cover the default route.

Identity migration is explicit: native/compact prompt strings and their existing
parser helpers were not changed by this slice. Controller source/configuration
identity changes, so old request IDs cannot be resumed under a newly constructed
configuration. Historical journal intents that omit `context_encoding` still
replay as native_v1; no historical request or receipt is rewritten. Compact service
callers must supply the compact prompt and compact parser identity, never a native
pin. Subsequent shared-contract packaging changes must update parser identities
honestly even when all three prompt byte strings remain identical.

This is synthetic software/SDK evidence. Actual deployed Granite model execution,
full context capacity and production acceptance remain separate build gates.
