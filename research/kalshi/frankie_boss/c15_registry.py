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


# Greg, 2026-10-09 (standing): the code version is RECORDED, NEVER COMPARED. implementation_identity()'s code_blobs (the
# git-blob sha1 of the nine files above) are written into every C15 checkpoint state as a record; a saved state is
# accepted on its FORMAT: the schema, the evidence contract (contract_hash) and IMPLEMENTATION_FORMAT, an integer bumped
# ONLY when the saved state's format (adapter / prefix / session / journal encoding) changes. A saved identity without
# a 'format' field carries format 1 (every state written up to 2026-10-09); when the format is bumped, write 'format'
# into implementation_identity() as well.
IMPLEMENTATION_FORMAT = 1


def implementation_accepts(saved):
    """True when a saved implementation identity is of this checkout's format (schema, contract_hash and format equal);
    its code_blobs are recorded, never compared."""
    if not isinstance(saved, dict) or not isinstance(saved.get("code_blobs"), dict):
        return False
    current = implementation_identity()
    return (saved.get("schema") == current["schema"] and saved.get("contract_hash") == current["contract_hash"]
            and saved.get("format", 1) == IMPLEMENTATION_FORMAT)

