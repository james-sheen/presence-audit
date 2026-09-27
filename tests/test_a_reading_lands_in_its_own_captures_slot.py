"""A reading is fed in the slot of the capture it came from, or not at all.

`feed` sends each point's history to the engine as a ladder: one reading per
grid slot, the newest one slot before the engine's clock. A ladder cannot say
*nothing here*. Until 0.2.3 each point's history was simply the readings it
had, so a capture where the point did not read closed up, and every reading
before it landed one slot later than the capture it came from -- while every
point that did read stayed where it was.

**For a point read beside another, that is a wrong answer rather than a
blurred one.** Measured through `bmc-sensor-audit adopt` on a driven series
generated from its driver at exactly one interval, 200 captures, true gain
0.004: one missed driver reading at capture 191 fitted -0.0021 with an interval
of [-0.0026, -0.0016]. Stamped and unstamped captures gave the same number,
because nothing reads the stamps.

This file holds, against a recording double, what the feeder now does:
a joined series is fed its unbroken run ending at the last capture, so every
reading it feeds is in its own capture's slot; the rest is counted in
`FeedResult.cut`; and everything that was never out of place is fed exactly as
before. What the engine then fits lives in the vertical that pins one.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from presence_audit import vocabulary as V                     # noqa: E402
from presence_audit.conformance import ReferenceVocabulary     # noqa: E402
from presence_audit.feeder import DetectOutcome, feed          # noqa: E402
from presence_audit.generator import (GeneratedPoint, Manifest,  # noqa: E402
                                      READING, peer_property)
from presence_audit.report import detect_as_text               # noqa: E402

DRIVER, DRIVEN, ALONE = "DRIVER_POINT", "DRIVEN_POINT", "ALONE_POINT"
SOURCE, SINK = "SOURCE_POINT", "SINK_POINT"
TYPES = {DRIVER: "driver_point", DRIVEN: "driven_point", ALONE: "alone_point",
         SOURCE: "source_point", SINK: "sink_point"}
CAPTURES = 6
CADENCE = 300.0


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


class _RecordingSession:
    """What the feeder asked the engine to do. A double, because this package
    does not depend on an engine and its CI fails on a skip."""

    def __init__(self) -> None:
        self.observations: dict[tuple[str, str], tuple[list, float]] = {}

    def add_entity(self, entity_id, entity_type, properties=None):
        pass

    def add_observations(self, entity_id, prop, series, interval_seconds=None):
        self.observations[(entity_id, prop)] = (list(series), interval_seconds)

    def add_relationship(self, source, relation, target):
        pass

    def fed(self, name, prop=READING):
        return self.observations.get((TYPES[name], prop), ([], None))[0]


def _point(name, *, outputs=()):
    return GeneratedPoint(entity_type=TYPES[name], declared_name=name,
                          source="probe.json", upper=(None, 100000.0),
                          lower=(None, -100000.0), flow_outputs=tuple(outputs))


def _manifest(*, coupled=(), channeled=(), flows=None):
    flows = flows or {}
    names = [DRIVER, DRIVEN, ALONE, SOURCE, SINK]
    return Manifest(domain_id="probe",
                    points=[_point(n, outputs=flows.get(n, ())) for n in names],
                    coupled=list(coupled), channeled=list(channeled),
                    sampling_interval_s=CADENCE)


def _value(name, position):
    """A reading that says which capture it came from: the position is in the
    last three digits, so a value fed out of place names the slot it came from."""
    return float(1000 * (list(TYPES).index(name) + 1) + position)


def _reports(missing=None):
    """`CAPTURES` captures; `missing` maps a name to the positions it did not
    read at. Every point is present in every capture -- a missed reading is a
    match whose reading is None, which is how a vertical reports one."""
    missing = missing or {}
    out = []
    for position in range(CAPTURES):
        out.append(_Report(matches=[
            _Match(_Declared(name),
                   _Live(None if position in missing.get(name, ()) else
                         _value(name, position)))
            for name in TYPES]))
    return out


def _slots(series):
    """Where the engine puts each value of a ladder: the newest one slot before
    its clock, so value i of n goes to the capture at position last - (n-1-i)."""
    last = CAPTURES - 1
    return [last - (len(series) - 1 - i) for i in range(len(series))]


COUPLED = {"coupled": [(DRIVER, DRIVEN)]}


class TestAJoinedSeriesIsFedWhereItsPositionsAreKnown:

    def test_a_missed_reading_cuts_the_run_to_the_captures_after_it(self):
        session = _RecordingSession()
        feed(session, _manifest(**COUPLED), _reports({DRIVER: {2}}))
        assert session.fed(DRIVER) == [_value(DRIVER, p) for p in (3, 4, 5)]
        assert session.fed(DRIVEN) == [_value(DRIVEN, p) for p in range(CAPTURES)]

    def test_every_reading_it_feeds_is_in_its_own_captures_slot(self):
        """The invariant itself, rather than the rule that produces it: decode
        each fed value's capture and compare it with the slot the engine gives
        it. The old feeder fails this for every reading before the gap."""
        session = _RecordingSession()
        feed(session, _manifest(**COUPLED), _reports({DRIVER: {2}, DRIVEN: {4}}))
        for name in (DRIVER, DRIVEN):
            series = session.fed(name)
            assert series, name
            assert [int(v) % 1000 for v in series] == _slots(series), name

    def test_the_cut_is_reported_with_what_it_cost(self):
        result = feed(_RecordingSession(), _manifest(**COUPLED),
                      _reports({DRIVER: {2}}))
        assert result.cut == {DRIVER: {"fed": 3, "not_fed": 2, "missed": 3,
                                       "captures": CAPTURES}}
        assert result.samples[DRIVER] == 3

    def test_the_driven_end_is_cut_the_same_way(self):
        session = _RecordingSession()
        result = feed(session, _manifest(**COUPLED), _reports({DRIVEN: {1}}))
        assert session.fed(DRIVEN) == [_value(DRIVEN, p) for p in (2, 3, 4, 5)]
        assert set(result.cut) == {DRIVEN}

    def test_captures_before_its_first_reading_are_not_a_gap(self):
        """A point that began reading late already lands in its own slots: the
        ladder is anchored at the newest reading, and nothing after it is
        missing."""
        session = _RecordingSession()
        result = feed(session, _manifest(**COUPLED), _reports({DRIVER: {0, 1}}))
        assert session.fed(DRIVER) == [_value(DRIVER, p) for p in (2, 3, 4, 5)]
        assert result.cut == {}

    def test_a_complete_series_is_fed_exactly_as_before(self):
        session = _RecordingSession()
        result = feed(session, _manifest(**COUPLED), _reports())
        for name in (DRIVER, DRIVEN):
            assert session.observations[(TYPES[name], READING)] == (
                [_value(name, p) for p in range(CAPTURES)], CADENCE)
        assert result.cut == {}


class TestAPointReadAloneIsFedAsBefore:
    """Deliberately unchanged. Its closed-up history still answers stuck-at, and
    cutting it would return a point that both sticks and stops reading to
    warm-up every time it stopped."""

    def test_it_keeps_every_reading_and_nothing_is_reported(self):
        session = _RecordingSession()
        result = feed(session, _manifest(**COUPLED), _reports({ALONE: {2}}))
        assert session.fed(ALONE) == [_value(ALONE, p) for p in (0, 1, 3, 4, 5)]
        assert ALONE not in result.cut


class TestEveryPairingIsJoined:

    def test_the_endpoints_of_a_fault_channel(self):
        session = _RecordingSession()
        result = feed(session, _manifest(channeled=[(DRIVER, DRIVEN)]),
                      _reports({DRIVER: {2}}))
        assert session.fed(DRIVER) == [_value(DRIVER, p) for p in (3, 4, 5)]
        assert set(result.cut) == {DRIVER}

    def test_a_flows_input_and_output(self):
        session = _RecordingSession()
        result = feed(session, _manifest(flows={SOURCE: [SINK]}),
                      _reports({SOURCE: {1}, SINK: {3}}))
        assert session.fed(SOURCE) == [_value(SOURCE, p) for p in (2, 3, 4, 5)]
        carried = session.fed(SOURCE, peer_property(SINK))
        assert carried == [_value(SINK, p) for p in (4, 5)]
        assert set(result.cut) == {SOURCE, SINK}

    def test_an_output_not_reading_now_carries_no_history(self):
        """Its newest reading is from an earlier capture, so the ladder would
        put it one slot or more too late. Nothing of it can be placed."""
        session = _RecordingSession()
        result = feed(session, _manifest(flows={SOURCE: [SINK]}),
                      _reports({SINK: {CAPTURES - 1}}))
        assert session.fed(SOURCE, peer_property(SINK)) == []
        assert result.cut[SINK] == {"fed": 0, "not_fed": CAPTURES - 1,
                                    "missed": CAPTURES, "captures": CAPTURES}


class TestTheReportSaysSo:

    @pytest.fixture
    def reference(self):
        previous = V._REGISTERED
        V.reset()
        V.register(ReferenceVocabulary())
        try:
            yield
        finally:
            V._REGISTERED = previous

    def test_detect_names_each_cut_and_what_it_cost(self, reference):
        result = feed(_RecordingSession(), _manifest(**COUPLED),
                      _reports({DRIVER: {2}}))
        text = detect_as_text(DetectOutcome(), result)
        assert "Fed from a missed reading on -- 1" in text
        assert f"{DRIVER}: 3 fed, 2 not; missed capture 3 of {CAPTURES}" in text

    def test_and_says_nothing_when_nothing_was_cut(self, reference):
        result = feed(_RecordingSession(), _manifest(**COUPLED), _reports())
        assert "Fed from a missed reading on" not in detect_as_text(
            DetectOutcome(), result)
