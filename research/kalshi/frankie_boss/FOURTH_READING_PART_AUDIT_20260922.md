# Fourth reading part: cause and repair — 2026-09-22

Greg confirmed that “one of four” means the fourth reading part. Analytical sections4.2 and4.4 are separate and remain for their normal run.

## What the retained evidence proves
The retained part4/4 note exists and covers corpus bytes527078–532065. The first merge generated an inline runaway tail; the next merge reported incomplete input; the final merge explicitly excluded part4. This was a merge failure, not evidence that useful knowledge or hypotheses were absent.

Artifacts are under records/chat6_scratchpad_20260921/cycle-00-docs/docs-cycle-00/. The retained docs-index.json binds their bytes and SHA256; regression tests independently hash the actual files.

| Artifact | Bytes | SHA256 |
|---|---:|---|
| reading-note-0003.md | 21270 | 3e7ab51bc59ae9d815ea2350e306f19570279cb29f069ffa72f772e1b7e1a982 |
| merge-0-0001.md | 174406 | bd788ab0428d28e15c95179b4cc71b0c72799a559b06b803cdf0c223b8c55a88 |
| merge-1-0001.md | 9471 | d763e3c8f21bc0b6deedc81c35da4496d6468433736279cc5c6f8c3fc7e660a3 |
| merge-2-final.md | 51210 | 5e4f356a01081a9abb8aad1e57a42ae4fa56f68034020f63bca412f8d04fbcb0 |

The earlier hash/refusal/runaway guards were insufficient: the first retained runaway used a long inline repeated tail, which the line-based runaway detector did not identify. The fourth note carried no independent SHA256 that could force retention. The actual-artifact regression reproduced that gap in codecs35802300091 and readiness35802300066; both failed only the new retained-fourth-part check.

## Repair
keep_if_lossy now requires all hashes AND every nonblank input line to survive exactly (outside whitespace ignored). It permits exact-line deduplication/reordering; otherwise it keeps the original inputs verbatim. This also catches a quiet omission where the model merely echoes a part heading or claims complete coverage. Rejected model output is retained separately and old merge artifacts still receive movement receipts.

A merge level that cannot reduce UTF-8 byte size returns the complete guarded notes without another model merge. The pre-existing depth stop now also applies to oversized groups. No output cap was introduced. More notes can remain after a conservative fallback; physical context admission may refuse them, never silently truncate them.

No analytical producer, source record, prior response, Pod bootstrap or live host was changed by this repair. The regression replays retained text through the current guard; it is not a new model call, a new production reading receipt, or proof of internal model comprehension.

## Scope
Pushed implementation a76ec2df801cff07638ed0b40bcd7d6a70f833c0; final CI/review receipts are recorded in SHIP_REVIEW_20260922_CHAT12.md. Deployment and a request-bound production reading/merge receipt remain required at the authorized rerun.
