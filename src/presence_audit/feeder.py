"""Feed a walk into the engine, and turn its envelope into an exit code.

The generator built the model. This supplies the readings and decides what the answer
means for CI.

**Stage 1 owns presence; only present-and-reading points are fed.** That is the
layering rule, and it is a blast-radius choice rather than a workaround: absence is a
question Stage 1 already answers precisely, with a three-valued verdict the engine has
no equivalent for. Feeding an absent point would ask the engine to re-derive something
weaker. The engine's own `missing_property` decline stays valuable as the belt to that
brace — if it ever fires, Stage 1 said a point was reading and its value did not reach
the model, which is a mapping bug and fails the gate.

**A single walk is one sample, and stuck-at needs about ten.** So liveness warms up:
until enough in-window observations exist, STABILITY declines `insufficient_samples`
and that decline is *reported*, not suppressed. A tool that hid it would look like it
was checking liveness from the first walk, which is the vacuous pass this project keeps
finding in other people's systems.

**Three decline classes, because the vocabulary is not ours.** A decline that asserts
the core case fails the gate; a decline about data sufficiency reports and passes; and
a reason this build does not recognise is reported prominently and does not silently
join either bucket. The engine's reason vocabulary is not exported as a constant, so
this classification is built from reasons actually observed — which makes an unknown
reason a certainty over time, not a hypothetical.

**A capture is placed in time by its order, or by its own stamp.** By order, the
default, each capture takes one slot of the declared grid, oldest first, ending at
the engine's clock. By stamp (`timed_by="captured_at"`), each takes the slot its
`captured_at` falls in, counted back from the newest, and a slot nothing fell in
stays empty. `FeedResult.timing` says which, so a reader never has to infer the
clock from the numbers.

Nothing here imports `arbiter_engine` at module scope. Stage 1 must keep running on a
bench with nothing provisioned.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Sequence

from . import vocabulary as _vocabulary
from .generator import (COUPLING_RELATION, DEFAULT_SAMPLE_INTERVAL_S, FAULT_RELATION,
                        READING, Manifest, peer_property)

__all__ = ["FeedResult", "DetectOutcome", "feed", "unmapped_observations",
           "evaluate", "STUCK_AT_SAMPLE_FLOOR", "ENVELOPE_SCHEMA_VERSION",
           "PlacementError", "TIMED_BY_CAPTURE", "TIMED_BY_INTERVAL"]

#: What `FeedResult.timing` names when each capture took the slot its own
#: stamp falls in, and when captures took the declared grid in order. The two
#: words the consulting vertical's feeder already reports under, so a reader of
#: both learns one vocabulary for one question.
TIMED_BY_CAPTURE = "captured_at"
TIMED_BY_INTERVAL = "interval_seconds"


class PlacementError(ValueError):
    """Captures that cannot be placed by their own stamps, and which ones.

    RAISED, unlike everything else `feed` counts. A placement nobody can make
    leaves nothing fed, and a session holding nothing reads exactly like a
    healthy one to every check that follows -- so a caller that did not look
    for a flag would print a clean verdict over no readings. The caller decides
    what to do instead; placing the captures on the grid by their order is one
    choice it can make, and say it made.
    """

# The wire contract this build parses. Versioned separately from the package by the
# engine, deliberately: `meta.schema_version` describes the ENVELOPE shape and moves
# only when that shape changes, so it is not the release number and must not be
# compared against one.
#
# Everything this module knows is keyed to that shape -- `findings` vs `not_checked`,
# the `problem_type` split, `reason` as the decline vocabulary. If the shape moves,
# each of those reads plausibly and wrongly, which is worse than failing: a decline
# the engine renamed lands in `unclassified` and a finding it restructured is quietly
# unattributable. So an unexpected version stops the run rather than degrading it.
ENVELOPE_SCHEMA_VERSION = 1

# Measured on 0.1.6: a constant series declines below about ten samples and produces a
# STABILITY finding at ten or more. See docs/stage2/s1-threshold-granularity.md for the
# sibling measurement; this one is recorded in the canary.
STUCK_AT_SAMPLE_FLOOR = 10


# Declines that assert the tool's core case. If one of these arrives, something the
# feeder promised the engine did not turn up.
_CORE_CASE_REASONS = frozenset({"missing_property", "no_current_value"})

# Declines that mean "not enough data yet", which is honest and not a failure.
_DATA_SUFFICIENCY_REASONS = frozenset({"insufficient_samples"})

# Declines that mean the check does not apply to THIS data. Different from both of
# the above: there is plenty of data and nothing the feeder promised is missing --
# the question is meaningless against the values that arrived.
#
# **Measured on 0.1.8, inside the pin this project already declares.** CONSERVATION
# declines `not_applicable` when the total input is at or below zero, where 0.1.6
# and 0.1.7 returned an empty problem list and said nothing at all. A declared power
# flow on a supply reading zero watts in is the case: real on any idle or powered-off
# rail, and it arrived here as a reason this build did not recognise.
#
# That classification was not WRONG -- the vocabulary genuinely had no member for it
# -- and it printed *declines this build does not recognise*, which was true on the
# day it was written and stopped being true the moment somebody measured it. A
# vocabulary is only derived while somebody keeps deriving it.
_NOT_APPLICABLE_REASONS = frozenset({"not_applicable", "undefined_for_values"})

# `undefined_for_values` joined the set above on 2026-09-02, BEFORE the engine
# release that emits it, and it is the same fact under a new name rather than a
# new fact. Measured against both engines on one model -- a declared power flow
# on a rail reading zero watts in: the pinned build declines `not_applicable`,
# the next one declines `undefined_for_values`, findings empty in both. The
# engine split a reason that was three answers under one name; this is the arm
# that means *the quantity has no value on these values*, which is what the
# paragraph above already describes.
#
# Classified ahead of the release on purpose. An unknown member lands in
# `unclassified_declines`, which is the correct behaviour and would have failed
# `--strict` on the day the pin moved, for a case this build has understood
# since 0.1.8. Reported from outside, measured here before believing it.

# A check that was declared and never made answerable: the model states the
# axiom and supplies no number for it to compare against.
#
# WHY THIS IS NOT A MODEL DEFECT, EVEN THOUGH THIS PACKAGE WRITES THE MODEL.
# The generator already withholds BOUNDEDNESS from a point whose declaration carries no
# thresholds, precisely so the engine is never asked a question nobody set. It
# cannot do the same for MONOTONICITY: declaring the axiom gets the reversal arm
# AND the rate arm, and there is no way to declare one without the other. So a
# counter arrives with a rate arm nobody bounded, and this package cannot bound
# it -- power-on hours climb at one per 3600 s and a correctable-ECC count has no
# published rate at all. That number is an operator-knowledge fact, which is the
# wall the supplemental declarations channel exists for and where this belongs
# in the long run.
#
# WHY NOT FOLDED INTO THE SET ABOVE. `_NOT_APPLICABLE_REASONS` means *the
# question is meaningless against the values that arrived*. This one means
# *nobody supplied the number*. Same bucket by decision, different fact -- and
# lumping them would make that set's own comment false, which is the exact drift
# this file keeps catching in itself.
#
# CLASSIFIED AHEAD OF THE RELEASE, the same way `undefined_for_values` was, and
# for a measured reason rather than a cautious one. An unreleased engine build
# makes MONOTONICITY's rate arm decline `no_threshold` when no rate is declared;
# before this line, that reason was in none of the five sets here, so it fell to
# `unclassified_declines` and `--strict` went from 0 to 1 on every healthy BMC
# carrying a counter. Measured by calling `evaluate` with that envelope, not
# inferred from reading the engine.
#
# `--strict` STILL FAILS on it, and should: a check that was never made
# answerable is not established, and strict is the mode that says so.
_NO_THRESHOLD_REASONS = frozenset({"no_threshold"})

# Declines that say the MODEL is wrong rather than the data. This package
# GENERATES the model, so a declaration the engine cannot run is this package's
# defect and must fail: nothing else will notice it.
#
# Kept out of `_CORE_CASE_REASONS` deliberately -- that set is subject to the
# expected-peer exemption below, which is a statement about a point that is not
# reading. A model defect has no peer to be excused by.
_MODEL_DEFECT_REASONS = frozenset({"missing_role"})

# A check gated on a property the entity must carry, where the entity did not
# carry it. The engine declines rather than passing, and says in as many words
# that it cannot tell a deliberate exemption from a mistyped name -- so this is
# routed to a human, not to a verdict.
#
# UNREACHABLE FROM THIS PACKAGE TODAY, and classified anyway: the generator emits
# no CONNECTIVITY statement and no `required_property`, so nothing here can
# produce it. Left in the inapplicable bucket rather than a failing one, because
# arriving would mean a supplemental file declared a gate, and the operator who
# wrote it is the one who knows whether the exemption was meant.
_PRECONDITION_REASONS = frozenset({"precondition_unmet"})


@dataclass
class FeedResult:
    fed: int = 0
    skipped_not_reading: int = 0
    skipped_not_modelled: int = 0
    samples: dict[str, int] = field(default_factory=dict)
    # Declared redundant pairs where the peer is not currently reading, so agreement
    # was not judged. Reported rather than dropped: a pairing that silently stops
    # being checked looks exactly like a pairing that agrees.
    peers_not_reading: list[str] = field(default_factory=list)
    # The same fact keyed by entity type, which is what a decline names. Kept beside
    # the human-readable list rather than parsed back out of it -- re-deriving one
    # from the other means a display change silently alters a gate decision.
    entities_missing_peers: set[str] = field(default_factory=set)
    #: Declared couplings that became an EDGE in the session, as (driver, driven)
    #: display names. `manifest.coupled` says which became a relationship RULE,
    #: which is a different claim: a rule with no edge under it is checked
    #: against nothing.
    coupled: list[tuple[str, str]] = field(default_factory=list)
    #: And every one that did not, with the reason. A coupling whose endpoint was
    #: not fed this run -- not reading, or not modelled -- has no edge, and the
    #: run then looks exactly like a run where no coupling was declared.
    couplings_not_fed: list[dict] = field(default_factory=list)
    #: Declared fault channels that became an edge, and every one that did not.
    channeled: list[tuple[str, str]] = field(default_factory=list)
    channels_not_fed: list[dict] = field(default_factory=list)
    #: The grid the observations were stamped on, in seconds. Reported because
    #: a fitted gain is only meaningful against the spacing it was fitted at,
    #: and until 0.1.10 this was 60 whatever the file said.
    interval_seconds: float = 0.0
    #: How many diff reports were fed. `fed` counts points; this counts the
    #: captures they came from, and zero means none arrived at all.
    reports: int = 0
    #: Points whose history was fed only from the last capture they missed on,
    #: by declared name: how many readings were fed, how many were not, and
    #: which capture broke the run (counted from one). Only a point the engine
    #: pairs with another is ever cut, and only on the grid -- see `_placed` for
    #: why, and for what the history that was not fed would have cost.
    cut: dict[str, dict] = field(default_factory=dict)
    #: How the captures were placed in time. `timed_by` is `interval_seconds`
    #: when they took the declared grid in order, and `captured_at` when each
    #: took the slot its own stamp falls in -- then with the first and last
    #: slot, how many captures filled how many slots, and the largest distance
    #: a stamp moved to reach its slot, which is where a collector drifting
    #: from its declared cadence shows. Empty when nothing was fed.
    timing: dict = field(default_factory=dict)
    #: The instant to judge a session fed by stamp at: the newest capture's own
    #: time, because its readings are where they were taken and the engine's
    #: windows end at its clock. None on the grid, whose ladder ends at the
    #: engine's clock whatever it reads.
    judged_at: datetime | None = None

    @property
    def fed_nothing(self) -> bool:
        """No report reached this feed, so the session holds nothing from it.

        The compose rule applied to a feed: composing nothing is could-not-
        complete, never clean. `feed` of no reports used to return a result
        indistinguishable from one where every point was skipped, and a check
        over such a session reads exactly like a healthy system. Marked rather
        than raised, because `2` is the caller's to give -- as
        `DetectOutcome.exit_code` already says of itself.
        """
        return self.reports == 0

    @property
    def warming_up(self) -> dict[str, int]:
        """Points with too little history for stuck-at detection, and how much
        they have. Surfaced so a report can say *liveness: warming up, 4/10* rather
        than implying it checked."""
        return {name: n for name, n in self.samples.items()
                if n < STUCK_AT_SAMPLE_FLOOR}


@dataclass
class DetectOutcome:
    findings: list[str] = field(default_factory=list)
    core_case_declines: list[str] = field(default_factory=list)
    data_declines: list[str] = field(default_factory=list)
    inapplicable_declines: list[str] = field(default_factory=list)
    unclassified_declines: list[str] = field(default_factory=list)
    unmapped: list[str] = field(default_factory=list)
    checked: dict = field(default_factory=dict)
    strict: bool = False
    schema_mismatch: str | None = None

    @property
    def exit_code(self) -> int:
        """0 clean, 1 something got worse, 2 could not complete.

        `2` is never returned from here: it belongs to the caller, which knows
        whether the capture source answered and whether the model loaded.
        Conflating *could not evaluate* with *declared points are missing* would
        fail a healthy system, and it only has to happen once before nobody trusts
        the gate.
        """
        if self.findings or self.core_case_declines or self.unmapped:
            return 1
        if self.strict and (self.data_declines or self.inapplicable_declines
                            or self.unclassified_declines):
            return 1
        return 0


def feed(session: Any, manifest: Manifest,
         reports: Sequence[Any], *,
         timed_by: str = TIMED_BY_INTERVAL) -> FeedResult:
    """Register entities and history from a chronological run of diff reports.

    `reports` runs oldest to newest; the newest supplies current values and all of
    them supply history. Passing a single report is the normal case and simply means
    liveness has one sample and will say so.

    `timed_by` says how each capture is placed in time. `interval_seconds`, the
    default, places them by their order on the declared grid, as every release
    before 0.2.4 did. `captured_at` places each by the stamp its report carries,
    snapped to the slot of the grid it falls in, and keeps the slots nothing fell
    in empty; judge the session as of `FeedResult.judged_at` after it. Captures
    that cannot be placed that way raise `PlacementError` before anything is fed.
    """
    if timed_by not in (TIMED_BY_INTERVAL, TIMED_BY_CAPTURE):
        raise ValueError(f"timed_by is {TIMED_BY_INTERVAL!r} or "
                         f"{TIMED_BY_CAPTURE!r}; got {timed_by!r}")
    if not reports:
        # Marked, not raised: `reports == 0` is what `fed_nothing` reads.
        return FeedResult()

    result = FeedResult(reports=len(reports))
    #: Entity types that actually reached the session, so a coupling is wired
    #: only between two things that are in it.
    registered: set[str] = set()
    # THE GRID IS THE COLLECTOR'S, NOT THIS MODULE'S.
    #
    # The supplemental format requires `sampling_interval_s` as soon as a
    # coupling is declared, and refuses a `propagation_delay_s` that is not a
    # multiple of it -- because a delay off the collection grid can align no
    # pair of readings. Until 0.1.10 this function then stamped every
    # observation sixty seconds apart regardless, so the file was validated
    # against one grid and fitted on another, and the two never compared notes.
    #
    # MEASURED, not reasoned. On a synthetic board whose driven series was
    # generated from its driver at exactly one collection interval, with the
    # file declaring the real 300 s cadence: the fit came back -0.0023 against
    # a truth of +0.0040 -- wrong sign, r-squared 0.33, and a confidence
    # interval that excluded the true value. Declaring 60 s, the grid this
    # function actually used, recovered 0.0040 at r-squared 1.0. A fitted gain
    # is only a statement about the spacing it was fitted at.
    result.interval_seconds = float(
        manifest.sampling_interval_s or DEFAULT_SAMPLE_INTERVAL_S)
    # Placed BEFORE anything reaches the session, so captures that cannot be
    # placed leave it exactly as it was handed over.
    instants: list[datetime] | None = None
    if timed_by == TIMED_BY_CAPTURE:
        instants, result.timing = _instants(reports, result.interval_seconds)
        result.judged_at = instants[-1]
    else:
        result.timing = {"timed_by": TIMED_BY_INTERVAL,
                         "interval_seconds": result.interval_seconds}
    # Each reading keeps the position of the capture it came from, because that
    # position is the only thing that says which slot of the grid it belongs in.
    history: dict[str, list[tuple[int, float]]] = {}
    for position, report in enumerate(reports):
        for match in report.matches:
            if match.live.reading is None:
                continue
            history.setdefault(match.declared.display_name, []).append(
                (position, float(match.live.reading)))
    joined = _joined(manifest)
    last = len(reports) - 1

    current = reports[-1]
    # Current readings by declared name, so a redundant peer's value can be attached
    # to the entity that declares the agreement. Built from the same `is_reading`
    # test the feed loop applies, rather than from `history`, which carries readings
    # from walks where the point may since have stopped.
    readings = {m.declared.display_name: float(m.live.reading)
                for m in current.matches
                if m.live.is_reading and m.live.reading is not None}
    for match in current.matches:
        name = match.declared.display_name
        entity_type = manifest.type_for(name)
        if entity_type is None:
            # Declared, matched, and deliberately not modelled -- a templated name,
            # a type the vertical does not audit, or no thresholds to bound against. Counted so the
            # difference between "not checked" and "not modelled" stays visible.
            result.skipped_not_modelled += 1
            continue
        if not match.live.is_reading or match.live.reading is None:
            # Stage 1 owns this verdict. Feeding it would ask the engine to
            # re-derive a weaker version of an answer we already have.
            result.skipped_not_reading += 1
            continue

        value = float(match.live.reading)
        properties = {READING: value}

        # A declared redundant peer's reading, carried on this entity so CONSISTENCY
        # has both numbers. Fed only when the peer is itself present and reading:
        # otherwise the engine declines `missing_property`, which for this axiom
        # means *the peer is not there* -- a fact Stage 1 has already reported
        # precisely, and re-deriving it here as a mapping bug would be wrong.
        generated = next((s for s in manifest.points if s.entity_type == entity_type), None)
        carried = () if generated is None else generated.agrees_with + generated.flow_outputs
        for peer in carried:
            peer_value = readings.get(peer)
            if peer_value is None:
                result.peers_not_reading.append(f"{name} -> {peer}")
                result.entities_missing_peers.add(entity_type)
                continue
            properties[peer_property(peer)] = peer_value

        session.add_entity(entity_type, entity_type, properties=properties)
        series = _series(name, history.get(name, []), last, joined, result,
                         instants)
        if series:
            session.add_observations(entity_type, READING, series,
                                     interval_seconds=result.interval_seconds)
        # CONSERVATION reads a SERIES, not a current value -- fed only the properties
        # it declines `insufficient_samples` with *no observations of input property*,
        # which reads like a warm-up and never clears. CONSISTENCY needs only the
        # current value, so this is redundant for a pairing and harmless: the model
        # declares the property either way, so nothing goes unread.
        if generated is not None and generated.flow_outputs:
            for peer in generated.flow_outputs:
                peer_series = _series(peer, history.get(peer, []), last, joined,
                                      result, instants)
                if peer_series:
                    session.add_observations(entity_type, peer_property(peer),
                                             peer_series,
                                             interval_seconds=result.interval_seconds)
        result.samples[name] = len(series)
        result.fed += 1
        registered.add(entity_type)

    _wire_couplings(session, manifest, result, registered)
    return result


def _joined(manifest: Manifest) -> set[str]:
    """Points the engine reads beside another point's readings, by declared name.

    The endpoints of every coupling and fault channel, whose edges the engine
    fits and walks, and a flow's input and outputs, which conservation sums
    at one instant. Derived from the manifest -- the same declarations `feed`
    wires -- rather than listed, so a new kind of pairing cannot arrive
    without this seeing it or a reader seeing that it does not.
    """
    names: set[str] = set()
    for pair in list(manifest.coupled) + list(manifest.channeled):
        names.update(pair)
    for point in manifest.points:
        if point.flow_outputs:
            names.add(point.declared_name)
            names.update(point.flow_outputs)
    return names


def _placed(name: str, readings: Sequence[tuple[int, float]], last: int,
            joined: set[str], result: FeedResult) -> list[float]:
    """The readings of one point to feed, in the only slots they can occupy.

    A series goes to the engine as a ladder: one reading per grid slot, the
    newest one slot before the engine's clock. A ladder has no way to say
    *nothing here*, so a capture where the point did not read closes up, and
    every reading before it lands one slot later than the capture it came from.

    **Harmless for a point judged alone, and wrong for one read beside
    another.** A coupling is fitted by pairing the driver at one slot with the
    driven a declared delay later, so one shifted series pairs every earlier
    driver reading with the wrong capture of the driven. Measured on a driven
    series generated from its driver at exactly one interval, 200 captures,
    true gain 0.004: complete, the fit recovers 0.004; with the driver missing
    ONE reading at capture 191, it returned -0.0021 with an interval of
    [-0.0026, -0.0016] -- the wrong sign, the truth excluded, and the number an
    `adopt` would have written down. Twenty whole captures missing moved the
    same fit only to 0.00395, because every series then closes up together.

    So a joined point is fed its unbroken run of readings ending at the last
    capture, which lands each one in its own capture's slot, and the rest are
    counted in `result.cut` rather than fed out of place. That discards
    history, and says how much. Keeping it needs each capture placed by its
    own time, snapped to the slot it falls in, which is what
    `timed_by="captured_at"` does; this ladder is the grid's alone.

    An unjoined point is fed as it always was: its closed-up history still
    answers stuck-at, and cutting it would put a point that both sticks and
    stops reading back into warm-up every time it stopped.
    """
    values = [value for _, value in readings]
    if name not in joined:
        return values
    kept: list[float] = []
    expected = last
    for position, value in reversed(readings):
        if position != expected:
            break
        kept.append(value)
        expected -= 1
    kept.reverse()
    if len(kept) < len(values):
        result.cut[name] = {"fed": len(kept), "not_fed": len(values) - len(kept),
                            "missed": expected + 1, "captures": last + 1}
    return kept


def _series(name: str, readings: Sequence[tuple[int, float]], last: int,
             joined: set[str], result: FeedResult,
             instants: Sequence[datetime] | None) -> list:
    """One point's readings as the engine receives them.

    On the grid, a ladder, cut where a joined point missed a reading. By stamp,
    `(instant, value)` pairs at the slot each reading's capture took: a pair
    carries its own time, so a capture the point missed is a slot with nothing
    in it rather than a shift, and nothing is cut.
    """
    if instants is None:
        return _placed(name, readings, last, joined, result)
    return [(instants[position], value) for position, value in readings]


def _instant(stamp: Any) -> datetime | None:
    """A capture's stamp as an instant in UTC, or None when it carries none.

    ISO 8601 with a `Z`, with an offset, or with neither -- read as UTC, which
    is how the engine reads an instant with no zone. Anything else raises
    `ValueError`: a stamp nobody can place is refused where it is read, not
    taken as absent.
    """
    if stamp is None:
        return None
    if isinstance(stamp, datetime):
        parsed = stamp
    else:
        text = str(stamp).strip()
        if not text:
            return None
        if text[-1] in "Zz":
            text = text[:-1] + "+00:00"
        parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _positions(numbers: Sequence[int]) -> str:
    """`capture 3`, or `captures 3, 7 and 9`, counted from one as `cut` counts."""
    shown = [str(n) for n in numbers[:5]]
    more = f" and {len(numbers) - 5} more" if len(numbers) > 5 else ""
    if len(shown) == 1 and not more:
        return f"capture {shown[0]}"
    listed = (", ".join(shown) + more if more
              else f"{', '.join(shown[:-1])} and {shown[-1]}")
    return f"captures {listed}"


def _instants(reports: Sequence[Any],
              interval: float) -> tuple[list[datetime], dict]:
    """The slot each capture's stamp falls in, and the timing that reports it.

    THE GRID IS KEPT, AND ONLY ITS ANCHOR MOVES. The engine pairs one reading
    with another a declared delay later only at identical instants, and the
    supplemental format holds every delay to a multiple of the interval. A
    stamp jittered by a few seconds would align with nothing, so each capture
    takes the nearest slot of the grid anchored at the newest stamp; the
    distance it moved is reported, never hidden. A stamp exactly half an
    interval from two slots takes the older one, so one run always lands one way.

    REFUSED, and no slot guessed, when a capture has no stamp or one that is not
    a date and time, when the captures are not in the order their stamps give,
    or when two fall in one slot: two readings of one point at one instant are
    one reading too many, and keeping either would be choosing which capture to
    believe.
    """
    stamps: list[datetime | None] = []
    unreadable: list[str] = []
    for position, report in enumerate(reports, start=1):
        raw = getattr(report, "captured_at", None)
        try:
            stamps.append(_instant(raw))
        except (TypeError, ValueError):
            stamps.append(None)
            unreadable.append(f"capture {position} ({raw!r})")
    if unreadable:
        raise PlacementError(
            f"{', '.join(unreadable[:5])}"
            f"{f' and {len(unreadable) - 5} more' if len(unreadable) > 5 else ''} "
            f"cannot be read as a date and time, so no capture was placed by its "
            f"stamp; give captured_at in ISO 8601")
    missing = [position for position, when in enumerate(stamps, start=1)
               if when is None]
    if missing:
        raise PlacementError(
            f"{_positions(missing)} of {len(stamps)} carry no captured_at, so the "
            f"run cannot be placed by its stamps; placing only the stamped ones "
            f"would put two clocks in one series")
    backwards = [position for position in range(2, len(stamps) + 1)
                 if stamps[position - 1] <= stamps[position - 2]]
    if backwards:
        raise PlacementError(
            f"{_positions(backwards)} {'is' if len(backwards) == 1 else 'are'} "
            f"stamped no later than the capture before; captures run oldest to "
            f"newest, and the newest supplies every current reading")
    anchor = stamps[-1]
    slots = [math.floor((anchor - when).total_seconds() / interval + 0.5)
             for when in stamps]
    shared = [(position - 1, position) for position in range(2, len(slots) + 1)
              if slots[position - 1] == slots[position - 2]]
    if shared:
        pairs = "; ".join(f"captures {a} and {b} ({stamps[a - 1].isoformat()}, "
                          f"{stamps[b - 1].isoformat()})" for a, b in shared[:3])
        raise PlacementError(
            f"{pairs} fall in one slot of the {interval:g} s grid, so one point "
            f"would carry two readings at one instant; drop one of them, or "
            f"declare the interval the captures were taken at")
    instants = [anchor - timedelta(seconds=slot * interval) for slot in slots]
    moved = max(abs((when - placed).total_seconds())
                for when, placed in zip(stamps, instants))
    return instants, {
        "timed_by": TIMED_BY_CAPTURE, "interval_seconds": interval,
        "first": instants[0].isoformat(), "last": anchor.isoformat(),
        "captures": len(stamps), "slots": slots[0] + 1,
        "empty_slots": slots[0] + 1 - len(stamps),
        "largest_offset_s": moved}


def _wire_couplings(session: Any, manifest: Manifest, result: FeedResult,
                    registered: set[str]) -> None:
    """Turn each declared coupling into an EDGE between the two entities.

    **The defect this exists to close.** A coupling declared in a supplemental
    file was read, validated in detail, and written into the generated model as
    a `relationship_rules` entry -- and then nothing anywhere added the
    relationship it describes. A rule is a statement about two TYPES; a fit
    needs an instance of it. So `model_describe` reported `couplings_seen: 0`
    and a run with a coupling declared was byte-identical to a run without one:
    no gain, no interval, and no refusal saying why.

    That is the worse half of the shape this package has a rule about. A
    component that ignores what it does not recognise at least has the excuse
    of not recognising it. This one parsed the block, refused four different
    malformations in it, emitted it into the model, recorded the pair in the
    manifest, and produced nothing -- with every check along the way passing.

    BOTH ENDPOINTS MUST HAVE BEEN FED, and a coupling whose endpoint was not is
    RECORDED rather than skipped. An edge to an entity that was never
    registered is a claim about something not in the session; leaving it out
    silently puts the run back in the state above, where a coupling that
    contributes nothing looks exactly like a coupling that agrees.
    """
    for source, target in manifest.coupled:
        source_type = manifest.type_for(source)
        target_type = manifest.type_for(target)
        absent = [name for name, entity_type in ((source, source_type),
                                                 (target, target_type))
                  if entity_type is None or entity_type not in registered]
        if absent:
            result.couplings_not_fed.append(
                {"from": source, "to": target, "reason": "endpoint_not_fed",
                 "missing": absent})
            continue
        session.add_relationship(source_type, COUPLING_RELATION, target_type)
        result.coupled.append((source, target))

    # A CAUSAL RULE WITH NO EDGE UNDER IT IS CHECKED AGAINST NOTHING, as a
    # coupling's is: the edge is what the engine's causal graph is built from.
    for source, target in manifest.channeled:
        source_type = manifest.type_for(source)
        target_type = manifest.type_for(target)
        absent = [name for name, entity_type in ((source, source_type),
                                                 (target, target_type))
                  if entity_type is None or entity_type not in registered]
        if absent:
            result.channels_not_fed.append(
                {"from": source, "to": target, "reason": "endpoint_not_fed",
                 "missing": absent})
            continue
        session.add_relationship(source_type, FAULT_RELATION, target_type)
        result.channeled.append((source, target))


def unmapped_observations(describe: dict) -> list[dict]:
    """Observations the model never read, from wherever the engine reports them.

    **Measured on 0.1.6: this key is at the TOP LEVEL** of the describe payload, while
    its sibling `unread_fields` sits under `model`. Two introspection keys at two
    levels in one payload, and reading the wrong one returns `None` — which reads as
    *this engine does not support it* rather than *there is nothing to report*.

    So both are checked. If the key relocates, this keeps working and the canary
    fails loudly, which is the right way round: silent blindness here means every
    Redfish-to-model mapping error stops being visible.
    """
    top = describe.get("unmapped_observations") or describe.get("unconsumed_observations")
    nested = (describe.get("model") or {}).get("unconsumed_observations")
    return list(top or nested or [])


def schema_mismatch(envelope: dict) -> str | None:
    """Say why this envelope cannot be trusted, or nothing if it can.

    Three outcomes rather than two, because *absent* and *different* are not the same
    fact. A version this build does not know is a wire contract that moved. An ABSENT
    version is an engine from before the field existed -- 0.1.6 and earlier shipped
    the same envelope shape without stamping it -- and the pin still admits those, so
    treating a missing stamp as a mismatch would refuse an engine this project
    supports.

    Reading it as `!= 1` alone would have collapsed both into one message and blamed
    the wrong thing for whichever it was.
    """
    meta = envelope.get("meta")
    if not isinstance(meta, dict) or "schema_version" not in meta:
        return None
    version = meta.get("schema_version")
    if version == ENVELOPE_SCHEMA_VERSION:
        return None
    return (f"the engine stamped this envelope schema_version {version!r}; this build "
            f"parses {ENVELOPE_SCHEMA_VERSION}. Every reading below -- findings, "
            f"declines, the {_vocabulary.noun()[0]} a finding names -- is keyed to "
            f"the shape that "
            f"version describes, so the run is reported as incomplete rather than "
            f"interpreted against a contract that moved")


def _describe_decline(decline: dict) -> str:
    entity = decline.get("entity_id", "?")
    axiom = decline.get("axiom", "?")
    reason = decline.get("reason", "?")
    detail = decline.get("detail")
    return f"{entity} [{axiom}] {reason}" + (f" -- {detail}" if detail else "")


def _is_expected_peer_decline(decline: dict, feed_result: Any) -> bool:
    """Whether a `missing_property` decline is the peer Stage 1 already reported.

    **The decline vocabulary is not one-dimensional, and reading it as though it
    were is a real defect this build had.** `missing_property` under BOUNDEDNESS
    means a value Stage 1 called present never reached the model -- a mapping bug,
    and the reason that reason fails the gate. Under CONSISTENCY it means the peer of
    a declared redundant pair is not carrying a reading, which the feeder already
    knows because it chose not to feed it, and which Stage 1 has already reported
    precisely as absence.

    Classified on `(axiom, reason)` AND cross-checked against what the feeder
    actually did, so a CONSISTENCY `missing_property` for a peer that WAS fed still
    fails the gate -- that one really is a mapping bug. Bucketing on `reason` alone
    failed the gate twice for one absent point, the second time asserting the name
    mapping was wrong when it was not.
    """
    if decline.get("axiom") != "CONSISTENCY":
        return False
    unfed = getattr(feed_result, "entities_missing_peers", None) or set()
    return str(decline.get("entity_id") or "") in unfed


def evaluate(envelope: dict, describe: dict, manifest: Manifest, *,
             strict_declines: bool = False, feed_result: Any = None) -> DetectOutcome:
    """Turn one engine envelope into a verdict a pipeline can act on."""
    outcome = DetectOutcome(checked=envelope.get("checked") or {},
                            strict=strict_declines)
    outcome.schema_mismatch = schema_mismatch(envelope)

    for finding in envelope.get("findings") or []:
        outcome.findings.append(manifest.translate_finding(finding))

    declines: Iterable[dict] = (envelope.get("not_checked")
                                or envelope.get("declines") or [])
    for decline in declines:
        reason = decline.get("reason")
        rendered = _describe_decline(decline)
        if reason in _CORE_CASE_REASONS and _is_expected_peer_decline(decline,
                                                                     feed_result):
            # A declared redundant peer that is not reading. Stage 1 has already
            # reported it as absent, precisely; counting it again here would fail the
            # gate twice for one fact and say the mapping was wrong, which it is not.
            outcome.data_declines.append(rendered)
        elif reason in _CORE_CASE_REASONS:
            # Stage 1 said this point was reading. If its value did not reach the
            # model, the mapping is wrong, and a mapping error is invisible unless
            # something fails on it.
            outcome.core_case_declines.append(rendered)
        elif reason in _DATA_SUFFICIENCY_REASONS:
            outcome.data_declines.append(rendered)
        elif reason in _MODEL_DEFECT_REASONS:
            # This package wrote the model. A declaration the engine cannot run
            # is ours, and it fails for the same reason a wrong mapping does.
            outcome.core_case_declines.append(rendered)
        elif (reason in _NOT_APPLICABLE_REASONS
                or reason in _PRECONDITION_REASONS
                or reason in _NO_THRESHOLD_REASONS):
            outcome.inapplicable_declines.append(rendered)
        else:
            # Not silently bucketed. A closed vocabulary with a missing member
            # reclassifies the case as its nearest neighbour and reports it with
            # confidence, which is worse than saying so.
            outcome.unclassified_declines.append(rendered)

    # Peer properties the model DOES declare, inside a `conservation` or
    # `consistency` block. The engine's unconsumed-observation report is built from
    # declared INDICATORS, so a peer reading fed for a cross-signal check arrives
    # there as `undeclared_property` -- and `unmapped` fails the gate, so a healthy
    # board with a declared flow would have exited 1 on every run.
    #
    # Filtered by (entity, property) pair rather than by prefix: a stray `peer_`
    # property on an entity that declares no such peer is still a mapping bug and
    # still reported.
    declared_peers = {
        (generated.entity_type, peer_property(peer))
        for generated in manifest.points
        for peer in generated.agrees_with + generated.flow_outputs}

    for unmapped in unmapped_observations(describe):
        entity = unmapped.get("entity_id", "?")
        prop = unmapped.get("property", "?")
        if (entity, prop) in declared_peers:
            continue
        outcome.unmapped.append(
            f"{entity}.{prop} "
            f"({unmapped.get('observations', '?')} observations, "
            f"{unmapped.get('reason', 'unread')})")

    return outcome
