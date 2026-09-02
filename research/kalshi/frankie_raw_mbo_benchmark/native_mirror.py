"""Section 4.4's one mechanically defined mirror key, and the matcher that uses it.

Contract 4.4: *"Preserve each member and its mechanically defined mirror key."*
Singular. This module is that key, so the definition has one implementation rather
than several that agree today.

The mirror is the SIDE-SWAPPED SIDE STRING, not a price reflection and not book
geometry: swap `A` for `B` through a member's side string, pair the string with its
swap, and let the lexicographically first of the pair be `CANONICAL`, so both members
of a pair resolve to the same key from either end. The definition is not new here - it
was built, ran, and emitted a `mirror-pair-index.json` with 966 mirror-ready keys as
`mirror_identity()` in `a_memory_member_first_recalculation_20260828.py`, which now
delegates here.

**How this relates to section 4.12's `SAME`/`FLIP` is an OPEN RULING, not settled here.**
An earlier version of this docstring asserted they were "different axes, both required".
The contract does not say that. Section 3 lists the stratifier as "side or mirror
orientation" (:65) and forbids averaging across "mirror orientations" (:71) - one axis
named two ways - while 4.12 stratifies on `SAME`/`FLIP` and speaks of "paired mirror
differences" in the same clause. So "4.12's orientation IS the mirror orientation" reads at
least as well as the split.

Nothing is pinned either way, and nothing needs to be yet: `DipoleStage.orientation` has no
producer anywhere in the tree and `mirror_signed_flow` is never looked up, so 4.12's
orientation is unfed and the question is not live. It becomes live the moment something
feeds it. Until then this module claims only 4.4's member-level pair key and makes no claim
about 4.12.

---

## The matcher, and why it exists (D-16, run 33605852433)

The delivered run formed **0 pairs in all 1,692 strata** with `excluded_missing_members`
totalling **3,454** - every stage unpaired - and emitted neither a matching distance nor a
per-reason unmatched counter. Frankie's D-16: *"the matcher's total failure is visible but
undiagnosable from the delivered evidence"*, and F-24: the mission's third seed hypothesis is
therefore **untested rather than refuted**. The cause was mechanical: nothing ever passed
`mirror_signed_flow` into `DipoleCalculator.observe_stage`, so every stage took the
`exclude_missing` branch. One counter would have said whether the rule found no candidates,
found candidates outside the bound, or was never invoked - and those are three different
programmes.

So `MirrorMatcher` below records the four things contract 4.4 names - **pair IDs, unmatched
members, exact differences, and matching distance** - and records them EVEN WHEN NOTHING
PAIRS. That is not a degraded mode, it is the mode that matters: a run pairing nothing must
still say why, broken down by reason, with the distance distribution of the near misses.
Zero pairs plus a populated `NO_COUNTERPART_IN_SCOPE` counter is a finding; zero pairs plus
silence is what D-16 is.

**The reason vocabulary is closed by an accounting identity, not by imagination.** Every
member the matcher accepts or is told about ends in exactly one of: a pair, or one declared
reason. `finalize()` refuses to return unless

    members_seen == 2 * pairs_formed + sum(unmatched_reason_counts.values())

holds, so a future branch that ends a member's life without stamping a reason fails loudly
here instead of quietly shrinking the population - which is the S116 lesson about counted
drops, in the one place where it is cheap to enforce. The six reasons are the six ways that
walk can end, and the first three are exactly Frankie's three questions.

A member the matcher never receives at all is `NOT_OFFERED_TO_MATCHER`, and that is the
reason the delivered run's 3,454 stages would have carried. It is a reason, not an absence:
D60 says a member is used, or retained and counted, or refused loudly, and "the producer did
not hand it over" is a diagnosis a reader can act on.

**One-to-one attribution, stated as a number.** A member enters at most one pair, so
`attributions_per_member` is exactly 1 and is emitted rather than left to be derived. That is
D-3's lesson applied before the fact: 4.7's `restoration_ratio` was an arrival density read
as a replacement ratio because its 18.18 attributions per episode lived in the traversal
counters rather than on the value. Where the one-to-one rule COSTS a pair - an in-bound
counterpart already committed to an earlier pair - that shows up as its own reason,
`COUNTERPART_EXHAUSTED`, instead of being absorbed into a distance complaint.

**This matcher is not wired.** Nothing in `native_calculation_runner` or the candidate
adapter calls it yet; wiring it is a change to files this work was not permitted to touch,
and it is stated in the handoff rather than assumed. Unwired, it is tested and inert, and it
claims no result about the seed hypothesis.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from research.kalshi.frankie_raw_mbo_benchmark.native_stratum import (
    EXACT_QUANTILE_CAP,
    RESOLVED,
    Declaration,
    StratifiedMeasure,
    StratumKey,
    StreamingDistribution,
)

CAUSAL_CLOCK = "ts_recv_ns"

CANONICAL = "CANONICAL"
MIRROR = "MIRROR"
VALID_ORIENTATIONS = frozenset({CANONICAL, MIRROR})

_SIDE_SWAP = str.maketrans({"A": "B", "B": "A"})


def mirror_identity(sides: str) -> dict[str, str]:
    """Resolve a side string to its mirror pair and this string's half of it.

    Deliberately total: a side string carrying `N` or any other character passes those
    characters through unswapped rather than raising, because an unsided or novel row is
    preserved and characterized here, never dropped (D60).
    """
    mirror = sides.translate(_SIDE_SWAP)
    pair = sorted((sides, mirror))
    return {
        "side_string": sides,
        "mirror_side_string": mirror,
        "mirror_pair_key": f"{pair[0]}|{pair[1]}",
        "orientation": CANONICAL if sides == pair[0] else MIRROR,
    }


def mirror_orientation(sides: str) -> str:
    """Just the pair half, for callers that stratify on it and need nothing else."""
    return mirror_identity(sides)["orientation"]


PAIRED = "PAIRED"
"""The side-orientation value a PAIR-level stratum carries.

Not a third member orientation, which is why it is not in `VALID_ORIENTATIONS`: a member is
`CANONICAL` or `MIRROR`, and a pair is one object spanning both. Section 3 forbids averaging
ACROSS mirror orientations; a within-pair difference is not that average, it is the estimand
the prohibition exists to protect, so it gets its own stratum label rather than borrowing one
of the halves' labels and reading as if the other half had been pooled in.
"""

MATCHING_RULE_ID = "MIRROR_EXACT_SIDE_SWAP_NEAREST_COORDINATE_V1"

NOT_OFFERED_TO_MATCHER = "NOT_OFFERED_TO_MATCHER"
"""The producer knew of the member and never handed it over.

The delivered run's condition for all 3,454 stages. Distinguishing it matters more than any
other reason here: a rule that was never invoked and a rule that ran and found nothing are
the same silence in the artifact and opposite findings about the mission's seed hypothesis.
"""

COORDINATE_ABSENT = "COORDINATE_ABSENT"
"""No lawful matching coordinate, so no distance could be formed for this member.

Excluded and counted, never coerced to zero. A zero coordinate is a position on the axis and
would let the member pair with anything else sitting near zero.
"""

SELF_MIRROR = "SELF_MIRROR"
"""The side string is invariant under the A/B swap, so no DISTINCT counterpart exists.

`NNN` mirrors to `NNN`. Pairing two such members would produce a pair whose halves are both
`CANONICAL` and whose within-pair difference measures two unsided members against each other,
which is not a mirror contrast. Declared unpairable rather than silently pairable.
"""

NO_COUNTERPART_IN_SCOPE = "NO_COUNTERPART_IN_SCOPE"
"""The rule ran and no member carrying the mirrored side string was ever offered in scope."""

DISTANCE_ABOVE_BOUND = "DISTANCE_ABOVE_BOUND"
"""Counterparts existed in scope and every one of them sat outside the declared bound.

This is the reason whose near-miss distances are the actionable evidence: a run failing here
with a p50 near miss just past the bound is a bound to re-site, and one failing with a p50
three orders out is an estimand to re-specify. Frankie's bar for 4.4 is exactly that number.
"""

COUNTERPART_EXHAUSTED = "COUNTERPART_EXHAUSTED"
"""An in-bound counterpart existed and had already been committed to an earlier pair.

The cost of one-to-one attribution, named. Folding these into `DISTANCE_ABOVE_BOUND` would
blame the bound for a contest over attribution and invite widening a bound that is correct.
"""

UNMATCHED_REASONS = (
    NOT_OFFERED_TO_MATCHER,
    COORDINATE_ABSENT,
    SELF_MIRROR,
    NO_COUNTERPART_IN_SCOPE,
    DISTANCE_ABOVE_BOUND,
    COUNTERPART_EXHAUSTED,
)


class MirrorError(ValueError):
    """A mirror match could not be attempted or accounted for consistently."""


@dataclass(frozen=True)
class MatchScope:
    """The non-poolable identity a pair must share, minus the side orientation.

    Side orientation is the one dimension a mirror pair MUST span - that is what a mirror is -
    so it is the one `StratumKey` field this scope does not carry. Everything else section 3
    forbids pooling across is carried, so two members can only pair inside one day, one role,
    one continuity segment, one family, one subfamily and one session phase.
    """

    source_day: str
    source_role: str
    continuity_segment: int
    family_id: str
    session_phase: str
    subfamily_id: str = ""

    def key(self, side_orientation: str) -> StratumKey:
        return StratumKey(
            source_day=self.source_day,
            source_role=self.source_role,
            continuity_segment=self.continuity_segment,
            family_id=self.family_id,
            side_orientation=side_orientation,
            session_phase=self.session_phase,
            clock=CAUSAL_CLOCK,
            subfamily_id=self.subfamily_id,
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "source_day": self.source_day,
            "source_role": self.source_role,
            "continuity_segment": self.continuity_segment,
            "family_id": self.family_id,
            "session_phase": self.session_phase,
            "subfamily_id": self.subfamily_id,
        }


@dataclass
class _Offered:
    """One member offered for matching, and everything the diagnosis will need later."""

    member_id: str
    sides: str
    mirror_sides: str
    mirror_pair_key: str
    orientation: str
    coordinate: float
    sequence: int
    scope: MatchScope
    paired_into: int | None = None
    counterparts_considered: int = 0
    nearest_distance: float | None = None
    nearest_free_distance: float | None = None
    nearest_committed_in_bound: float | None = None

    def note_consideration(self, distance: float, *, counterpart_committed: bool, in_bound: bool) -> None:
        """Record one comparison, from either end.

        Recorded on BOTH members of every comparison, which is what makes the diagnosis
        symmetric in time. Without it the earlier-offered member of an out-of-bound pair
        reports `NO_COUNTERPART_IN_SCOPE` - it saw an empty pool when it arrived - while the
        later one reports `DISTANCE_ABOVE_BOUND`, and the same fact reads two ways depending
        on arrival order.
        """
        self.counterparts_considered += 1
        if self.nearest_distance is None or distance < self.nearest_distance:
            self.nearest_distance = distance
        if counterpart_committed:
            if in_bound and (
                self.nearest_committed_in_bound is None or distance < self.nearest_committed_in_bound
            ):
                self.nearest_committed_in_bound = distance
        elif self.nearest_free_distance is None or distance < self.nearest_free_distance:
            self.nearest_free_distance = distance


class MirrorMatcher:
    """Section 4.4's matcher: pair IDs, unmatched members with reasons, exact differences, distance.

    Streaming and order-independent in outcome: a member offered before its counterpart waits
    in the pool rather than being decided against an empty pool, and the pair forms when the
    second half arrives. Nothing looks forward - a member is paired against members already
    seen, never against one that has not been offered yet.
    """

    def __init__(
        self,
        *,
        coordinate_name: str,
        distance_bound: float,
        exact_cap: int | None = None,
        seed: int = 0,
    ) -> None:
        if not isinstance(coordinate_name, str) or not coordinate_name.strip():
            raise MirrorError(
                "the matching coordinate must be named; an unnamed distance is a number whose "
                "units cannot be read off the output, which is D-16's second half"
            )
        if not isinstance(distance_bound, (int, float)) or isinstance(distance_bound, bool):
            raise MirrorError("distance_bound must be numeric")
        if distance_bound < 0:
            raise MirrorError("distance_bound must be non-negative")
        self.coordinate_name = coordinate_name
        self.distance_bound = float(distance_bound)

        kwargs: dict[str, Any] = {"seed": seed}
        if exact_cap is not None:
            kwargs["exact_cap"] = exact_cap

        def measure(name: str, numerator: str, population: str, missingness: str) -> StratifiedMeasure:
            return StratifiedMeasure(
                name=name,
                declaration=Declaration(
                    numerator_formula=numerator,
                    population=population,
                    causal_cutoff=(
                        f"member offer time on {CAUSAL_CLOCK}; a member is matched only against "
                        "members already offered"
                    ),
                    status=RESOLVED,
                    missingness_rule=missingness,
                ),
                **kwargs,
            )

        self.matching_distance = measure(
            "matching_distance",
            (
                f"|{coordinate_name}(canonical) - {coordinate_name}(mirror)| for a formed pair, "
                f"under {MATCHING_RULE_ID} with bound {self.distance_bound}"
            ),
            "formed mirror pairs within the stratum",
            "unmatched members are excluded here and counted under their own reason",
        )
        self.unmatched_nearest_distance = measure(
            "unmatched_nearest_candidate_distance",
            (
                f"|{coordinate_name}(member) - {coordinate_name}(nearest counterpart considered)| "
                "for a member that ended unpaired; the near miss"
            ),
            "unmatched members that had at least one counterpart to compare against",
            (
                "a member with no counterpart in scope contributes NO distance and is counted "
                "under NO_COUNTERPART_IN_SCOPE; it is never entered as a distance of zero"
            ),
        )

        # Always present, whatever the strata do. The delivered artifact's failure was that
        # section 4.4 contributed no averaged rows AT ALL, so a consumer could not tell an
        # empty measure from an absent one. These two carry n=0 with null quantiles rather
        # than vanishing.
        self.pair_distances = StreamingDistribution(exact_cap=exact_cap or EXACT_QUANTILE_CAP, seed=seed)
        self.near_miss_distances = StreamingDistribution(exact_cap=exact_cap or EXACT_QUANTILE_CAP, seed=seed)

        self._pool: dict[MatchScope, dict[str, list[_Offered]]] = {}
        self._sequence = 0
        self._next_pair_id = 0
        self.members_seen = 0
        self.members_offered = 0
        self.members_withheld = 0
        self.pairs: list[dict[str, Any]] = []
        self.unmatched: list[dict[str, Any]] = []
        # Declared at zero from construction. An unmatched reason with no occurrences is still
        # a declared reason - `{}` says the matcher has nothing to report, `{...: 0}` says it
        # looked and that branch never fired, and those are different statements.
        self.unmatched_reason_counts: dict[str, int] = {reason: 0 for reason in UNMATCHED_REASONS}
        self._finalized = False

    # --- the offer path ---------------------------------------------------

    def offer(
        self,
        *,
        member_id: str,
        sides: str,
        coordinate: float | None,
        scope: MatchScope,
    ) -> dict[str, Any]:
        """Offer one member for matching and report what happened to it.

        Returns the member's disposition immediately: `PAIRED`, `PENDING` (in the pool,
        awaiting a counterpart that may still arrive) or `UNMATCHED` with its reason for the
        two dispositions that can be settled on arrival.
        """
        if self._finalized:
            raise MirrorError(
                "this matcher has been finalized; offering more members would change a "
                "population that has already been published"
            )
        if not isinstance(member_id, str) or not member_id.strip():
            raise MirrorError(
                "every offered member needs an id; contract 4.4 retains PAIR IDS, and a pair "
                "naming nothing is not exact evidence of anything"
            )
        if not isinstance(scope, MatchScope):
            raise MirrorError("a member must be offered inside a MatchScope")
        self.members_seen += 1
        self.members_offered += 1
        identity = mirror_identity(sides)

        if coordinate is None:
            return self._record_unmatched(
                member_id=member_id,
                identity=identity,
                scope=scope,
                reason=COORDINATE_ABSENT,
                coordinate=None,
            )
        if identity["mirror_side_string"] == sides:
            return self._record_unmatched(
                member_id=member_id,
                identity=identity,
                scope=scope,
                reason=SELF_MIRROR,
                coordinate=float(coordinate),
            )

        member = _Offered(
            member_id=member_id,
            sides=sides,
            mirror_sides=identity["mirror_side_string"],
            mirror_pair_key=identity["mirror_pair_key"],
            orientation=identity["orientation"],
            coordinate=float(coordinate),
            sequence=self._sequence,
            scope=scope,
        )
        self._sequence += 1

        by_sides = self._pool.setdefault(scope, {})
        # Pooled BEFORE the search and kept there after it pairs. A committed member stays
        # visible as a candidate so a later member can report COUNTERPART_EXHAUSTED against
        # it; dropping it on pairing would make the diagnosis depend on arrival order, with
        # the same fact reading NO_COUNTERPART_IN_SCOPE for whoever came last. The pool is
        # bounded by the section's own population - 3,454 stages in the delivered run, not
        # the 4.26M group stream - and the scan is within one scope, which held about two
        # members on average across 1,692 strata.
        by_sides.setdefault(member.sides, []).append(member)
        candidates = by_sides.get(member.mirror_sides, [])
        best: _Offered | None = None
        best_distance: float | None = None
        for candidate in candidates:
            distance = abs(member.coordinate - candidate.coordinate)
            committed = candidate.paired_into is not None
            in_bound = distance <= self.distance_bound
            member.note_consideration(distance, counterpart_committed=committed, in_bound=in_bound)
            if not committed:
                candidate.note_consideration(distance, counterpart_committed=False, in_bound=in_bound)
            if committed or not in_bound:
                continue
            # Nearest wins; the earlier offer breaks a tie. Both halves of that are the
            # determinism the rule declaration claims - a tie broken by dict order would make
            # the pair set depend on insertion history nobody recorded.
            if best_distance is None or distance < best_distance or (
                distance == best_distance and best is not None and candidate.sequence < best.sequence
            ):
                best, best_distance = candidate, distance

        if best is None:
            return {
                "member_id": member_id,
                "disposition": "PENDING",
                "mirror_pair_key": member.mirror_pair_key,
                "orientation": member.orientation,
                "counterparts_considered": member.counterparts_considered,
                "nearest_candidate_distance": member.nearest_distance,
            }
        return self._form_pair(member, best, float(best_distance))

    def withhold(self, *, member_id: str, sides: str, scope: MatchScope, note: str) -> dict[str, Any]:
        """Record a member the producer declined to offer, with the note saying why.

        This is the D60 shape for the delivered run: 3,454 stages existed, the matcher never
        saw one, and the artifact recorded that as an exclusion count with no reason. A
        withheld member is retained and counted here, and its note travels on the row.
        """
        if self._finalized:
            raise MirrorError(
                "this matcher has been finalized; withholding more members would change a "
                "population that has already been published"
            )
        if not str(note).strip():
            raise MirrorError(
                "a withheld member needs the producer's reason; an unexplained withholding is "
                "the defect, not the record of it"
            )
        self.members_seen += 1
        self.members_withheld += 1
        identity = mirror_identity(sides)
        return self._record_unmatched(
            member_id=member_id,
            identity=identity,
            scope=scope,
            reason=NOT_OFFERED_TO_MATCHER,
            coordinate=None,
            note=note,
        )

    # --- accounting -------------------------------------------------------

    def _form_pair(self, member: _Offered, counterpart: _Offered, distance: float) -> dict[str, Any]:
        pair_id = self._next_pair_id
        self._next_pair_id += 1
        member.paired_into = pair_id
        counterpart.paired_into = pair_id
        canonical, mirrored = (
            (member, counterpart) if member.orientation == CANONICAL else (counterpart, member)
        )
        # Signed, and oriented by the pair key rather than by arrival order, so the same pair
        # yields the same difference whichever half arrived first. An unsigned distance is
        # already carried beside it; a sign that flips with input order would be noise.
        exact_difference = canonical.coordinate - mirrored.coordinate
        key = member.scope.key(PAIRED)
        self.matching_distance.observe(key, distance)
        self.pair_distances.add(distance)
        row = {
            "pair_id": pair_id,
            "mirror_pair_key": canonical.mirror_pair_key,
            "canonical_member_id": canonical.member_id,
            "mirror_member_id": mirrored.member_id,
            "canonical_side_string": canonical.sides,
            "mirror_side_string": mirrored.sides,
            "coordinate_name": self.coordinate_name,
            "canonical_coordinate": canonical.coordinate,
            "mirror_coordinate": mirrored.coordinate,
            "exact_difference": exact_difference,
            "matching_distance": distance,
            # The qualifiers travel ON the row. A pair read out of a companion row six months
            # from now must carry the rule and the bound it was formed under, or "distance
            # 4,000" is a number with no admissibility statement attached to it.
            "matching_rule": MATCHING_RULE_ID,
            "distance_bound": self.distance_bound,
            "attributions_per_member": 1,
            "stratum": member.scope.key(PAIRED).as_dict(),
        }
        self.pairs.append(row)
        return {
            "member_id": member.member_id,
            "disposition": "PAIRED",
            "pair_id": pair_id,
            "mirror_pair_key": canonical.mirror_pair_key,
            "orientation": member.orientation,
            "matching_distance": distance,
            "exact_difference": exact_difference,
        }

    def _record_unmatched(
        self,
        *,
        member_id: str,
        identity: dict[str, str],
        scope: MatchScope,
        reason: str,
        coordinate: float | None,
        note: str | None = None,
        counterparts_considered: int = 0,
        nearest_distance: float | None = None,
        nearest_free_distance: float | None = None,
        nearest_committed_in_bound: float | None = None,
    ) -> dict[str, Any]:
        if reason not in self.unmatched_reason_counts:
            raise MirrorError(f"unknown unmatched reason: {reason}")
        orientation = identity["orientation"]
        key = scope.key(orientation)
        self.matching_distance.exclude_missing(key)
        if nearest_distance is None:
            # No comparison happened, so there is no distance. Excluded and counted rather
            # than entered as zero: zero is the distance of a perfect match.
            self.unmatched_nearest_distance.exclude_missing(key)
        else:
            self.unmatched_nearest_distance.observe(key, nearest_distance)
            self.near_miss_distances.add(nearest_distance)
        self.unmatched_reason_counts[reason] += 1
        row = {
            "member_id": member_id,
            "side_string": identity["side_string"],
            "mirror_side_string": identity["mirror_side_string"],
            "mirror_pair_key": identity["mirror_pair_key"],
            "orientation": orientation,
            "unmatched_reason": reason,
            "coordinate_name": self.coordinate_name,
            "coordinate": coordinate,
            "counterparts_considered": counterparts_considered,
            "nearest_candidate_distance": nearest_distance,
            # The two halves of the near miss, kept apart because they argue for opposite
            # repairs: a free counterpart just outside the bound says re-site the bound, a
            # committed counterpart inside it says the contest was over attribution. Computed
            # on every comparison either way, so emitting only their minimum would be the
            # `sum_of_squares` mistake this file's neighbours already made once.
            "nearest_free_candidate_distance": nearest_free_distance,
            "nearest_committed_in_bound_distance": nearest_committed_in_bound,
            "matching_rule": MATCHING_RULE_ID,
            "distance_bound": self.distance_bound,
            "producer_note": note,
            "stratum": key.as_dict(),
        }
        self.unmatched.append(row)
        return {
            "member_id": member_id,
            "disposition": "UNMATCHED",
            "unmatched_reason": reason,
            "mirror_pair_key": identity["mirror_pair_key"],
            "orientation": orientation,
            "nearest_candidate_distance": nearest_distance,
        }

    @staticmethod
    def _pooled_reason(member: _Offered) -> str:
        """Why a member that survived to the end of the stream never paired.

        Order matters. `COUNTERPART_EXHAUSTED` is checked first because it is the more
        specific diagnosis: an in-bound counterpart DID exist and one-to-one attribution
        refused it, which is an attribution result. Reporting that as a distance failure
        would argue for widening a bound that was never the obstacle.
        """
        if member.counterparts_considered == 0:
            return NO_COUNTERPART_IN_SCOPE
        if member.nearest_committed_in_bound is not None:
            return COUNTERPART_EXHAUSTED
        return DISTANCE_ABOVE_BOUND

    def finalize(self) -> list[dict[str, Any]]:
        """Resolve every member still pooled, then prove the population adds up."""
        if self._finalized:
            raise MirrorError("this matcher has already been finalized")
        stranded = [
            member
            for by_sides in self._pool.values()
            for members in by_sides.values()
            for member in members
            if member.paired_into is None
        ]
        rows = []
        for member in sorted(stranded, key=lambda m: m.sequence):
            rows.append(
                self._record_unmatched(
                    member_id=member.member_id,
                    identity=mirror_identity(member.sides),
                    scope=member.scope,
                    reason=self._pooled_reason(member),
                    coordinate=member.coordinate,
                    counterparts_considered=member.counterparts_considered,
                    nearest_distance=member.nearest_distance,
                    nearest_free_distance=member.nearest_free_distance,
                    nearest_committed_in_bound=member.nearest_committed_in_bound,
                )
            )
        self._finalized = True
        accounted = 2 * len(self.pairs) + sum(self.unmatched_reason_counts.values())
        if accounted != self.members_seen:
            # The completeness proof for the reason vocabulary. If a branch ever ends a
            # member's life without stamping one of the six, the population silently shrinks
            # and every rate computed off it is wrong in the direction that flatters it.
            raise MirrorError(
                f"mirror accounting does not close: {self.members_seen} members seen against "
                f"{accounted} accounted for ({len(self.pairs)} pairs, "
                f"{sum(self.unmatched_reason_counts.values())} unmatched)"
            )
        return rows

    # --- output -----------------------------------------------------------

    def companion_rows(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for measure in (self.matching_distance, self.unmatched_nearest_distance):
            rows.extend(measure.rows())
        return rows

    def matching_rule(self) -> dict[str, Any]:
        """The rule itself, written where the output is read.

        D-16's second half: 4.4 was *"the only estimand in the artifact whose definition
        cannot be read off the output"*. Every other measure declares its numerator formula,
        so this one declares its matching rule in the same place and in the same shape.
        """
        return {
            "rule_id": MATCHING_RULE_ID,
            "mirror_key": "side string with A and B swapped; lexicographically first half is CANONICAL",
            "eligibility": "exact mirrored side string within one MatchScope",
            "scope_fields": [
                "source_day",
                "source_role",
                "continuity_segment",
                "family_id",
                "session_phase",
                "subfamily_id",
            ],
            "coordinate_name": self.coordinate_name,
            "distance_formula": f"abs(member.{self.coordinate_name} - counterpart.{self.coordinate_name})",
            "distance_bound": self.distance_bound,
            "selection": "nearest admissible counterpart; earlier offer breaks a tie",
            "attribution": "ONE_TO_ONE",
            "attributions_per_member": 1,
            "lookahead": "none; a member matches only against members already offered",
        }

    def summary(self) -> dict[str, Any]:
        pairs = len(self.pairs)
        return {
            "section": "4.4",
            "causal_clock": CAUSAL_CLOCK,
            "matching_rule": self.matching_rule(),
            # False is the delivered run's answer and it is not derivable from a pair count
            # of zero, which is why it is stated rather than implied.
            "matcher_invoked": self.members_offered > 0,
            "members_seen": self.members_seen,
            "members_offered": self.members_offered,
            "members_withheld": self.members_withheld,
            "pairs_formed": pairs,
            "members_paired": 2 * pairs,
            "members_unmatched": sum(self.unmatched_reason_counts.values()),
            "unmatched_reason_counts": dict(self.unmatched_reason_counts),
            "pair_matching_distance": self.pair_distances.as_dict(),
            "unmatched_nearest_candidate_distance": self.near_miss_distances.as_dict(),
            "finalized": self._finalized,
            "accounting_identity": (
                "members_seen == 2 * pairs_formed + sum(unmatched_reason_counts); enforced in "
                "finalize, so a member cannot leave the population without a stated reason"
            ),
            "zero_pair_policy": (
                "reason counts and both distance distributions are emitted whatever the pair "
                "count; zero pairs with no diagnosis is D-16"
            ),
            "stratum_counts": {
                m.name: m.stratum_count
                for m in (self.matching_distance, self.unmatched_nearest_distance)
            },
        }
