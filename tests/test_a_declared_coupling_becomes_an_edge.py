"""A coupling was parsed, validated, emitted -- and reached the engine as nothing.

**The defect, measured before it was fixed.** A supplemental file declaring one
coupling produced a `relationship_rules` entry in the generated model and a pair
in the manifest, and then nothing anywhere called `add_relationship`. A rule is a
statement about two TYPES; a fit needs an instance of it. So `model_describe`
reported `couplings_seen: 0`, and a run with a coupling declared was
indistinguishable from a run without one: no gain, no interval, and no refusal
saying why.

**And the grid was wrong underneath it.** This format REQUIRES
`sampling_interval_s` as soon as a coupling is declared, and refuses a
`propagation_delay_s` that is not a multiple of it -- because a delay off the
collection grid can align no pair of readings. `feed` then stamped every
observation sixty seconds apart whatever the file said. The file was validated
against one grid and fitted on another, and the load-time check and the feeder
never compared notes.

Measured end to end on a synthetic pair whose driven series was generated from
its driver at exactly one collection interval, the file declaring the real 300 s
cadence: **-0.0023 against a truth of +0.0040** -- wrong sign, r-squared 0.33,
and a confidence interval excluding the true value. That is the number an
`adopt` verb would have written into somebody's file with a sentence beside it
saying it was measured.

WHY IT SURVIVED THIS LONG, WHICH IS THE PART WORTH KEEPING. This package owns
the coupling format and REFUSES to depend on an engine, and its CI fails on any
skip -- so the half that needs one cannot be tested here. The vertical that has
the engine pin had never run a coupling end to end. The gap sat exactly on the
seam between two repositories, where neither suite could see it and both were
green.

So this file holds everything provable without an engine, against a recording
double: the edge is added, the grid is the file's, and an endpoint that did not
arrive is REPORTED. The end-to-end fit against a known truth lives in
`bmc-sensor-audit`, which is where the engine pin lives.
"""

from __future__ import annotations

import json
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from presence_audit import conformance, generator
from presence_audit.supplemental import load_supplemental

from presence_audit import feeder
from presence_audit.feeder import feed
from presence_audit.generator import (COUPLING_RELATION,
                                      DEFAULT_SAMPLE_INTERVAL_S,
                                      GeneratedSensor, Manifest, READING,
                                      WINDOW_SAMPLES, window_for)

DRIVER = "DRIVER_POINT"
DRIVEN = "DRIVEN_POINT"
DRIVER_TYPE = "driver_point"
DRIVEN_TYPE = "driven_point"
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
    """What the feeder asked the engine to do, in order.

    A double rather than the engine itself, because this package does not depend
    on one and its CI fails on a skip. What is asserted here is what the FEEDER
    did, which is the half that was wrong; what the engine then makes of it is
    asserted where the engine is installed.
    """

    def __init__(self) -> None:
        self.entities: list[tuple] = []
        self.observations: list[tuple] = []
        self.relationships: list[tuple] = []

    def add_entity(self, entity_id, entity_type, properties=None):
        self.entities.append((entity_id, entity_type, dict(properties or {})))

    def add_observations(self, entity_id, prop, series, interval_seconds=None):
        self.observations.append((entity_id, prop, list(series), interval_seconds))

    def add_relationship(self, source, relation, target):
        self.relationships.append((source, relation, target))


def _manifest(*, cadence=CADENCE, coupled=True):
    return Manifest(
        domain_id="probe",
        sensors=[
            GeneratedSensor(entity_type=DRIVER_TYPE, declared_name=DRIVER,
                            source="probe.json", upper=(None, 20000.0),
                            lower=(None, 500.0)),
            GeneratedSensor(entity_type=DRIVEN_TYPE, declared_name=DRIVEN,
                            source="probe.json", upper=(None, 85.0),
                            lower=(None, 5.0)),
        ],
        coupled=[(DRIVER, DRIVEN)] if coupled else [],
        sampling_interval_s=cadence,
    )


def _reports(count=4, *, driven_reading=41.0):
    out = []
    for index in range(count):
        out.append(_Report(matches=[
            _Match(_Declared(DRIVER), _Live(3000.0 + index)),
            _Match(_Declared(DRIVEN), _Live(driven_reading)),
        ]))
    return out


class TestTheCouplingBecomesAnEdge:

    def test_the_relationship_is_added(self):
        session = _RecordingSession()
        feed(session, _manifest(), _reports())
        assert session.relationships == [
            (DRIVER_TYPE, COUPLING_RELATION, DRIVEN_TYPE)], (
            "the declared coupling produced no edge, so a fit has no instance "
            "of the rule to run on and `couplings_seen` comes back 0")

    def test_the_result_says_which_ones_were_wired(self):
        """`manifest.coupled` says which became a RULE. That a rule exists is
        not the claim a reader needs: a rule with no edge under it is checked
        against nothing, and those were the same field until now."""
        result = feed(_RecordingSession(), _manifest(), _reports())
        assert result.coupled == [(DRIVER, DRIVEN)]
        assert not result.couplings_not_fed

    def test_a_run_with_no_coupling_adds_no_edge(self):
        session = _RecordingSession()
        feed(session, _manifest(coupled=False), _reports())
        assert session.relationships == []


class TestTheGridIsTheFilesAndNotThisModules:

    def test_observations_are_stamped_at_the_declared_cadence(self):
        session = _RecordingSession()
        feed(session, _manifest(), _reports())
        intervals = {interval for _id, prop, _series, interval
                     in session.observations if prop == READING}
        assert intervals == {CADENCE}, (
            f"observations were stamped at {intervals} against a declared "
            f"cadence of {CADENCE}; a delay validated on one grid and fitted "
            f"on another aligns the wrong pair of readings")

    def test_the_result_reports_the_grid_it_used(self):
        """A fitted gain is a statement about the spacing it was fitted at, and
        a reader comparing one against a datasheet cannot check it otherwise."""
        assert feed(_RecordingSession(), _manifest(),
                    _reports()).interval_seconds == CADENCE

    def test_the_default_applies_only_where_nothing_was_declared(self):
        """The cadence is required exactly when a coupling is -- so this path
        is the one where no coupling exists, and the number this module picks
        is overruling nobody."""
        result = feed(_RecordingSession(), _manifest(cadence=None, coupled=False),
                      _reports())
        assert result.interval_seconds == DEFAULT_SAMPLE_INTERVAL_S

    def test_the_default_is_the_number_that_was_always_used(self):
        """Pinned so the fix cannot become a behaviour change for every model
        that declares no coupling: those were fed at sixty seconds before this
        and are fed at sixty seconds after it."""
        assert DEFAULT_SAMPLE_INTERVAL_S == 60.0


class TestAnEndpointThatDidNotArriveIsReported:
    """Same rule the declared pairings already follow. A coupling that produced
    no edge contributes no fit AND no refusal, so silence here reads exactly
    like a coupling the data agreed with."""

    def test_a_driven_point_that_is_not_reading_stops_the_edge(self):
        session = _RecordingSession()
        feed(session, _manifest(), _reports(driven_reading=None))
        assert session.relationships == []

    def test_and_it_is_recorded_rather_than_dropped(self):
        result = feed(_RecordingSession(), _manifest(),
                      _reports(driven_reading=None))
        assert result.couplings_not_fed == [
            {"from": DRIVER, "to": DRIVEN, "reason": "endpoint_not_fed",
             "missing": [DRIVEN]}]
        assert result.coupled == []

    def test_a_name_the_manifest_never_modelled_is_named_too(self):
        manifest = _manifest()
        manifest.coupled = [(DRIVER, "NEVER_MODELLED")]
        result = feed(_RecordingSession(), manifest, _reports())
        assert result.couplings_not_fed[0]["missing"] == ["NEVER_MODELLED"]


class TestTheManifestCarriesTheCadence:
    """It travels on the manifest rather than as a second argument to `feed`
    because it is a generation-time fact about the declaration, and because
    `--manifest-out` then records the grid the run was fitted on."""

    def test_it_is_serialised(self):
        assert _manifest().to_dict()["sampling_interval_s"] == CADENCE

    def test_it_is_absent_rather_than_defaulted_when_nothing_declared_one(self):
        assert Manifest(domain_id="x").to_dict()["sampling_interval_s"] is None


class TestTheWindowIsMeasuredInSamplesAndNotInMinutes:
    """The consequence of the fix above, and it nearly shipped unnoticed.

    `window:` is a hard CEILING on how many observations can ever be counted,
    so it only means anything relative to the collection cadence. It was the
    fixed string `"15m"`, which was right only because the feeder stamped every
    sample sixty seconds apart -- 15 minutes over 60 seconds, less the one that
    falls on the boundary, is fourteen against a floor of ten.

    Feeding at the DECLARED cadence changed the divisor and nothing else. At
    five minutes a fifteen-minute window holds TWO. Measured end to end before
    this was fixed: two completely frozen sensors over forty walks produced no
    finding at all and declined `insufficient_samples` -- which reads as still
    warming up and never clears, at any number of walks.

    So the two halves of one arithmetic now live in one module, and this
    asserts the RELATIONSHIP rather than the numbers: tuning any of the three
    stays possible, tuning them into a dead zone does not.
    """

    @pytest.mark.parametrize("interval", [10.0, 30.0, 60.0, 300.0, 900.0])
    def test_the_window_holds_more_samples_than_the_floor_at_any_cadence(
            self, interval):
        window = window_for(interval)
        seconds = (float(window[:-1]) * 60 if window.endswith("m")
                   else float(window[:-1]))
        capacity = seconds / interval - 1
        assert capacity >= feeder.STUCK_AT_SAMPLE_FLOOR, (
            f"a {window} window at {interval:g}s per sample holds "
            f"{capacity:g} observations and STABILITY needs "
            f"{feeder.STUCK_AT_SAMPLE_FLOOR}; liveness would decline "
            f"insufficient_samples forever, at any number of walks")

    def test_the_sample_count_carries_the_margin_it_always_had(self):
        """One boundary sample is lost, and the rest is headroom. Asserted so a
        reduction to exactly the floor -- which passes the test above and leaves
        nothing for a walk that arrives late -- is a deliberate edit."""
        assert WINDOW_SAMPLES - 1 >= feeder.STUCK_AT_SAMPLE_FLOOR + 4

    def test_the_default_cadence_generates_exactly_what_it_always_did(self):
        """The compatibility claim. A board that was being fed correctly at
        sixty seconds must see no change at all from this, and `15m` is the
        string every model this package has generated so far carries."""
        assert window_for(DEFAULT_SAMPLE_INTERVAL_S) == "15m"
        assert window_for(None) == "15m"

    def test_it_is_a_duration_the_engine_parses(self):
        for interval in (10.0, 60.0, 300.0):
            window = window_for(interval)
            assert window[-1] in "smhd" and window[:-1], window

    def test_a_generated_indicator_carries_the_scaled_window(self):
        """Through `generate`, not through `window_for` -- the function being
        right is not the claim; the indicator carrying its answer is. The
        cadence is read from the supplemental in one place and the sensor loop
        runs before the coupling block, which is where this nearly went wrong."""
        from presence_audit import conformance
        model, manifest = _generate_with_cadence(300.0)
        windows = {spec["window"]
                   for specs in model["domain"]["indicators"].values()
                   for spec in specs if "window" in spec}
        assert windows == {"75m"}, windows
        assert manifest.sampling_interval_s == 300.0


# --- generating a real model, to check the cadence reaches the indicators ----

@dataclass
class _Threshold:
    bound: str
    level: str
    value: float
    is_upper: bool = True


@dataclass
class _Point:
    display_name: str
    type: str
    thresholds: list = field(default_factory=list)
    source: str = "declaration"
    disabled: bool = False
    is_templated: bool = False
    expects_reading = None

    @property
    def name(self) -> str:
        return self.display_name


@dataclass
class _Declaration:
    points: list
    anomalies: list = field(default_factory=list)
    sources: list = field(default_factory=list)


def _generate_with_cadence(cadence: float):
    doc = {
        "format": "presence-audit/supplemental/2",
        "provenance": "a fixture; states nothing about any machine",
        "sampling_interval_s": cadence,
        "couplings": [{"from": DRIVER, "to": DRIVEN,
                       "propagation_delay_s": cadence,
                       "time_constant_s": cadence,
                       "response_model": "step", "gain": "estimate",
                       "basis": "a fixture"}],
    }
    path = Path(tempfile.mkdtemp()) / "supplemental.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    declaration = _Declaration(points=[
        _Point(DRIVER, "speed"),
        _Point(DRIVEN, "distance",
               [_Threshold("upper", "warning", 40.0),
                _Threshold("upper", "critical", 45.0)]),
    ])
    return generator.generate(declaration, domain_id="bench",
                              supplemental=load_supplemental(path),
                              vocabulary=conformance.ReferenceVocabulary())
