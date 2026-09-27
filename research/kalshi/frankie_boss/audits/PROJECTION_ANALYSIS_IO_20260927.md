# Projection and analysis preparation — actual observations 2026-09-27

## Scope and live identity
The user authorized checking projection/digest resource use and the remaining analysis preparation for avoidable serial work. This assessment made no ROOT transition, inference, source replay, deletion or infrastructure change. Runtime remains 01caae9d3a0e7ccdb165c734fe25ecf130c5c0f5, workflow36319242284, PID58168, token099d4eb6-a46d-4b94-a888-f15e55c1ee7e:53570313. Calculation root: /opt/frankie-box/work/monday-calculations/full-20211004-20260927-r1-48.

All2032203 scientific records and finalized ledgers remain retained. The final calculations receipt is not yet published. Principal analysis, actual Granite requests, classroom, grades/corrections and retention remain pending.

## Measured CPU and I/O
Read-only workflow36321527916 sampled the same process from13:11:42.459328Z to13:12:02.461710Z:
-19.29CPU-seconds over20.002387seconds, approximately0.964core.
-Process read-character counter advanced190193664bytes (~9.51MB/s); write-character counter advanced459822782bytes (~22.99MB/s).
-Physical read_bytes advanced190316544bytes.
-RSS2006728KiB, swap0; host memory available roughly254736712KiB. No memory pressure and low I/O waiting during this interval.
-Stage root-projection, failed0.32process threads do not imply32active compute workers. The existing stage-local0/unknown counter is not useful completion progress.

This establishes CPU-limited execution for the observed interval, not a controlled speedup benchmark.

## File position and storage
Read-only workflow36321642052, using committed observere14e679ac8d97610912d90345cea4b8e73206c6f, captured at13:13:40.687399Z:
-Active input exact_member_rows.jsonl:position16787587072 of537182189410bytes (3.12512% by bytes).
-44layer pairs,88open member/lifecycle spool files; their observed total40652336829bytes. Lifecycle spools were still empty.
-Largest open spool full_bid_ask_depth-members.jsonl:24856231174bytes.
-Free filesystem space240395096064bytes.
-Original ledger remains in recovery-9defa3169f7d46679491da2b1bfbbce2; no copy was substituted.
-ROOT affinity permits32logicalCPUs, but source execution remains serial.
The verbose first observation exhausted the SSM output budget before all samples could be parsed; only this complete first file-position sample is claimed. The observer now summarizes spool totals and the five largest spools to preserve complete subsequent samples.

Conditional extrapolations, not ETAs or reserved-capacity predictions:
-At9.51MB/s, the remaining member-ledger read alone is approximately15.2hours, before lifecycle projection, final layer serialization and digest.
-At the observed spool/input ratio, complete member spools would total approximately1.30TB, requiring approximately1.26TB more, versus240.40GB free.
-At22.99MB/s output, that free space corresponds to approximately2.9hours. Record complexity and compression vary; this is not an exact exhaustion time.
Additional copies, final JSON layers and digest scratch are not included in this storage extrapolation. Current capacity cannot be assumed sufficient. Extra CPUs alone do not address expansion.

## Exact source findings
At01caae9:
1. frankie_box_bedrock.py project() parses each member row once, iterates its applicable layers serially, and appends type-preserving intermediate rows through RowSpool. Lifecycle rows and final layer publication follow serially. It has no projection helper pool or resumable projection-batch cursor.
2. RowSpool.append() recursively applies the journal pack codec then JSON-encodes it. write_json() later reads/unpacks those rows and uses Python iterencode(indent=1) to serialize the final layers, then reads each layer again for its hash.
3. frankie_box_digest_sources.py copies and independently hashes every pinned projected layer, parses rows into SQLite, and merges group/column values with per-cell SELECT/INSERT operations. These preserve conflict checks and group ordering; they are not safely removable by treating all rows as independent.
4. frankie_box_digest_document.py processes tables serially. write_table() already inverse-verifies its emitted table; document assembly then inverse-verifies it again and hashes the table before/after. Complete document bytes are hashed at result, intent and publication. Some same-file byte witnesses can potentially be shared with unchanged-file guards, as in finalization. Removing independent semantic proof requires a carefully defined replacement; this audit removes nothing.
5. Principal execution requires calculations-receipt.json and --require-retained-derivation. It reuses science, then runs reading, mandatory classroom, teaching and writing. Classroom14CPUhelpers prepare sources/tokenizers only; they do not accelerate projection, SQLite digest work or GPU generation.

## Concrete next implementation boundary
The demonstrated target is projection's serial parse/project/encode path and its expanded intermediates. A useful fix must address BOTH CPU and disk volume, preserve exact scientific values, causal row order, all required layers/reducers and historical hashes, retain partial outputs, and add durable projection progress/recovery. Bounded CPU processes are appropriate for Python-heavy work; merely adding Python threads is not evidence of parallel CPU execution. Reusing encoded rows and a verified compact or compressed transport should avoid repeated materialization, but all readers and publication receipts must agree on its contract.

Do not silently activate a new format, apply output caps, reduce records/layers, delete older ledgers, or hot-patch this runtime. Any actual transition still requires a fresh verified complete checkpoint and an explicit preserved-output/resume path; the existing terminal-finalize pause mode currently refuses root-projection. No pause was attempted by this assessment.

## Receipts and limits
-36321527916: completed success, actual20-second CPU/I/O observation.
-36321642052: completed success, complete first file-offset/space observation.
-e14e679: committed/pushed metadata-only observer; no active ROOT source mutation.
-No model calls, validators, scientific tests, benchmark/comparison runs or parallel agents.
-No new claim about classroom speedup, Granite learning or Tuesday.
