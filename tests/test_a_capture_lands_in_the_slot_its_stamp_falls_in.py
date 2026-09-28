"""A capture fed by its stamp lands in the slot its own time falls in.

On the grid, `feed` places captures by their order: one slot each, the newest
one slot before the engine's clock, whatever each capture's `captured_at` says.
A capture that was never taken closes up, and a point read beside another that
missed one reading is cut at the miss, because a ladder cannot hold a gap.

`timed_by="captured_at"` places each capture instead at the slot of the grid its
stamp falls in, counted back from the newest stamp, and feeds `(instant, value)`
pairs. A pair carries its own time, so a missed capture or a missed reading is
an empty slot rather than a shift, and nothing is cut. What cannot be placed
that way -- a capture with no stamp or an unreadable one, captures out of
order, two captures in one slot -- is refused before anything is fed.

The readings of a capture below say which capture they came from, so a value
fed out of place names the slot it came from.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from presence_audit import diff                                  # noqa: E402
from presence_audit.conformance import (Capture, DeclarationSource,  # noqa: E402
                                        ReferenceVocabulary, SAMPLE_CAPTURE,
                                        SAMPLE_DECLARATION)
from presence_audit.feeder import (DetectOutcome, PlacementError,  # noqa: E402
                                   TIMED_BY_CAPTURE, TIMED_BY_INTERVAL, feed)
from presence_audit.generator import (GeneratedPoint, Manifest,  # noqa: E402
                                      READING)
from presence_audit.report import detect_as_text                 # noqa: E402

DRIVER, DRIVEN, ALONE = "DRIVER_POINT", "DRIVEN_POINT", "ALONE_POINT"
TYPES = {DRIVER: "driver_point", DRIVEN: "driven_point", ALONE: "alone_point"}
CADENCE = 300.0
START = datetime(2026, 9, 1, 12, 0, 0, tzinfo=timezone.utc)


@dataclass
class _Live:
    reading: float | None

    @property
    def is_reading(self) -> bool:
        return self.reading is not None


@dataclass
class _Declared:
    display_name: str


@dataclass
class _Match:
    declared: _Declared
    live: _Live


@dataclass
class _Report:
    matches: list
    captured_at: object = None


class _RecordingSession:
    """What the feeder asked the engine to do."""

    def __init__(self) -> None:
        self.observations: dict[tuple[str, str], list] = {}
        self.entities: list[str] = []

    def add_entity(self, entity_id, entity_type, properties=None):
        self.entities.append(entity_id)

    def add_observations(self, entity_id, prop, series, interval_seconds=None):
        self.observations[(entity_id, prop)] = list(series)

    def add_relationship(self, source, relation, target):
        pass

    def fed(self, name):
        return self.observations.get((TYPES[name], READING), [])


def _manifest(coupled=((DRIVER, DRIVEN),)):
    return Manifest(
        domain_id="probe",
        points=[GeneratedPoint(entity_type=TYPES[n], declared_name=n,
                               source="probe.json", upper=(None, 100000.0),
                               lower=(None, -100000.0)) for n in TYPES],
        coupled=list(coupled), sampling_interval_s=CADENCE)


def _value(name, slot):
    """A reading that names the slot it was taken in, in its last three digits."""
    return float(1000 * (list(TYPES).index(name) + 1) + slot)


def _reports(slots, *, missing=None, stamp=None):
    """One capture per slot number, oldest first, each stamped at its slot.

    `missing` maps a name to the slots it did not read at; `stamp` turns a
    slot's instant into the text its capture carries."""
    missing = missing or {}
    stamp = stamp or (lambda when, slot: when.isoformat())
    return [_Report(
        matches=[_Match(_Declared(n), _Live(None if slot in missing.get(n, ())
                                            else _value(n, slot)))
                 for n in TYPES],
        captured_at=stamp(START + timedelta(seconds=slot * CADENCE), slot))
        for slot in slots]


def _at(slot):
    return START + timedelta(seconds=slot * CADENCE)


def _fed(reports, **kwargs):
    session = _RecordingSession()
    result = feed(session, _manifest(), reports, timed_by=TIMED_BY_CAPTURE,
                  **kwargs)
    return session, result


class TestEachCaptureTakesTheSlotItsStampFallsIn:

    def test_every_reading_is_fed_at_its_own_captures_time(self):
        session, _ = _fed(_reports(range(6)))
        for name in TYPES:
            assert session.fed(name) == [(_at(s), _value(name, s)) for s in range(6)]

    def test_a_missed_reading_is_an_empty_slot_and_moves_nothing(self):
        session, result = _fed(_reports(range(6), missing={DRIVER: {3}}))
        assert session.fed(DRIVER) == [(_at(s), _value(DRIVER, s))
                                       for s in (0, 1, 2, 4, 5)]
        assert session.fed(DRIVEN) == [(_at(s), _value(DRIVEN, s)) for s in range(6)]
        assert result.cut == {}, "a pair holds its own time, so nothing is cut"

    def test_a_capture_that_was_never_taken_is_an_empty_slot(self):
        session, result = _fed(_reports([0, 1, 3, 4, 5]))
        assert [when for when, _ in session.fed(DRIVER)] == [_at(s) for s in (0, 1, 3, 4, 5)]
        assert (result.timing["captures"], result.timing["slots"],
                result.timing["empty_slots"]) == (5, 6, 1)

    def test_a_stamp_off_the_grid_takes_its_slot_and_the_distance_is_reported(self):
        jitter = {1: 20.0, 2: -25.0, 4: 7.0}

        def stamp(when, slot):
            return (when + timedelta(seconds=jitter.get(slot, 0.0))).isoformat()
        session, result = _fed(_reports(range(6), stamp=stamp))
        assert [when for when, _ in session.fed(DRIVEN)] == [_at(s) for s in range(6)]
        assert result.timing["largest_offset_s"] == 25.0

    @pytest.mark.parametrize("slots", [(0, 1, 2, 4), (0, 2, 5)],
                             ids=["odd-half", "even-half"])
    def test_half_an_interval_from_two_slots_takes_the_older_one(self, slots):
        """1.5 and 2.5 intervals back: rounding half to even would send the
        second to the newer slot, so both are asked."""
        def stamp(when, slot):
            return (when + timedelta(seconds=CADENCE / 2 if slot == 2 else 0)
                    ).isoformat()
        session, _ = _fed(_reports(slots, stamp=stamp))
        assert [when for when, _ in session.fed(ALONE)] == [_at(s) for s in slots]

    @pytest.mark.parametrize("spelling", [
        lambda when: when.strftime("%Y-%m-%dT%H:%M:%SZ"),
        lambda when: when.isoformat(),
        lambda when: when.astimezone(timezone(timedelta(hours=8))).isoformat(),
        lambda when: when.replace(tzinfo=None).isoformat(),
        lambda when: when,
    ], ids=["zulu", "offset", "another-zone", "no-zone-is-utc", "a-datetime"])
    def test_every_spelling_of_one_instant_is_one_instant(self, spelling):
        session, _ = _fed(_reports(range(3), stamp=lambda when, slot: spelling(when)))
        assert [when for when, _ in session.fed(DRIVER)] == [_at(s) for s in range(3)]

    def test_the_run_is_judged_as_of_its_newest_capture(self):
        _, result = _fed(_reports(range(6)))
        assert result.judged_at == _at(5)
        assert result.timing == {
            "timed_by": TIMED_BY_CAPTURE, "interval_seconds": CADENCE,
            "first": _at(0).isoformat(), "last": _at(5).isoformat(),
            "captures": 6, "slots": 6, "empty_slots": 0, "largest_offset_s": 0.0}

    def test_one_capture_is_one_slot_at_its_own_time(self):
        session, result = _fed(_reports([7]))
        assert session.fed(DRIVER) == [(_at(7), _value(DRIVER, 7))]
        assert result.judged_at == _at(7)


class TestTheGridIsStillTheDefaultAndUnchanged:

    def test_the_default_feeds_a_ladder_and_reads_no_stamp(self):
        session = _RecordingSession()
        result = feed(session, _manifest(), _reports([0, 1, 3, 4, 5]))
        assert session.fed(DRIVER) == [_value(DRIVER, s) for s in (0, 1, 3, 4, 5)]
        assert result.timing == {"timed_by": TIMED_BY_INTERVAL,
                                 "interval_seconds": CADENCE}
        assert result.judged_at is None

    def test_on_the_grid_a_joined_point_is_still_cut_at_its_miss(self):
        session = _RecordingSession()
        result = feed(session, _manifest(), _reports(range(6), missing={DRIVER: {3}}))
        assert session.fed(DRIVER) == [_value(DRIVER, s) for s in (4, 5)]
        assert result.cut[DRIVER]["missed"] == 4

    def test_an_unknown_placement_is_refused_by_name(self):
        with pytest.raises(ValueError, match="timed_by"):
            feed(_RecordingSession(), _manifest(), _reports(range(2)),
                 timed_by="wall_clock")


class TestWhatCannotBePlacedIsRefusedBeforeAnythingIsFed:

    def _refused(self, reports, match):
        session = _RecordingSession()
        with pytest.raises(PlacementError, match=match):
            feed(session, _manifest(), reports, timed_by=TIMED_BY_CAPTURE)
        assert session.entities == [] and session.observations == {}, (
            "a refused placement fed part of the run")

    def test_two_captures_in_one_slot(self):
        def stamp(when, slot):
            return (when + timedelta(seconds=100 if slot == 3 else 0)).isoformat()
        reports = _reports([0, 1, 2, 3], stamp=stamp)
        reports[3].captured_at = (_at(2) + timedelta(seconds=100)).isoformat()
        self._refused(reports, "captures 3 and 4 .* fall in one slot")

    def test_a_capture_with_no_stamp(self):
        reports = _reports(range(4))
        reports[1].captured_at = None
        self._refused(reports, "capture 2 of 4 carry no captured_at")

    def test_a_stamp_that_is_not_a_time(self):
        reports = _reports(range(3))
        reports[2].captured_at = "yesterday"
        self._refused(reports, "capture 3 .*'yesterday'.* cannot be read")

    def test_captures_out_of_the_order_their_stamps_give(self):
        reports = _reports(range(4))
        reports[1], reports[2] = reports[2], reports[1]
        self._refused(reports, "capture 3 is stamped no later")

    def test_two_captures_at_one_instant(self):
        reports = _reports(range(3))
        reports[2].captured_at = reports[1].captured_at
        self._refused(reports, "capture 3 is stamped no later")


class TestTheReportSaysWhichClock:

    def test_a_placement_by_stamp_is_printed_with_its_snap(self):
        _, result = _fed(_reports([0, 1, 3, 4, 5]))
        text = detect_as_text(DetectOutcome(), result)
        assert ("Placed by capture time -- 5 capture(s) in 6 slot(s) of 300 s, "
                "1 empty; the largest snap to a slot was 0 s, as of "
                f"{_at(5).isoformat()}") in text

    def test_a_run_on_the_grid_prints_what_it_always_printed(self):
        result = feed(_RecordingSession(), _manifest(), _reports(range(3)))
        assert "Placed by capture time" not in detect_as_text(DetectOutcome(), result)


class TestACapturesTimeReachesItsReport:

    def test_the_report_carries_the_time_its_capture_states(self):
        report = diff.compare(DeclarationSource(SAMPLE_DECLARATION),
                              Capture(SAMPLE_CAPTURE),
                              vocabulary=ReferenceVocabulary())
        assert report.captured_at == SAMPLE_CAPTURE["samples"][-1]["t"]

    def test_a_capture_without_the_member_still_compares(self):
        class _Untimed:
            def __init__(self, inner):
                self._inner = inner
            points = property(lambda s: s._inner.points)
            complete = property(lambda s: s._inner.complete)
            errors = property(lambda s: s._inner.errors)

        report = diff.compare(DeclarationSource(SAMPLE_DECLARATION),
                              _Untimed(Capture(SAMPLE_CAPTURE)),
                              vocabulary=ReferenceVocabulary())
        assert report.captured_at is None
