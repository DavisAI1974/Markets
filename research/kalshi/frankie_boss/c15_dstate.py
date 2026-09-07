"""Isolated C15 D1-D6 geometry: R2 §5, corrected R3 addendum §4.1.

No book, anchor, lifecycle, normalization, observer, or builder is implemented
here. The caller supplies the already selected far-side price and anchor.
``advance_synthetic`` is the mechanics seam; ``ReceiptDChain`` binds an
explicit RecordPrefixChain authority. Receipt binding proves prefix identity,
not derivation of the supplied book/anchor values (the later observer owns
that proof). One consumer owns one publisher/instrument for one source scope.

C1 remains deferred under addendum §7 despite its clarified §4.2 semantics.
The last completed duration is captured at completion, as in R2 §5.4's
``duration_last`` tuple; a later unarmed extreme cannot rewrite that step.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from fractions import Fraction
import hashlib
import math
import re

try:
    from .causal_packet import canonical_bytes
    from .causal_prefix_records import RecordGroupReceipt, RecordPrefixChain
except ImportError:
    from causal_packet import canonical_bytes
    from causal_prefix_records import RecordGroupReceipt, RecordPrefixChain


SCHEMA = "C15_DCHAIN_R3_V1"
P_PULLBACK_TICKS = 1
R_BREAK_TICKS = 3


def _int(value, name, minimum=0):
    if type(value) is not int or value < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}")
    return value


def _hash(domain, payload):
    return hashlib.sha256(domain.encode() + b"\0" + canonical_bytes(payload)).hexdigest()


@dataclass(frozen=True)
class DObservation:
    group_ordinal: int
    source_member_index: int
    session_id: str
    anchor_dir: int | None
    far_best_price_raw: int | None
    book_integrity: bool

    def __post_init__(self):
        _int(self.group_ordinal, "group_ordinal")
        _int(self.source_member_index, "source_member_index")
        if not isinstance(self.session_id, str) or not self.session_id:
            raise ValueError("session_id must be a nonempty string")
        if self.anchor_dir is not None and (
            type(self.anchor_dir) is not int or self.anchor_dir not in (-1, 1)
        ):
            raise ValueError("anchor_dir must be -1, +1, or None")
        if self.far_best_price_raw is not None and type(self.far_best_price_raw) is not int:
            raise ValueError("far_best_price_raw must be an integer or None")
        if type(self.book_integrity) is not bool:
            raise ValueError("book_integrity must be boolean")


@dataclass(frozen=True)
class DState:
    anchor_dir: int | None = None
    E: Fraction | None = None
    E_prev: Fraction | None = None
    armed: bool = False
    broken: bool = False
    pull_depth: Fraction = Fraction(0)
    n_ext: int = 0
    m_last: Fraction | None = None
    m_prev: Fraction | None = None
    p_last: Fraction | None = None
    p_prev: Fraction | None = None
    g_E: int | None = None
    g_E_prev: int | None = None
    age: int = 0
    duration_last: int | None = None


@dataclass(frozen=True)
class DValue:
    value: float
    state: str
    reason: str | None = None


@dataclass(frozen=True)
class DOutput:
    """D1..D6 in fixed order; immutable diagnostic snapshot, no normalization."""
    columns: tuple[DValue, ...]
    state: DState


def _present(value):
    if not math.isfinite(value):
        raise ValueError("nonfinite PRESENT D value is a builder defect")
    return DValue(float(value), "PRESENT")


def _absent(state, reason):
    return DValue(0.0, state, reason)


def _columns(s):
    unavailable = "CHAIN_BROKEN" if s.broken else "NO_COMPLETED_STEP"
    missing = _absent("MISSING", unavailable)
    ratio = missing
    if s.n_ext >= 2:
        ratio = (_absent("INVALID", "DEGENERATE_STEP") if s.m_prev == 0 else
                 _present(math.log(s.m_last / s.m_prev)))
    return (
        _present(math.log1p(s.age)), _present(math.log1p(s.n_ext)), ratio,
        _present(math.log1p(s.p_last)) if s.n_ext >= 1 else missing,
        _present(math.log1p(s.duration_last)) if s.n_ext >= 1 else missing,
        _present(math.log1p(s.p_prev)) if s.n_ext >= 2 else missing,
    )


def _transition(s, o, tick_raw):
    # Undefined anchors freeze before direction comparison. An invalid book or
    # unknown tick similarly cannot mutate geometry.
    if o.anchor_dir is None:
        return DOutput((_absent("MISSING", "SIDE_UNDEFINED"),) * 6, s)
    if tick_raw is None:
        return DOutput((_absent("INVALID", "TICK_UNKNOWN"),) * 6, s)
    if not o.book_integrity or o.far_best_price_raw is None:
        return DOutput((_absent("INVALID", "BOOK_INTEGRITY"),) * 6, s)
    # Exact rational comparisons avoid tick rounding before threshold tests.
    x = o.anchor_dir * Fraction(o.far_best_price_raw, tick_raw)
    i = o.group_ordinal
    if s.anchor_dir != o.anchor_dir:
        s = DState(anchor_dir=o.anchor_dir, E=x, g_E=i)
    elif x <= s.E:
        s = replace(s, age=s.age + 1)
        if x < s.E:
            depth = max(s.pull_depth, s.E - x)
            s = replace(s, pull_depth=depth)
            if not s.broken:
                s = replace(s, armed=s.armed or depth >= P_PULLBACK_TICKS)
                if depth >= R_BREAK_TICKS:
                    s = replace(s, broken=True, armed=False, n_ext=0,
                                E_prev=None, m_last=None, m_prev=None,
                                p_last=None, p_prev=None, g_E_prev=None,
                                duration_last=None)
    else:
        if s.broken:
            s = replace(s, broken=False, n_ext=0)
        elif s.armed:
            s = replace(s, n_ext=s.n_ext + 1, E_prev=s.E,
                        m_prev=s.m_last, m_last=x - s.E,
                        p_prev=s.p_last, p_last=s.pull_depth,
                        g_E_prev=s.g_E, duration_last=i - s.g_E)
        s = replace(s, E=x, g_E=i, age=0, armed=False, pull_depth=Fraction(0))
    return DOutput(_columns(s), s)


class DChain:
    """Single-instrument mechanics machine; the tick is immutable configuration.

    Ordinals count every instrument group, including frozen groups. ``age``
    follows the specified frozen-state rule; duration uses group ordinals.
    Scope boundaries reset even if the first new-scope anchor is undefined.
    No checkpoint/export API is part of this isolated lane.
    """

    def __init__(self, *, tick_raw: int | None):
        if tick_raw is not None:
            _int(tick_raw, "tick_raw", 1)
        self._tick_raw = tick_raw
        self._state = DState()
        self._ordinal = -1
        self._member = None
        self._session = None

    def advance_synthetic(self, observation: DObservation) -> DOutput:
        """Consume one caller-supplied group; never creates provenance authority."""
        if not isinstance(observation, DObservation):
            raise ValueError("expected DObservation")
        if observation.group_ordinal != self._ordinal + 1:
            raise ValueError("instrument groups must start at zero and advance without gaps")
        if self._member is not None and observation.source_member_index < self._member:
            raise ValueError("source member cannot regress")
        boundary = (observation.source_member_index != self._member or
                    observation.session_id != self._session)
        state = DState() if boundary else self._state
        output = _transition(state, observation, self._tick_raw)
        # Transactional: validation and all arithmetic precede mutation.
        self._state = output.state
        self._ordinal = observation.group_ordinal
        self._member = observation.source_member_index
        self._session = observation.session_id
        return output


@dataclass(frozen=True)
class DReceiptOutput:
    output: DOutput
    builder_code_sha: str
    config_hash: str
    terminal_prefix_hash: str
    receipt_hash: str
    dstate_receipt_hash: str


class ReceiptDChain:
    """Explicit chain-context consumer; no adapter/observer installation.

    The constructing caller supplies the verified git blob SHA of this module.
    Session identity and derived anchor/book values are caller evidence, not
    inferred from a record receipt. Those derivation proofs are integration work.
    """

    def __init__(self, chain: RecordPrefixChain, *, instrument_id: int,
                 publisher_id: int, tick_raw: int | None, builder_code_sha: str):
        if not isinstance(chain, RecordPrefixChain):
            raise ValueError("expected authoritative RecordPrefixChain")
        self._instrument = _int(instrument_id, "instrument_id")
        self._publisher = _int(publisher_id, "publisher_id")
        if not isinstance(builder_code_sha, str) or not re.fullmatch(r"[0-9a-f]{40}", builder_code_sha):
            raise ValueError("builder_code_sha must be a git blob SHA")
        self._chain = chain
        self._machine = DChain(tick_raw=tick_raw)
        self._code_sha = builder_code_sha
        self._config_hash = _hash(SCHEMA + "/CONFIG", dict(
            schema=SCHEMA, instrument_id=instrument_id, publisher_id=publisher_id,
            tick_raw=tick_raw, p_pullback_ticks=P_PULLBACK_TICKS,
            r_break_ticks=R_BREAK_TICKS))

    def advance(self, receipt: RecordGroupReceipt, *, session_id: str,
                anchor_dir: int | None, far_best_price_raw: int | None,
                book_integrity: bool) -> DReceiptOutput:
        self._chain.validate_result_bearing(receipt)
        return self._advance_bound(receipt, session_id, anchor_dir,
                                   far_best_price_raw, book_integrity)

    def advance_probe(self, receipt: RecordGroupReceipt, *, session_id: str,
                      anchor_dir: int | None, far_best_price_raw: int | None,
                      book_integrity: bool) -> DReceiptOutput:
        """Mechanics lane with the same trusted-chain check and no promotion."""
        self._chain.validate_probe(receipt)
        return self._advance_bound(receipt, session_id, anchor_dir,
                                   far_best_price_raw, book_integrity)

    def _advance_bound(self, receipt, session_id, anchor_dir,
                       far_best_price_raw, book_integrity):
        if (receipt.instrument_id, receipt.publisher_id) != (self._instrument, self._publisher):
            raise ValueError("receipt publisher/instrument does not match consumer")
        observation = DObservation(receipt.instrument_group_ordinal,
                                   receipt.source_member_index, session_id, anchor_dir,
                                   far_best_price_raw, book_integrity)
        output = self._machine.advance_synthetic(observation)
        bound = dict(schema=SCHEMA, builder_code_sha=self._code_sha,
                     config_hash=self._config_hash, receipt_hash=receipt.receipt_hash,
                     terminal_prefix_hash=receipt.terminal_prefix_hash,
                     observation=asdict(observation), columns=[asdict(v) for v in output.columns])
        return DReceiptOutput(output, self._code_sha, self._config_hash,
                              receipt.terminal_prefix_hash, receipt.receipt_hash,
                              _hash(SCHEMA + "/RECEIPT", bound))

    def export_state(self):
        """Exact bounded geometry; the outer C15 checkpoint supplies authority."""
        state = {key: ([value.numerator, value.denominator]
                       if isinstance(value, Fraction) else value)
                 for key, value in asdict(self._machine._state).items()}
        payload = dict(schema=SCHEMA, code_sha=self._code_sha,
                       config_hash=self._config_hash,
                       machine=dict(state=state, ordinal=self._machine._ordinal,
                                    member=self._machine._member,
                                    session=self._machine._session))
        return {**payload, "state_hash": _hash(SCHEMA + "/STATE", payload)}

    @classmethod
    def restore(cls, chain, payload, **config):
        """Restore only inside a hash-bound, trusted outer checkpoint envelope."""
        machine = cls(chain, **config)
        if (type(payload) is not dict or set(payload) !=
                {"schema", "code_sha", "config_hash", "machine", "state_hash"}):
            raise ValueError("invalid D checkpoint fields")
        body = {k: v for k, v in payload.items() if k != "state_hash"}
        if (payload["schema"] != SCHEMA or payload["code_sha"] != machine._code_sha
                or payload["config_hash"] != machine._config_hash
                or payload["state_hash"] != _hash(SCHEMA + "/STATE", body)):
            raise ValueError("D checkpoint identity mismatch")
        raw = payload["machine"]
        if type(raw) is not dict or set(raw) != {"state", "ordinal", "member", "session"}:
            raise ValueError("invalid D machine checkpoint")
        _int(raw["ordinal"], "ordinal", -1)
        if raw["ordinal"] + 1 != chain.instrument_next_ordinal(machine._instrument):
            raise ValueError("D checkpoint and prefix ordinal disagree")
        values = raw["state"]
        if type(values) is not dict or set(values) != set(asdict(DState())):
            raise ValueError("invalid D state fields")
        values = dict(values)
        for key in ("E", "E_prev", "pull_depth", "m_last", "m_prev", "p_last", "p_prev"):
            value = values[key]
            if value is not None:
                if (type(value) is not list or len(value) != 2
                        or any(type(x) is not int for x in value) or value[1] <= 0):
                    raise ValueError("invalid D rational")
                values[key] = Fraction(*value)
        for key in ("age", "n_ext"):
            _int(values[key], key)
        for key in ("g_E", "g_E_prev", "duration_last"):
            if values[key] is not None:
                _int(values[key], key)
        for key in ("armed", "broken"):
            if type(values[key]) is not bool:
                raise ValueError("invalid D boolean")
        if raw["ordinal"] >= 0:
            DObservation(raw["ordinal"], raw["member"], raw["session"],
                         values["anchor_dir"], None, True)
        elif raw["member"] is not None or raw["session"] is not None or values != asdict(DState()):
            raise ValueError("nonempty initial D state")
        state = DState(**values)
        if (state.pull_depth is None or state.pull_depth < 0
                or (state.anchor_dir is None) != (state.E is None)
                or (state.broken and (state.armed or state.n_ext))
                or (state.n_ext >= 1 and any(x is None or x <= 0 for x in
                    (state.m_last, state.p_last, state.duration_last)))
                or (state.n_ext >= 2 and any(x is None or x <= 0 for x in
                    (state.m_prev, state.p_prev)))):
            raise ValueError("inconsistent D geometry")
        machine._machine._state = state
        machine._machine._ordinal = raw["ordinal"]
        machine._machine._member = raw["member"]
        machine._machine._session = raw["session"]
        if machine.export_state() != payload:
            raise ValueError("noncanonical D checkpoint")
        return machine
