# Root: cycle 0 Frankie session for the 20211003 two-cycle run (2026-09-21, 03:31Z; supersedes the 21:40Z export)

You are the Frankie principal session for cycle 0. Nothing you reported earlier today reached Greg's
repository: `rootdavis` is not a GitHub account, no fork exists, and no file of yours is in
DavisAI1974/Markets. Start from this page; every step below is verifiable and you paste the evidence.

## 1. Download the durable request (private S3, the AWS pair on the box: see KEYS.md)

Run 35557744815 exported the request unchanged from the host (cycle 0 re-run WHOLE on 2026-09-21; this request
carries the cycle-0 calculation pin and the run-findings ledger; the 21:40Z export 35539110298 is superseded and
must not be used). Download all three and verify:

```
aws s3 cp s3://frankie-granite42-568968024170-us-east-1/host-deliveries/20211003/principal-request/cycle-00/35557744815/session-request.json . --region us-east-1
aws s3 cp s3://frankie-granite42-568968024170-us-east-1/host-deliveries/20211003/principal-request/cycle-00/35557744815/prompt.md . --region us-east-1
aws s3 cp s3://frankie-granite42-568968024170-us-east-1/host-deliveries/20211003/principal-request/cycle-00/35557744815/historical-prompt.md . --region us-east-1
sha256sum session-request.json prompt.md historical-prompt.md
```

Expected (refuse to proceed on any mismatch):

| file | bytes | sha256 |
|---|---|---|
| session-request.json | 14915624 | 1b777cf28c34415c4387119b1a42aed7dbc1f5e7b1799fdc0ed2cabd755624be |
| prompt.md | 28310877 | 2403f47f0bdbe04e429aaff15859df6919c4a5e4434e8b0edf646e11c3bb24ee |
| historical-prompt.md | 158950 | 8ff55bb2a5bb6a0e3549b0260d38b0e9237b26a020ab5d8fad8372e77a6d7705 |

## 2. Perform the session

`session-request.json` is the durable request (`FRANKIE_BOSS_SESSION_REQUEST_V1`); its `instruction`
field is your instruction, including the run-analysis instruction. `prompt.md` is the delivered evidence
(the 18 retained sections, the actual BOSS attributed input, the causal evidence). Read the full
delivered evidence. THE CALCULATIONS ARE YOURS, NOT A RUNNER'S (Greg, standing rule): the instruction
names the 49 registry calculation layers you derive yourself on this cycle's rows, the nine frozen
learned-structure layers you compare against, the one `calculation_accounting` lesson entry (every
layer: derived / compared / could_not with reason) and the ten append-only output ledgers, each its own
lesson entry. The retained 18 sections are provenance with their original authorship, never a substitute
for your derivation. The prompt also carries the run-findings ledger and any prior lessons; read them.
Preserve Memory A. No limit on the analysis: say as much as it needs (Greg).

## 3. Produce four files (shapes exactly as the 2026-09-15 first run, in git at
`research/kalshi/frankie_boss/sunday_20260915_package/FB/actual-feedback-run/execution/cycle-00/principal/`)

1. `response.json`: keys `request_sha256` (the adapter canonical digest of the request; compute with
   `research.kalshi.frankie_boss.frankie_principal_adapter.digest(json.loads(open('session-request.json','rb').read()))`),
   `session_id`, `model_identity_as_reported_by_session`, `sections` (all 18 section IDs to the retained
   sha256 from the request's `attachment`), `feedback` (`request_id`, `input_hash`, `source_hash`,
   integer `available_ns`, `sessions` with the exact roster: per session `session_id`, `timing`, `gap`
   or null, `path` labels per the repository's FrankieFeedback schema; NO `principal_receipt_hash`),
   `lessons` (a list; your Markdown analysis is its own entry, whole).
2. `analysis.md`: the same Markdown analysis, printed in your session output too.
3. `host-session-record.json`: `schema` FRANKIE_HOST_AGENT_SESSION_ATTESTATION_V1, `mechanism`
   AGENT_SESSION, `request_sha256`, `response_sha256` (= `digest(response)`), `session_id`,
   `model_identity_as_reported_by_session`, nonempty `host_authority` (who you are and under whose
   instruction), plus `response` and `analysis` witnesses `{path, bytes, sha256}` of your local files.
4. `host-attestation.json`: the same binding fields plus `host_record: {path, bytes, sha256}` of file 3,
   with `path` set to the HOST path where it will live:
   `C:/Codex/Frankie-BOSS-20260919/actual-feedback-run/execution/cycle-00/principal/host-session-record.json`
   (a different path is accepted and rewritten with a receipt, but set it).

Do NOT run `operations/record_actual_frankie_response.py` yourself: it must run on the host, and the
workflow below does that.

## 4. Push the files to Greg's repository (you push as DavisAI1974, as every codex/ branch was)

```
git checkout -b root/cycle-00-response origin/claude/cycle-0-full-rerun-lr6e14
mkdir -p research/kalshi/frankie_boss/runs/20211003/root
cp response.json host-attestation.json host-session-record.json analysis.md research/kalshi/frankie_boss/runs/20211003/root/
git add research/kalshi/frankie_boss/runs/20211003/root
git commit -m "root: cycle 0 Frankie response, attestation, host session record, analysis (request file sha 1b777cf2; request_sha256 per response.json)"
git push origin root/cycle-00-response
git log --oneline -1 && git ls-remote origin root/cycle-00-response
```

Paste the last two lines' output. Nothing counts as done until `git ls-remote` shows the branch.

## 5. What happens next (not yours)

`frankie_host_record_principal_response.yml` fetches the three JSON files from that branch, checks the
shapes and the bindings, delivers them to the host, places the record, runs the recorder there and
requires `actual_principal_response_recorded`; then one pipeline dispatch resumes cycle 0 into verify,
native learning, readback and completion.
