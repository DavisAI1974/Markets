"""Session adapter regressions using retained fake provider artifacts, no network."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest

from deploy.aws.box import frankie_box_classroom_cache as C
from deploy.aws.box import frankie_box_staged_reading as S
from deploy.aws.box import frankie_box_staged_session as A


class FakeSession:
    def __init__(self, root):
        self.work = Path(root)
        self.jobs = self.work / "jobs"
        self.jobs.mkdir()
        self.serverless = None
        self.engine = dict(served_model_name="retained-model", config_hash="c" * 64)
        self.served_model = "retained-model"
        self.request_sha256 = "a" * 64
        self.calls = []
        self.fail_after = None
        self.corrupt_prompt = False

    def _input_tokens(self, text):
        return len(text.encode("utf-8"))

    def _classroom_call(self, name, text, parse, lane):
        if self.fail_after is not None and len(self.calls) >= self.fail_after:
            raise RuntimeError("interrupted")
        meta = json.loads(text.split("Delivery binding and range:\n", 1)[1].split("\n", 1)[0])
        body = json.dumps(dict(ack={k: meta[k] for k in S.ACK_FIELDS}, assessment="Scoped assessment."))
        job_id = S.digest(dict(name=name, text=text))
        directory = self.jobs / job_id[:24]
        directory.mkdir()
        (directory / "prompt.txt").write_text(text + ("!" if self.corrupt_prompt else ""), encoding="utf-8")
        request = dict(name=name, body_sha256="d" * 64)
        outcome = dict(name=name, job_id=job_id, body_sha256="d" * 64,
                       result_status=200, text=body, incomplete=False, model="retained-model")
        raw = dict(choices=[dict(finish_reason="stop", message=dict(content=body))])
        for filename, value in (("request.json", request), ("outcome.json", outcome), ("result.json", raw)):
            (directory / filename).write_text(json.dumps(value), encoding="utf-8")
        self.calls.append((name, text))
        return parse(body), dict(attempt=name, job_id=job_id, lane=lane,
                                 prompt_sha256=S.witness(text)["sha256"], incomplete=False)

    def note(self, text):
        pass


def consume(session, cache, source="full history\n" * 500):
    return A.consume_sources(session, [dict(source_id="history", content=source)],
        role="scientific_teacher", phase="shared_knowledge", snapshot_hash="b" * 64,
        request_hash="a" * 64, cache=cache, task_instruction="Assess all supplied evidence.",
        input_budget=1900)


class StagedSessionTests(unittest.TestCase):
    def test_completed_cache_reuses_actual_exchanges_without_model_calls(self):
        with TemporaryDirectory() as directory:
            session = FakeSession(directory)
            cache = C.ClassroomCache(session.work / "cache", {"test": "identity"})
            first = consume(session, cache)
            calls = len(session.calls)
            second = consume(session, cache)
            self.assertEqual(first, second)
            self.assertEqual(calls, len(session.calls))
            self.assertGreater(calls, 1)
            self.assertEqual(first["status"], "complete")

    def test_partial_resume_calls_only_unfinished_parts(self):
        with TemporaryDirectory() as directory:
            session = FakeSession(directory)
            cache = C.ClassroomCache(session.work / "cache", {"test": "identity"})
            session.fail_after = 1
            with self.assertRaises(RuntimeError):
                consume(session, cache)
            completed = session.calls[0][0]
            session.fail_after = None
            result = consume(session, cache)
            self.assertEqual([name for name, _ in session.calls].count(completed), 1)
            self.assertEqual(result["status"], "complete")

    def test_actual_retained_prompt_is_checked_not_just_call_metadata(self):
        with TemporaryDirectory() as directory:
            session = FakeSession(directory)
            cache = C.ClassroomCache(session.work / "cache", {"test": "identity"})
            session.corrupt_prompt = True
            with self.assertRaises(ValueError):
                consume(session, cache, "evidence")

    def test_changed_source_creates_new_plan_and_preserves_old_cache_records(self):
        with TemporaryDirectory() as directory:
            session = FakeSession(directory)
            cache = C.ClassroomCache(session.work / "cache", {"test": "identity"})
            old = consume(session, cache, "first evidence")
            new = consume(session, cache, "second evidence")
            self.assertNotEqual(old["plan_hash"], new["plan_hash"])
            self.assertEqual(len(session.calls), 2)
            self.assertEqual(len(list(cache.directory.glob("staged-part-*.json"))), 2)


if __name__ == "__main__":
    unittest.main()
