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
