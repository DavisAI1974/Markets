# One Runpod smoke request from the host

`run_probe` validates the independently pinned admission receipt before any HTTP.
The admission module owns the exact frozen nonmarket request, served model and
context/token budget. Synthetic admission is refused by the production path.
Require exact equality between supplied and separately approved Pod IDs. Derive
only `https://{pod_id}-8081.proxy.runpod.net`, as documented by
[Runpod](https://docs.runpod.io/pods/configuration/expose-ports). There is no URL,
port, prompt, output-budget or request-ID override. Required key matches the
proxy's format, is sent only as Authorization, and is never logged or journaled.

At most three authenticated health requests precede one inference. Each health
has at most5s, inference at most80s, and every exchange is clamped to the remaining
whole90s budget. No redirects, environment proxies, or inference retries. Health
must equal the proxy's minimal status; it does not prove hosted identity.

SQLite uses synchronous FULL and a unique Pod-ID attempt key. Commit the attempt
before entering inference I/O. Concurrent calls, changed admission/request IDs,
uncertain timeout and restart cannot resend for that Pod through the same journal.
There is no reset API. A canceled/crashed call leaves the durable attempted row.
Store bounded sanitized outcome separately; failure to store outcome cannot erase
the attempt. The trusted host must preserve the same absolute journal file and
its storage durability; deletion, replacement, alternate journals or arbitrary
direct HTTP callers are outside this helper's enforcement boundary.

Receipts retain canonical request hash, admission hash, Pod ID, health count,
outcome, and bounded successful provider response. Error content and credentials
are not retained. A successful response must be one stopped text-only completion
for the exact served model. This is one connectivity/protocol smoke, not trading,
repeatability, hosted runtime identity, complete controller acceptance or model
quality acceptance. Closing HTTP does not establish cancellation of generation.
Completion text must be exactly READY, allowing trailing whitespace. Reported
usage must match admitted prompt count, positive output within16 tokens, and
consistent total within4096. These are provider-reported protocol checks, not
independent hosted runtime/tokenizer identity verification.

Concrete HTTPS enforces certificate verification, response length<=65536 and
JSON content type, no transfer/content encoding. A socket watchdog closes slow
headers/body at the remaining deadline. Standard-library DNS resolution can
return after the deadline; late connect returns are refused before transmitting.
The helper therefore does not promise a hard process-return deadline during DNS
or local filesystem stalls. An independent operator cleanup path is still needed.

No allocation, termination, shell commands, credentials lookup, main entrypoint,
model download or hosted workflow changes. The caller supplies only the proxy
key, never a Runpod account API credential. GPU billing cleanup remains the
independent host/operator procedure; an elapsed local deadline is not termination.
Sunday remains held.

Acceptance: fake transport inspects a separately opened SQLite connection to
prove attempt commit precedes POST; successful and ambiguous attempts both refuse
restart without further HTTP; failed admission/Pod pin causes zero I/O; health
count and total time are bounded; malformed/oversized/secret-echo responses are
sanitized. Concrete HTTPS adapter tests use connection doubles only.
