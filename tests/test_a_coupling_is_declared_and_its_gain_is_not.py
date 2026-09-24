"""A coupling states that one reading drives another. It usually cannot state by how much.

This format's rule is that an operator claim carries what establishes it -- a floor is
a specification, not a guess. A coupling has two claims in it and they are not the same
kind of thing:

**That A drives B** is structural. Somebody who knows the installation knows it, and
writing it down is exactly what this file is for.

**By how much** is a coefficient, and almost nobody has one. Inventing it to make a
simulation run would put a guess in the one place this format exists to refuse one. So
the gain may be withheld -- `gain: estimate` -- and the engine then fits it from
history, reports it with its `n`, its `r_squared` and an interval, and projects nothing
until a human writes a number down.

THE GRID CONSTRAINT WAS MEASURED, NOT REASONED. The engine aligns the two series on
their shared sampling grid, so a `propagation_delay_s` that is not a whole number of
collection steps can align no pair of readings at all: it declines `delay_off_grid` and
the coupling contributes nothing, from a file that reads as correct. That was found by
running it before this format was designed -- a delay of 60 s against a five-minute
cadence -- and it is why `sampling_interval_s` is required here rather than optional.

WHAT THIS FILE DOES NOT ASSERT. Not the fitted number: that is the engine's and it
moves with the data. What is pinned is that a declaration reaches the model, that an
endpoint the model does not carry is REPORTED rather than dropped, and that every
refusal this format makes is a refusal rather than a warning.
"""

from __future__ import annotations

import json
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from presence_audit import conformance, generator
from presence_audit.supplemental import (ESTIMATE, FORMAT,
                                         FORMATS_WITHOUT_COUPLINGS,
                                         RESPONSE_MODELS, Coupling,
                                         Supplemental, SupplementalError,
                                         load_supplemental, unmatched_names)


# --------------------------------------------------------------------------
# Stand-ins: exactly the protocol members the generator reads, and no more.
# --------------------------------------------------------------------------

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


DRIVER, DRIVEN = "DRIVER_POINT", "DRIVEN_POINT"

#: A whole coupling, valid. Every refusal test below is this with one thing wrong,
#: so the difference between the two is the thing under test and nothing else.
WHOLE = {"from": DRIVER, "to": DRIVEN,
         "propagation_delay_s": 300, "time_constant_s": 600,
         "gain": ESTIMATE, "basis": "the first moves the medium the second reads"}

INTERVAL = 300


def _file(**overrides) -> Path:
    doc = {"format": FORMAT, "provenance": "a bench",
           "sampling_interval_s": INTERVAL, "couplings": [dict(WHOLE)]}
    doc.update(overrides)
    path = Path(tempfile.mkdtemp()) / "supplemental.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    return path


def _with(**changes) -> Path:
    return _file(couplings=[{**WHOLE, **changes}])


def _points(driven_type: str = "distance", driver_type: str = "speed") -> list:
    """A driver with NO bounds at all, and a driven point with a band.

    The driver having none is the interesting half: the ordinary exclusion rule
    drops a point with nothing to bound against, so a coupling naming one has to
    be what keeps it in the model.
    """
    return [_Point(DRIVER, driver_type),
            _Point(DRIVEN, driven_type,
                   [_Threshold("upper", "warning", 40.0),
                    _Threshold("upper", "critical", 45.0)])]


def _generate(path: Path, points=None):
    return generator.generate(
        _Declaration(points=points if points is not None else _points()),
        domain_id="bench", supplemental=load_supplemental(path),
        vocabulary=conformance.ReferenceVocabulary())


class TestTheFileIsReadStrictly:
    """Every one of these is a refusal, never a warning. A malformed coupling that
    loaded anyway declares a chain the engine was never asked about, and the run
    reports nothing because nothing was checked."""

    def test_a_whole_coupling_loads(self):
        loaded = load_supplemental(_file())
        assert len(loaded.couplings) == 1
        assert loaded.couplings[0].gain_is_withheld
        assert loaded.sampling_interval_s == INTERVAL

    @pytest.mark.parametrize("changes,because", [
        ({"to": DRIVER}, "both ends the same"),
        ({"propagation_delay_s": 60}, "a delay off the sampling grid"),
        ({"time_constant_s": 0}, "a settling time of nought"),
        ({"response_model": "immediate"}, "a response model the engine lacks"),
        ({"gain": 0.0, "gain_basis": "x"}, "a gain of zero"),
        ({"gain": -0.003}, "a number with nothing establishing it"),
        ({"gain_basis": "x"}, "a basis for a number that was withheld"),
    ])
    def test_it_refuses(self, changes, because):
        with pytest.raises(SupplementalError):
            load_supplemental(_with(**changes))

    @pytest.mark.parametrize("key", ["from", "to", "basis",
                                     "propagation_delay_s", "time_constant_s"])
    def test_every_required_key_is_required(self, key):
        with pytest.raises(SupplementalError):
            load_supplemental(_file(
                couplings=[{k: v for k, v in WHOLE.items() if k != key}]))

    def test_a_coupling_without_a_cadence_is_refused(self):
        """The grid cannot be checked without it, and an unchecked delay is the
        silent case this whole constraint exists for."""
        doc = {"format": FORMAT, "provenance": "a bench",
               "couplings": [dict(WHOLE)]}
        path = Path(tempfile.mkdtemp()) / "s.json"
        path.write_text(json.dumps(doc), encoding="utf-8")
        with pytest.raises(SupplementalError, match="sampling_interval_s"):
            load_supplemental(path)

    def test_the_grid_refusal_shows_the_arithmetic(self):
        """A reader has to be able to fix it without running anything. The message
        carries both numbers and the quotient, because *off the grid* alone leaves
        them to work out which of the two to change."""
        with pytest.raises(SupplementalError) as raised:
            load_supplemental(_with(propagation_delay_s=450))
        message = str(raised.value)
        assert "450" in message and str(INTERVAL) in message
        assert "1.5" in message, "the quotient is not shown"

    def test_a_delay_of_zero_is_allowed(self):
        """Nought steps IS on the grid, and a coupling with no transport lag is a
        real thing -- the engine's `step` response model is exactly that shape.

        The sentence here said the engine has an *immediate* response model. It
        does not and never has; that word is a leftover from the draft of
        `RESPONSE_MODELS` that was written from memory, and it survived into a
        docstring one line below the parametrised case that uses the same word as
        an example of something the engine REFUSES."""
        assert load_supplemental(_with(propagation_delay_s=0)).couplings


class TestTheGainIsTheOperatorsClaimAboutMeasurement:

    def test_withheld_is_the_default(self):
        loaded = load_supplemental(_file(
            couplings=[{k: v for k, v in WHOLE.items() if k != "gain"}]))
        assert loaded.couplings[0].gain == ESTIMATE
        assert loaded.couplings[0].gain_is_withheld

    def test_a_number_with_a_basis_is_accepted_and_is_not_withheld(self):
        loaded = load_supplemental(_with(gain=-0.003, gain_basis="a datasheet"))
        assert loaded.couplings[0].gain == pytest.approx(-0.003)
        assert not loaded.couplings[0].gain_is_withheld

    def test_the_two_are_carried_to_the_engine_differently(self):
        """The whole point of the distinction. A withheld gain reaches the model as
        the engine's own word for it; a stated one reaches it as the number."""
        withheld, _ = _generate(_file())
        stated, _ = _generate(_with(gain=-0.003, gain_basis="a datasheet"))
        rule_w = withheld["domain"]["relationship_rules"][0]["transition"]
        rule_s = stated["domain"]["relationship_rules"][0]["transition"]
        assert rule_w["gain"] == ESTIMATE
        assert rule_s["gain"] == pytest.approx(-0.003)
        assert rule_s["source"] == "a datasheet", (
            "a stated gain must carry its own basis into the model, not the "
            "coupling's structural one")


class TestADeclarationReachesTheModel:

    def test_the_rule_names_the_generated_types_not_the_declared_names(self):
        model, manifest = _generate(_file())
        rule = model["domain"]["relationship_rules"][0]
        types = {s.declared_name: s.entity_type for s in manifest.sensors}
        assert rule["source_type"] == types[DRIVER]
        assert rule["target_type"] == types[DRIVEN]
        assert rule["type"] in model["domain"]["relationship_types"]

    def test_the_time_course_travels(self):
        rule = _generate(_file())[0]["domain"]["relationship_rules"][0]
        assert rule["temporal"] == {"propagation_delay_s": 300.0,
                                    "time_constant_s": 600.0,
                                    "response_model": "exponential"}

    def test_a_point_with_no_bounds_is_modelled_because_a_coupling_names_it(self):
        """The driver carries no thresholds, so the ordinary rule excludes it. A
        coupling naming it is what asks the question -- the same argument the flow
        participants already win on."""
        model, manifest = _generate(_file())
        assert DRIVER in model["domain"]["entity_types"]
        assert not [s for s in manifest.sensors
                    if s.declared_name == DRIVER and (s.upper != (None, None)
                                                      or s.lower != (None, None))]

    def test_the_driver_gets_a_projector(self):
        """Measured: without one a rollout that lets the world drift completes
        nought steps and declines `model_missing`."""
        model, _ = _generate(_file())
        driver = model["domain"]["indicators"][DRIVER]
        assert any(spec.get("dynamics") for spec in driver), driver

    def test_a_model_with_no_couplings_grows_no_keys(self):
        """An empty block must not add `relationship_rules: []` to every model this
        core has ever generated -- a key that is present and empty reads as a
        capability that ran and found nothing."""
        model, _ = _generate(_file(couplings=[]))
        assert "relationship_rules" not in model["domain"]
        assert "relationship_types" not in model["domain"]


class TestNothingIsDroppedInSilence:
    """The generator's own rule, applied to the new block: a generator that
    silently drops what it cannot express produces a model that looks complete."""

    def test_an_endpoint_the_model_does_not_carry_is_reported(self):
        """The real case is an endpoint that was DECLARED and then excluded -- an
        unreadable type, a disabled entry -- because a name the declaration never
        had is caught earlier by `unmatched_names`."""
        model, manifest = _generate(
            _file(), points=[_Point(DRIVER, "speed"),
                             _Point(DRIVEN, "a type the vocabulary refuses",
                                    [_Threshold("upper", "warning", 40.0)])])
        assert "relationship_rules" not in model["domain"]
        assert manifest.uncoupled == [
            {"from": DRIVER, "to": DRIVEN,
             "reason": "endpoint_not_modelled", "missing": [DRIVEN]}]
        assert manifest.counts()["couplings_not_expressed"] == 1
        assert manifest.counts()["couplings"] == 0

    def test_the_reason_it_was_excluded_is_readable_beside_it(self):
        """Reporting the coupling without the exclusion leaves a reader knowing
        that something failed and not why."""
        _, manifest = _generate(
            _file(), points=[_Point(DRIVER, "speed"),
                             _Point(DRIVEN, "a type the vocabulary refuses",
                                    [_Threshold("upper", "warning", 40.0)])])
        assert DRIVEN in [n for names in manifest.excluded.values() for n in names]

    def test_both_counts_are_in_the_manifest(self):
        _, manifest = _generate(_file())
        assert manifest.counts()["couplings"] == 1
        assert manifest.counts()["couplings_not_expressed"] == 0
        assert manifest.coupled == [(DRIVER, DRIVEN)]

    def test_the_manifest_serialises_them(self):
        """It is an artifact somebody commits and reads later."""
        _, manifest = _generate(_file())
        emitted = manifest.to_dict()
        assert emitted["coupled"] == [[DRIVER, DRIVEN]]
        assert emitted["uncoupled"] == []


class TestATypoIsCaughtByTheMechanismThatAlreadyExists:

    def test_a_coupling_endpoint_joins_the_cross_check(self):
        """`unmatched_names` is how every other block catches a misspelling. A
        coupling that routed around it would be the one entry in this file whose
        typo is silent."""
        loaded = load_supplemental(_with(**{"to": "NOT_DECLARED"}))
        assert unmatched_names(loaded, {DRIVER}) == ["NOT_DECLARED"]

    def test_both_ends_are_in_the_names_the_file_mentions(self):
        loaded = load_supplemental(_file())
        assert {DRIVER, DRIVEN} <= loaded.names()


class TestTheRestatedEnumIsWellFormed:
    """A restated DEFAULT drifts a number; a restated CLOSED ENUM refuses a value
    the engine accepts, or accepts one it does not. So it has to be checked.

    **AND IT CANNOT BE CHECKED HERE.** Stage 1 does not import the engine and will
    not depend on it, so the comparison needs an environment this package refuses
    to require. The first version of this reached for `importorskip` -- and this
    repository's CI fails on ANY skip, for a reason it states: a skip means the
    test that adapts a really published implementation went unrun, and its absence
    is invisible in a green run. A guard that goes quiet where it matters is worse
    than one that lives somewhere else.

    So what runs here is the half that can: the tuple is a closed set of distinct
    non-empty strings, which catches a fat-fingered edit. **The comparison against
    the engine's own enum belongs in a vertical**, which is where the engine pin
    already lives -- this package's README gives that as the reason the pin is not
    here either.
    """

    def test_it_is_a_closed_set_of_distinct_names(self):
        assert RESPONSE_MODELS, "the restatement is empty; nothing would validate"
        assert len(set(RESPONSE_MODELS)) == len(RESPONSE_MODELS), RESPONSE_MODELS
        assert all(isinstance(m, str) and m.strip() for m in RESPONSE_MODELS)

    def test_the_loader_accepts_exactly_those_and_no_others(self):
        """The set is not decoration: it is what the loader admits. Checked
        against the loader rather than asserted, so a member added to the tuple
        and not reaching the check would be caught."""
        for model in RESPONSE_MODELS:
            assert load_supplemental(
                _with(response_model=model)).couplings[0].response_model == model
        with pytest.raises(SupplementalError):
            load_supplemental(_with(response_model="not_a_response_model"))


class TestTheShapeItself:

    def test_a_coupling_knows_its_members(self):
        coupling = Coupling(source="A", target="B", basis="b",
                            propagation_delay_s=0, time_constant_s=1)
        assert coupling.members == ("A", "B")

    def test_a_file_carrying_only_couplings_is_not_empty(self):
        """`__bool__` gates whether the caller reports the file at all."""
        assert bool(Supplemental(couplings=[
            Coupling(source="A", target="B", basis="b",
                     propagation_delay_s=0, time_constant_s=1)]))


class TestAnOlderReaderIsTOLDRatherThanLeftToIgnoreIt:
    """The version-skew half, and it was found by asking what a build WITHOUT this
    change does with a file that has it.

    Measured on such a build: the file loads without error, the couplings are
    dropped, and `bool(supplemental)` is False -- so the caller reports no
    declarations at all. An operator gets a clean run in which nothing they wrote
    was read, which is the failure this module's first paragraph refuses for a
    malformed entry, arriving through the version skew instead.
    """

    @pytest.mark.parametrize("older", FORMATS_WITHOUT_COUPLINGS)
    def test_a_coupling_under_an_older_format_is_refused(self, older):
        with pytest.raises(SupplementalError) as raised:
            load_supplemental(_file(format=older))
        assert FORMAT in str(raised.value), (
            "the refusal does not name the format to use instead")

    @pytest.mark.parametrize("older", FORMATS_WITHOUT_COUPLINGS)
    def test_those_formats_still_read_everything_they_ever_did(self, older):
        """The bump must not retire them. Their shape is a subset of this one and
        a file written before it is still this document."""
        loaded = load_supplemental(_file(format=older, couplings=[],
                                          counters=[{"sensor": "C",
                                                     "basis": "it climbs"}]))
        assert [c.sensor for c in loaded.counters] == ["C"]

    def test_the_current_format_is_the_one_couplings_need(self):
        assert FORMAT not in FORMATS_WITHOUT_COUPLINGS
        assert load_supplemental(_file()).couplings

