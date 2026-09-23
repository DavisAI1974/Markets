"""Durable Session adapter for exact staged evidence delivery.

Uses the existing classroom-call guard and retained Pod/serverless job files.
It neither provisions an endpoint nor substitutes generated notes for sources.
"""
import importlib.util
import json
from pathlib import Path
import sys

try:
    from . import frankie_box_staged_reading as S
except ImportError:
    _name = "_frankie_box_staged_reading"
    S = sys.modules.get(_name)
    if S is None:
        _spec = importlib.util.spec_from_file_location(_name, Path(__file__).with_name("frankie_box_staged_reading.py"))
        S = importlib.util.module_from_spec(_spec)
        sys.modules[_name] = S
        _spec.loader.exec_module(S)


def _read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def retained_exchange(session, call, prompt, *, role, request_hash):
    """Read actual transport artifacts; do not trust call metadata alone."""
    name, job_id = call["attempt"], call["job_id"]
    if call.get("lane") == "reader" and getattr(session, "serverless", None) is not None:
        directory = session.work / "serverless-jobs" / name
    else:
        directory = session.jobs / job_id[:24]
    retained_prompt = (directory / "prompt.txt").read_bytes().decode("utf-8", errors="strict")
    request = _read(directory / "request.json")
    outcome = _read(directory / "outcome.json")
    raw_result = (directory / "result.json").read_bytes().decode("utf-8", errors="strict")
    result = json.loads(raw_result)
    if (retained_prompt != prompt or call.get("prompt_sha256") != S.witness(prompt)["sha256"]
            or request.get("name") != name or outcome.get("name") != name
            or not request.get("body_sha256")
            or request.get("body_sha256") != outcome.get("body_sha256")
            or (outcome.get("job_id") or outcome.get("runpod_job_id")) != job_id
            or outcome.get("error") or outcome.get("incomplete") or call.get("incomplete")
            or outcome.get("result_status") != 200):
        raise ValueError("retained completed provider exchange does not match staged call")
    choices = result.get("choices")
    if (not isinstance(choices, list) or len(choices) != 1
            or choices[0].get("finish_reason") != "stop"):
        raise ValueError("provider result did not finish normally")
    response = outcome.get("text")
    if not isinstance(response, str) or not response.strip():
        raise ValueError("retained provider response is empty")
    if choices[0].get("message", {}).get("content") != response:
        raise ValueError("retained provider response differs from the raw result")
    # The established transport extracts final_text; its saved outcome is the
    # response consumed by the classroom parser. Keep both witnesses.
    return dict(prompt=dict(S.witness(retained_prompt), content=retained_prompt),
                response=dict(S.witness(response), content=response),
                provider_job=dict(id=job_id, status="completed", role=role,
                    request_hash=request_hash, prompt_sha256=S.witness(prompt)["sha256"],
                    response_sha256=S.witness(response)["sha256"],
                    result_sha256=S.witness(raw_result)["sha256"],
                    body_sha256=request["body_sha256"], model=outcome.get("model"),
                    transport="serverless" if outcome.get("runpod_job_id") else "pod",
                    incomplete=False))


def consume_sources(session, sources, role, phase, snapshot_hash, request_hash,
                    cache, task_instruction, *, input_budget=87000):
    """Deliver every source range and return a fully inline validated receipt.

    Sources use {source_id (or id), content:str|UTF8bytes[,sha256,bytes]}.
    Caller supplies the existing ClassroomCache. Cache entries are plan/part
    bound; completed parts resume without another provider call. All source
    ranges and raw exchanges remain in the returned receipt and durable cache.
    """
    if not isinstance(task_instruction, str) or not task_instruction.strip():
        raise ValueError("nonempty staged task instruction required")
    engine = getattr(session, "engine", None) or {}
    model = engine.get("served_model_name") or getattr(session, "served_model", None)
    binding = dict(role=role, phase=phase, request_hash=request_hash,
                   snapshot_hash=snapshot_hash, model_identity=model)
    header = lambda meta: (
        "You are acting as " + role + " in phase " + phase + ".\n" +
        task_instruction + "\nAssess only the supplied source range in this call. "
        "Other ranges are separate completed exchanges; do not claim to have them "
        "in this call or replace their exact evidence with an invented summary.")
    manifest, prompts = S.plan_sources(sources, header, session._input_tokens,
                                      input_budget, binding=binding)

    def one(part):
        part_id = part["part_id"]
        prompt = prompts[part_id]
        filename = "staged-part-" + manifest["plan_hash"][:16] + "-" + part_id[:24] + ".json"
        retained = cache.load(filename, prompt)
        if retained is not None:
            return S.validate_part(manifest, part_id, retained["receipt"])
        expected = {k: part[k] for k in S.ACK_FIELDS}

        def parse(text):
            try:
                answer = json.loads(text)
                if (not isinstance(answer, dict) or S.digest(answer.get("ack")) != S.digest(expected)
                        or not isinstance(answer.get("assessment"), str) or not answer["assessment"].strip()):
                    raise ValueError("exact source acknowledgement and nonempty assessment required")
                return answer
            except (ValueError, TypeError) as exc:
                # Match the existing Session guard's exception identity when
                # running through its real module loader.
                loader = getattr(sys.modules.get(session.__class__.__module__), "classroom_module", None)
                if loader is not None:
                    raise loader().ClassroomOutput(str(exc)) from exc
                raise ValueError(str(exc)) from exc

        name = "staged-" + manifest["plan_hash"][:16] + "-" + part_id[:24]
        _, call = session._classroom_call(name, prompt, parse, "reader")
        exchange = retained_exchange(session, call, prompt, role=role, request_hash=request_hash)
        actual = json.loads(exchange["response"]["content"])
        receipt = dict(part_id=part_id, plan_hash=manifest["plan_hash"], binding=binding,
                       source_offset=part["source_offset"], ack=actual.get("ack"), **exchange)
        receipt = S.validate_part(manifest, part_id, receipt)
        cache.save(filename, prompt, dict(schema="FRANKIE_STAGED_PART_CACHE_V1", receipt=receipt))
        return receipt

    if hasattr(session, "_fan_out"):
        receipts = session._fan_out("staged " + role + " " + phase, manifest["parts"], one)
    else:
        receipts = [one(part) for part in manifest["parts"]]
    return S.assemble_parts(manifest, receipts)
