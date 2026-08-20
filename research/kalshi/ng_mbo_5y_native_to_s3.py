"""Lossless five-year NG.v.0 MBO batch acquisition -> existing Markets AWS S3 bucket.

Canonical archive invariant:
- Databento batch output remains native compressed DBN (.dbn.zst), byte-for-byte.
- No JSON/dataframe conversion is used for the canonical copy.
- Every uploaded object gets a local SHA-256 recorded in S3 metadata + immutable segment manifest.
- Segment/job receipts are stored in S3 before polling, so reruns reuse an existing Databento job
  instead of repurchasing the same date span.

This script is intentionally driven by environment variables from the GitHub Actions workflow.
"""
from __future__ import annotations

import datetime as dt
import glob
import hashlib
import json
import os
import tempfile
import time
from pathlib import Path

import boto3
import databento as db


def _required(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise SystemExit(f"required environment variable unavailable: {name}")
    return value


def main() -> None:
    api_key = _required("DATABENTO_API_KEY")
    bucket = _required("BUCKET")
    prefix = _required("PREFIX").strip("/")
    dataset = _required("DATASET")
    symbol = _required("SYMBOL")
    stype = _required("STYPE")
    schema = _required("SCHEMA")
    label = _required("LABEL")
    start = dt.date.fromisoformat(_required("START"))
    end = dt.date.fromisoformat(_required("END"))
    year_max = float(_required("YEAR_MAX_USD"))

    s3 = boto3.client("s3", region_name=os.environ.get("AWS_DEFAULT_REGION"))
    client = db.Historical(api_key)

    quoted = float(
        client.metadata.get_cost(
            dataset=dataset,
            symbols=[symbol],
            stype_in=stype,
            schema=schema,
            start=start.isoformat(),
            end=end.isoformat(),
        )
    )
    print(f"[preflight] {label} quote=${quoted:.12f} ceiling=${year_max:.2f}", flush=True)
    if quoted > year_max:
        raise SystemExit(f"year quote ${quoted:.6f} exceeds hard ceiling ${year_max:.2f}")

    def exists(key_name: str) -> bool:
        try:
            s3.head_object(Bucket=bucket, Key=key_name)
            return True
        except Exception as exc:  # boto3 ClientError; avoid importing botocore just for 404 classification
            response = getattr(exc, "response", {})
            code = response.get("Error", {}).get("Code")
            status = response.get("ResponseMetadata", {}).get("HTTPStatusCode")
            if str(code) in {"404", "NoSuchKey", "NotFound"} or status == 404:
                return False
            raise

    def get_json(key_name: str):
        return json.loads(s3.get_object(Bucket=bucket, Key=key_name)["Body"].read())

    def put_json(key_name: str, obj) -> None:
        s3.put_object(
            Bucket=bucket,
            Key=key_name,
            Body=(json.dumps(obj, indent=2, sort_keys=True) + "\n").encode(),
            ContentType="application/json",
        )

    def segments(a: dt.date, b: dt.date):
        """Month-bounded [start,end) spans, retaining partial boundary months exactly."""
        cur = a
        while cur < b:
            if cur.month == 12:
                nxt = dt.date(cur.year + 1, 1, 1)
            else:
                nxt = dt.date(cur.year, cur.month + 1, 1)
            stop = min(nxt, b)
            yield cur, stop
            cur = stop

    receipt = {
        "schema": "NG_MBO_5Y_NATIVE_DBN_INGEST_V1",
        "label": label,
        "dataset": dataset,
        "symbol": symbol,
        "stype_in": stype,
        "data_schema": schema,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "year_quote_usd": quoted,
        "year_ceiling_usd": year_max,
        "native_dbn_preserved": True,
        "canonical_conversion_performed": False,
        "segments": [],
    }

    for seg_start, seg_end in segments(start, end):
        segment = f"{seg_start:%Y%m%d}_{seg_end:%Y%m%d}"
        done_key = f"{prefix}/_done/{segment}.done"
        job_key = f"{prefix}/_jobs/{segment}.json"
        manifest_key = f"{prefix}/manifests/{segment}.json"

        if exists(done_key) and exists(manifest_key):
            print(f"[resume] {segment} already complete", flush=True)
            receipt["segments"].append({"segment": segment, "status": "already_complete"})
            continue

        segment_quote = float(
            client.metadata.get_cost(
                dataset=dataset,
                symbols=[symbol],
                stype_in=stype,
                schema=schema,
                start=seg_start.isoformat(),
                end=seg_end.isoformat(),
            )
        )
        print(f"[quote] {segment} ${segment_quote:.8f}", flush=True)

        if exists(job_key):
            saved = get_json(job_key)
            jid = saved["job_id"]
            print(f"[resume] {segment} reuse job {jid}", flush=True)
        else:
            job = client.batch.submit_job(
                dataset=dataset,
                symbols=[symbol],
                stype_in=stype,
                schema=schema,
                start=seg_start.isoformat(),
                end=seg_end.isoformat(),
                encoding="dbn",
                compression="zstd",
                split_duration="day",
            )
            jid = job.get("id")
            if not jid:
                raise RuntimeError(f"no job id returned for {segment}: {job}")
            saved = {
                "job_id": jid,
                "segment": segment,
                "start": seg_start.isoformat(),
                "end": seg_end.isoformat(),
                "quote_usd": segment_quote,
                "submitted_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
                "dataset": dataset,
                "symbol": symbol,
                "stype_in": stype,
                "schema": schema,
            }
            # Durable before poll: a rerun reuses this job and does not silently rebuy the span.
            put_json(job_key, saved)
            print(f"[submit] {segment} job={jid}", flush=True)

        deadline = time.time() + 4.5 * 3600
        while True:
            details = client.batch.get_job_details(jid)
            state = details.get("state")
            print(f"[poll] {segment} job={jid} state={state}", flush=True)
            if state == "done":
                break
            if state in {"failed", "expired"}:
                raise RuntimeError(f"{segment} job {jid} state={state}")
            if time.time() > deadline:
                raise RuntimeError(
                    f"{segment} job {jid} polling deadline exceeded; rerun will reuse the saved job id"
                )
            time.sleep(30)

        with tempfile.TemporaryDirectory(prefix=f"ngmbo_{segment}_") as tmp:
            client.batch.download(jid, output_dir=tmp)
            files = sorted(glob.glob(os.path.join(tmp, "**", "*.dbn.zst"), recursive=True))
            if not files:
                raise RuntimeError(f"{segment} job {jid}: no .dbn.zst files downloaded")

            entries = []
            for file_path in files:
                path = Path(file_path)
                hasher = hashlib.sha256()
                size = 0
                with path.open("rb") as fh:
                    for chunk in iter(lambda: fh.read(8 * 1024 * 1024), b""):
                        hasher.update(chunk)
                        size += len(chunk)
                digest = hasher.hexdigest()

                # Read-only schema sanity probe. The native file itself is never rewritten.
                store = db.DBNStore.from_file(str(path))
                first_type = None
                saw_mbo = False
                for i, rec in enumerate(store):
                    rec_type = type(rec).__name__
                    first_type = first_type or rec_type
                    if rec_type == "MBOMsg":
                        saw_mbo = True
                        break
                    if i >= 999:
                        break
                if first_type is None:
                    raise RuntimeError(f"{path.name}: empty DBN file")
                if not saw_mbo:
                    raise RuntimeError(
                        f"{path.name}: no MBOMsg found in first 1000 records (first={first_type})"
                    )

                dest_key = f"{prefix}/native/{segment}/{path.name}"
                s3.upload_file(
                    str(path),
                    bucket,
                    dest_key,
                    ExtraArgs={
                        "Metadata": {
                            "sha256": digest,
                            "dataset": dataset,
                            "schema": schema,
                            "symbol": symbol,
                            "stype": stype,
                            "job_id": str(jid),
                            "segment": segment,
                        }
                    },
                )
                head = s3.head_object(Bucket=bucket, Key=dest_key)
                if int(head["ContentLength"]) != size:
                    raise RuntimeError(
                        f"{path.name}: S3 size mismatch local={size} remote={head['ContentLength']}"
                    )
                if head.get("Metadata", {}).get("sha256") != digest:
                    raise RuntimeError(f"{path.name}: S3 SHA-256 metadata mismatch")

                entries.append(
                    {
                        "file": path.name,
                        "s3_key": dest_key,
                        "bytes": size,
                        "sha256": digest,
                        "first_record_type_probe": first_type,
                        "mbo_probe": True,
                    }
                )
                print(
                    f"[upload] {segment} {path.name} bytes={size} sha256={digest[:16]}...",
                    flush=True,
                )

        manifest = {
            "schema": "NG_MBO_NATIVE_SEGMENT_MANIFEST_V1",
            "segment": segment,
            "dataset": dataset,
            "symbol": symbol,
            "stype_in": stype,
            "data_schema": schema,
            "start": seg_start.isoformat(),
            "end": seg_end.isoformat(),
            "job_id": jid,
            "quote_usd": segment_quote,
            "native_dbn_preserved": True,
            "files": entries,
            "completed_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        }
        put_json(manifest_key, manifest)
        s3.put_object(
            Bucket=bucket,
            Key=done_key,
            Body=(
                json.dumps({"segment": segment, "job_id": jid, "manifest": manifest_key}) + "\n"
            ).encode(),
        )
        receipt["segments"].append(
            {
                "segment": segment,
                "status": "complete",
                "job_id": jid,
                "quote_usd": segment_quote,
                "files": len(entries),
            }
        )

    receipt["completed_at_utc"] = dt.datetime.now(dt.timezone.utc).isoformat()
    local_receipt = Path(f"/tmp/{label}.json")
    local_receipt.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    put_json(f"{prefix}/year_receipts/{label}.json", receipt)
    print(json.dumps(receipt, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
