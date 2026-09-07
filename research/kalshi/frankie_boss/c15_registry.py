"""Owner-directed full-evidence contract; replaces the reduced C15R2 draft."""
import hashlib
from pathlib import Path

try:
    from .c15_journal import SCHEMA, evidence_hash
except ImportError:
    from c15_journal import SCHEMA, evidence_hash


def implementation_identity():
    here = Path(__file__).parent
    files = [here / name for name in (
        "c15_builder.py", "c15_observer.py", "c15_journal.py", "c15_registry.py",
        "causal_prefix.py", "causal_prefix_records.py", "causal_packet.py", "mbo_resume_state.py")]
    files.append(here.parents[1] / "ng_exhaustion_mbo_v4_state_adapter_20260820.py")
    hashes = {}
    for path in files:
        data = path.read_bytes()
        hashes[path.name] = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
    return dict(schema=SCHEMA, code_blobs=hashes,
                contract_hash=evidence_hash(dict(schema=SCHEMA, retention="all supplied evidence",
                                                  reductions=[], fields="all original fields")))
