from pathlib import Path

ADAPTER = Path('research/kalshi/frankie_raw_mbo_benchmark/native_candidate_adapter.py')


def once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    assert count == 1, f'{label}: expected one match, got {count}'
    return text.replace(old, new, 1)


text = ADAPTER.read_text(encoding='utf-8')

# Task C: use the validated Section-2 carrier at the existing recognition call site.
old = 'from research.kalshi.frankie_raw_mbo_benchmark.native_candidate import Candidate\n'
new = old + '''from research.kalshi.frankie_raw_mbo_benchmark.native_clocks import (\n    CAUSAL_CLOCK,\n    RecognitionLabel,\n)\n'''
text = once(text, old, new, 'RecognitionLabel import')

old = '''    recognition: CandidateRecognition\n    orientation: str\n'''
new = '''    recognition: CandidateRecognition\n    recognition_label: RecognitionLabel\n    orientation: str\n'''
text = once(text, old, new, 'episode validated label field')

old = '''        else:\n            # H+N by construction, with N the detection lag. See the module docstring: a\n            # candidate whose birth is its own detection cannot be recognised before it.\n            # The instant is the candidate lane's SECOND BIN, not an F_LAST receive, and the\n            # basis says so on the record (S121 item one).\n            record.record_call(recv_ns=available_ns, basis=RECOGNIZED_BASIS_AVAILABLE_SECOND_BIN)\n\n        # 4.12 REFUSES an orientation outside {SAME, FLIP}, and it is right to. A segment's\n'''
new = '''        else:\n            # H+N by construction, with N the detection lag. See the module docstring: a\n            # candidate whose birth is its own detection cannot be recognised before it.\n            # The instant is the candidate lane's SECOND BIN, not an F_LAST receive, and the\n            # basis says so on the record (S121 item one).\n            record.record_call(recv_ns=available_ns, basis=RECOGNIZED_BASIS_AVAILABLE_SECOND_BIN)\n\n        # Section 2's typed carrier validates the outcome/time pair at the production caller.\n        # CandidateRecognition still owns first-call bookkeeping and all of its existing fields;\n        # this object adds the invariant check and canonical lead = reference - observed beside it.\n        if record.outcome is None or record.recognized_recv_ns is None:\n            raise CandidateAdapterError(\n                f"candidate {candidate.candidate_id} record_call produced no recognition instant"\n            )\n        recognition_label = RecognitionLabel(\n            label=record.outcome,\n            clock=CAUSAL_CLOCK,\n            reference_ns=birth_ns,\n            observed_ns=record.recognized_recv_ns,\n        )\n\n        # 4.12 REFUSES an orientation outside {SAME, FLIP}, and it is right to. A segment's\n'''
text = once(text, old, new, 'validate recognition after record_call')

old = '''            candidate=candidate,\n            stages=[stage] if stage is not None else [],\n            recognition=record,\n            orientation=orientation,\n'''
new = '''            candidate=candidate,\n            stages=[stage] if stage is not None else [],\n            recognition=record,\n            recognition_label=recognition_label,\n            orientation=orientation,\n'''
text = once(text, old, new, 'store validated label on episode')

old = '''            "recognition_outcome": record.outcome,\n            # S121 item one: the instant the call was knowable and the clock it is on, so the\n'''
new = '''            "recognition_outcome": record.outcome,\n            "recognition_label": recognition_label.as_dict(),\n            # S121 item one: the instant the call was knowable and the clock it is on, so the\n'''
text = once(text, old, new, 'open row adds validated label')

old = '''        recognition_row = self.recognition.record(episode.recognition)\n        if completed:\n'''
new = '''        recognition_row = self.recognition.record(episode.recognition)\n        recognition_row["recognition_label"] = episode.recognition_label.as_dict()\n        if completed:\n'''
text = once(text, old, new, 'closed recognition output adds validated label')

ADAPTER.write_text(text, encoding='utf-8')
