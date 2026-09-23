"""Shared knowledge regression contract. Synthetic fixtures; no provider calls."""
import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from research.kalshi.frankie_boss import dipole_shared_knowledge as knowledge


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def witnessed(text):
    raw = text.encode("utf-8")
    return dict(content=text, bytes=len(raw), sha256=sha(raw))


class SharedKnowledgeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.payloads = {
            "baseline": b'{"cutoff_ns":1633305600000000001}\r\n',
            "correction": "Old claim withdrawn; evidence remains. α\n".encode("utf-8"),
        }
        self.catalog = dict(
            schema="FRANKIE_SHARED_KNOWLEDGE_CATALOG_V1", version="fixture-v1",
            groups=[dict(id="K01", status="RECALCULATION_NEEDED",
                         explanation="Preserve the failed construction and the correction.")],
            sources=[
                dict(id=name, path="research/" + name + ".txt", revision="a" * 40,
                     sha256=sha(raw), bytes=len(raw), status="SUPERSEDED" if name == "baseline" else "CURRENT",
                     explanation="Historical evidence, not automatic promotion.", required=True,
                     access="SHARED_RESEARCH", provenance={"repository": "DavisAI1974/Markets"},
                     supersedes=["baseline"] if name == "correction" else [])
                for name, raw in self.payloads.items()
            ],
        )

    def build(self, catalog=None, name="snapshot"):
        return knowledge.build_snapshot(
            catalog or self.catalog, lambda entry: self.payloads[entry["id"]], self.root / name)

    def receipt(self, snapshot, role="principal", request_hash="b" * 64):
        binding = dict(role=role, phase="shared_knowledge", request_hash=request_hash,
                       snapshot_hash=snapshot.snapshot_hash, model_identity="fixture-reader")
        parts = []
        for number, entry in enumerate(snapshot.sources):
            source = knowledge.read_source(snapshot, entry["id"], 0, entry["bytes"])
            ack = dict(part_id="part-" + str(number), source_id=entry["id"], start=0,
                       end=entry["bytes"], source_sha256=entry["sha256"],
                       chunk_sha256=source["chunk_sha256"])
            prefix = json.dumps(dict(binding=binding, ack=ack), sort_keys=True) + "\nSOURCE:\n"
            prompt = witnessed(prefix + source["content"] + "\nEND SOURCE\n")
            response = witnessed(json.dumps(dict(ack=ack, assessment="Historical finding read with its caveats."),
                                             sort_keys=True))
            parts.append(dict(**ack, source_offset=len(prefix.encode("utf-8")), prompt=prompt,
                              response=response, ack=ack,
                              provider_job=dict(id="actual-fixture-job-" + str(number), status="completed",
                                  role=role, request_hash=request_hash,
                                  prompt_sha256=prompt["sha256"], response_sha256=response["sha256"])))
        return dict(schema="FRANKIE_STAGED_READING_RECEIPT_V1", binding=binding,
                    plan_hash="c" * 64, parts=parts)

    def validate(self, snapshot, receipt, role="principal"):
        return knowledge.validate_reading(snapshot, receipt, role, "b" * 64)

    def test_exact_source_bytes_statuses_and_supersession_survive_roundtrip(self):
        snapshot = self.build()
        again = knowledge.load_snapshot(snapshot.directory, snapshot.snapshot_hash)
        self.assertEqual(again.catalog, self.catalog)
        for name, raw in self.payloads.items():
            part = knowledge.read_source(again, name, 0, len(raw))
            self.assertEqual(part["content"].encode("utf-8"), raw)
            self.assertEqual(part["source_sha256"], sha(raw))
            self.assertTrue(part["eof"])
        self.assertIn("1633305600000000001", knowledge.read_source(
            again, "baseline", 0, 1000)["content"])

    def test_same_snapshot_build_is_idempotent_without_resolving_again(self):
        first = self.build()
        def forbidden(_):
            self.fail("Already verified immutable snapshot must not fetch again")
        again = knowledge.build_snapshot(self.catalog, forbidden, first.directory)
        self.assertEqual(first.snapshot_hash, again.snapshot_hash)

    def test_catalog_revision_cannot_replace_an_existing_snapshot(self):
        first = self.build()
        changed = copy.deepcopy(self.catalog)
        changed["sources"][0]["explanation"] = "New interpretation"
        with self.assertRaisesRegex(ValueError, "snapshot"):
            knowledge.build_snapshot(changed, lambda e: self.payloads[e["id"]], first.directory)
        second = self.build(changed, "snapshot-v2")
        self.assertNotEqual(first.snapshot_hash, second.snapshot_hash)
        self.assertEqual(knowledge.load_snapshot(first.directory, first.snapshot_hash).catalog, self.catalog)

    def test_all_source_deficiencies_are_reported_and_no_snapshot_published(self):
        def unavailable(entry):
            if entry["id"] == "baseline":
                raise FileNotFoundError("original source unavailable")
            return b"wrong version"
        with self.assertRaises(knowledge.KnowledgeIncomplete) as caught:
            knowledge.build_snapshot(self.catalog, unavailable, self.root / "incomplete")
        self.assertEqual({d["source_id"] for d in caught.exception.deficiencies},
                         {"baseline", "correction"})
        self.assertFalse((self.root / "incomplete" / "MANIFEST.json").exists())

    def test_hash_and_size_are_independently_checked(self):
        for field, value in (("sha256", "f" * 64), ("bytes", 1)):
            with self.subTest(field=field):
                changed = copy.deepcopy(self.catalog)
                changed["sources"][0][field] = value
                with self.assertRaises(knowledge.KnowledgeIncomplete):
                    self.build(changed, "bad-" + field)

    def test_current_teacher_key_and_unreviewed_access_are_refused(self):
        for changes in ({"path": "classroom-audit/dipole-classroom-teacher-key.audit.json"},
                        {"access": "HOST_ONLY"}):
            with self.subTest(changes=changes):
                changed = copy.deepcopy(self.catalog)
                changed["sources"][0].update(changes)
                with self.assertRaisesRegex(ValueError, "shared|teacher"):
                    self.build(changed)

    def test_duplicate_id_invalid_digest_and_path_escape_are_refused(self):
        cases = [
            lambda c: c["sources"].append(copy.deepcopy(c["sources"][0])),
            lambda c: c["sources"][0].update(sha256="abc"),
            lambda c: c["sources"][0].update(path="../private.txt"),
            lambda c: c["sources"][0].update(required=False),
            lambda c: c["sources"][0].update(bytes=True),
        ]
        for mutate in cases:
            with self.subTest(mutate=mutate):
                changed = copy.deepcopy(self.catalog)
                mutate(changed)
                with self.assertRaises(ValueError):
                    self.build(changed)

    def test_changed_source_or_manifest_invalidates_an_existing_handle(self):
        snapshot = self.build()
        target = snapshot.directory / "sources" / self.catalog["sources"][0]["sha256"]
        target.write_bytes(b"mutated")
        with self.assertRaisesRegex(ValueError, "source"):
            knowledge.read_source(snapshot, "baseline", 0, 20)
        with self.assertRaises(ValueError):
            knowledge.load_snapshot(snapshot.directory, snapshot.snapshot_hash)

    def test_source_symlink_is_not_accepted(self):
        snapshot = self.build()
        target = snapshot.directory / "sources" / self.catalog["sources"][0]["sha256"]
        outside = self.root / "outside"
        outside.write_bytes(target.read_bytes())
        target.unlink()
        target.symlink_to(outside)
        with self.assertRaisesRegex(ValueError, "symlink"):
            knowledge.load_snapshot(snapshot.directory, snapshot.snapshot_hash)

    def test_utf8_chunks_never_replace_or_skip_bytes(self):
        snapshot = self.build()
        raw = self.payloads["correction"]
        position, assembled = 0, b""
        while position < len(raw):
            part = knowledge.read_source(snapshot, "correction", position, 5)
            self.assertLessEqual(part["bytes"], 5)
            assembled += part["content"].encode("utf-8")
            self.assertGreater(part["next_byte_start"], position)
            position = part["next_byte_start"]
        self.assertEqual(assembled, raw)
        alpha = raw.index("α".encode("utf-8"))
        with self.assertRaisesRegex(ValueError, "UTF-8"):
            knowledge.read_source(snapshot, "correction", alpha + 1, 5)
        with self.assertRaisesRegex(ValueError, "UTF-8"):
            knowledge.read_source(snapshot, "correction", alpha, 1)

    def test_both_roles_need_their_own_complete_delivery(self):
        snapshot = self.build()
        for role in ("principal", "scientific_teacher"):
            result = self.validate(snapshot, self.receipt(snapshot, role), role)
            self.assertEqual(result["status"], "complete")
            self.assertEqual(result["source_ids"], ["baseline", "correction"])
        with self.assertRaisesRegex(ValueError, "binding"):
            self.validate(snapshot, self.receipt(snapshot), "scientific_teacher")

    def test_omitted_source_or_gap_or_duplicate_cannot_count_as_complete(self):
        snapshot = self.build()
        original = self.receipt(snapshot)
        variants = [original["parts"][:-1],
                    original["parts"] + [copy.deepcopy(original["parts"][0])]]
        for parts in variants:
            broken = dict(original, parts=parts)
            with self.assertRaises(ValueError):
                self.validate(snapshot, broken)
        broken = copy.deepcopy(original)
        broken["parts"][0]["start"] = 1
        with self.assertRaises(ValueError):
            self.validate(snapshot, broken)

    def test_forged_prompt_or_response_or_job_or_ack_is_refused(self):
        snapshot = self.build()
        changes = [
            lambda r: r["binding"].update(request_hash="e" * 64),
            lambda r: r["binding"].update(snapshot_hash="e" * 64),
            lambda r: r["parts"][0]["prompt"].update(content="summary only"),
            lambda r: r["parts"][0]["response"].update(content="unwitnessed response"),
            lambda r: r["parts"][0]["provider_job"].update(status="incomplete"),
            lambda r: r["parts"][0]["provider_job"].update(prompt_sha256="e" * 64),
            lambda r: r["parts"][0]["provider_job"].update(role="scientific_teacher"),
            lambda r: r["parts"][0]["ack"].update(end=0),
            lambda r: r["parts"][0].update(source_offset=0),
        ]
        for mutate in changes:
            with self.subTest(mutate=mutate):
                broken = self.receipt(snapshot)
                mutate(broken)
                with self.assertRaises(ValueError):
                    self.validate(snapshot, broken)

    def test_rehashed_summary_cannot_impersonate_delivery_of_original_source(self):
        snapshot = self.build()
        receipt = self.receipt(snapshot)
        part = receipt["parts"][0]
        part["prompt"] = witnessed("A summary of the historical finding, without its original bytes.")
        part["provider_job"]["prompt_sha256"] = part["prompt"]["sha256"]
        with self.assertRaisesRegex(ValueError, "source"):
            self.validate(snapshot, receipt)

    def test_response_ack_must_be_in_retained_actual_response(self):
        snapshot = self.build()
        receipt = self.receipt(snapshot)
        part = receipt["parts"][0]
        part["response"] = witnessed(json.dumps(dict(ack={}, assessment="I read something else.")))
        part["provider_job"]["response_sha256"] = part["response"]["sha256"]
        with self.assertRaisesRegex(ValueError, "ack"):
            self.validate(snapshot, receipt)


    def test_descriptor_is_portable_and_detects_catalog_or_projection_tampering(self):
        snapshot = self.build()
        value = knowledge.descriptor(snapshot)
        self.assertEqual(knowledge.validate_descriptor(value), value)
        self.assertEqual(value["snapshot_hash"], snapshot.snapshot_hash)
        self.assertEqual(value["catalog_hash"], sha(json.dumps(
            snapshot.catalog, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")))
        for field in ("catalog", "sources", "snapshot_hash", "catalog_hash"):
            broken = copy.deepcopy(value)
            if field == "catalog":
                broken[field]["sources"][0]["status"] = "PROMOTED"
            elif field == "sources":
                broken[field] = broken[field][:-1]
            else:
                broken[field] = "e" * 64
            with self.subTest(field=field), self.assertRaises(ValueError):
                knowledge.validate_descriptor(broken)

    def test_scientific_review_requires_full_additional_response_and_history(self):
        snapshot = self.build()
        receipt = self.receipt(snapshot, "scientific_teacher")
        receipt["binding"]["phase"] = "scientific_review"
        additional = [dict(source_id="initial-response", content="Initial claims. α\n"),
                      dict(source_id="completed-history", content="All prior learning, including old corrections.\n")]
        for source in additional:
            raw = source["content"].encode("utf-8")
            ack = dict(part_id=source["source_id"], source_id=source["source_id"],
                       start=0, end=len(raw), source_sha256=sha(raw), chunk_sha256=sha(raw))
            prefix = json.dumps(dict(binding=receipt["binding"], ack=ack), sort_keys=True) + "\n"
            prompt = witnessed(prefix + source["content"])
            response = witnessed(json.dumps(dict(ack=ack, assessment="Reviewed supplied evidence.")))
            receipt["parts"].append(dict(**ack, ack=ack, source_offset=len(prefix.encode("utf-8")),
                prompt=prompt, response=response, provider_job=dict(
                    id="job-" + source["source_id"], status="completed", role="scientific_teacher",
                    request_hash="b" * 64, prompt_sha256=prompt["sha256"], response_sha256=response["sha256"])))
        result = knowledge.validate_reading(snapshot, receipt, "scientific_teacher", "b" * 64,
            additional_sources=additional, expected_phase="scientific_review")
        self.assertEqual(result["source_ids"][-2:], ["initial-response", "completed-history"])
        for changed in (additional[:-1], [dict(additional[0], content="changed"), additional[1]]):
            with self.assertRaises(ValueError):
                knowledge.validate_reading(snapshot, receipt, "scientific_teacher", "b" * 64,
                    additional_sources=changed, expected_phase="scientific_review")
        with self.assertRaisesRegex(ValueError, "binding"):
            knowledge.validate_reading(snapshot, receipt, "scientific_teacher", "b" * 64,
                additional_sources=additional)

    def test_additional_source_cannot_shadow_snapshot(self):
        snapshot = self.build()
        with self.assertRaisesRegex(ValueError, "duplicate"):
            knowledge.validate_reading(snapshot, self.receipt(snapshot), "principal", "b" * 64,
                additional_sources=[dict(id="baseline", content="replacement")])


if __name__ == "__main__":
    unittest.main()
