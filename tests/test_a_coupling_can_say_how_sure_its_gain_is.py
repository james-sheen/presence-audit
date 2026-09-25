"""A coupling can say how sure its gain is.

The engine's `gain_sigma:` is how sure anyone is of a coupling's gain -- a
datasheet's plus-or-minus, or a fit's standard error -- and it widens the band
around every value the coupling drives by the gain's own doubt. Format 2 had no
field for it and refused the key by name, so that band always treated the gain
as exact and a datasheet tolerance could not be written down at all.

**IT IS NOT WHAT MAKES A PROJECTION GRADEABLE, AND THAT WAS MEASURED.** It was
filed as the reason a vertical's coupling was never graded; the reason was the
vertical's rollout, seeded from current readings with no action, which moves
nothing -- so a declared spread filed nothing either. Seeded from the driver's
forecast, the adopted gain was graded with or without one -- a CRPS of 0.10918
either way, the spread adding the gain's doubt to a band the forecast's doubt
dominated.

Format 3 carries the spread, with a basis of its own. Pinned here:

* it is READ and it REACHES THE MODEL -- 0.1.10's lesson was a block this build
  parsed, validated and never delivered, so a run with it was byte-identical to
  a run without;
* every way of stating one that the engine would read as no spread, or that
  is a spread on no number, is refused rather than loaded;
* a format 2 file carrying one names the id to use;
* and nothing a format 2 document said changes.

Whether the ENGINE reads it back is checked in a vertical, where the engine pin
lives: this repository's CI fails on any skip, and the engine is not a
dependency here.
"""

from __future__ import annotations

import json
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from presence_audit import conformance, generator
from presence_audit.supplemental import (ACCEPTED_FORMATS,
                                         COUPLING_KEYS_BY_FORMAT, FORMAT,
                                         SupplementalError, load_supplemental)

PREVIOUS = "presence-audit/supplemental/2"
DRIVER, DRIVEN = "DRIVER_POINT", "DRIVEN_POINT"
INTERVAL = 300

#: A coupling whose gain is stated and whose spread is stated, valid. Every
#: refusal below is this with one thing wrong.
STATED = {"from": DRIVER, "to": DRIVEN,
          "propagation_delay_s": 300, "time_constant_s": 600,
          "gain": 0.004, "gain_basis": "a commissioning measurement",
          "gain_sigma": 0.0002,
          "gain_sigma_basis": "the standard error of that measurement",
          "basis": "the first moves the medium the second reads"}


def _file(fmt: str = FORMAT, **coupling_changes) -> Path:
    coupling = {**STATED, **coupling_changes}
    coupling = {k: v for k, v in coupling.items() if v is not _DROP}
    doc = {"format": fmt, "provenance": "a bench",
           "sampling_interval_s": INTERVAL, "couplings": [coupling]}
    path = Path(tempfile.mkdtemp()) / "supplemental.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    return path


#: Marks a key to leave out of the block altogether.
_DROP = object()


# Stand-ins: exactly the protocol members the generator reads, and no more.

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


def _transition(path: Path) -> dict:
    declaration = _Declaration(points=[
        _Point(DRIVER, "speed"),
        _Point(DRIVEN, "distance", [_Threshold("upper", "warning", 40.0),
                                    _Threshold("upper", "critical", 45.0)])])
    model, _manifest = generator.generate(
        declaration, domain_id="bench", supplemental=load_supplemental(path),
        vocabulary=conformance.ReferenceVocabulary())
    rules = model["domain"]["relationship_rules"]
    assert len(rules) == 1, rules
    return rules[0]["transition"]


class TestTheSpreadIsReadAndDelivered:

    def test_it_is_read(self):
        coupling = load_supplemental(_file()).couplings[0]
        assert coupling.gain_sigma == pytest.approx(0.0002)
        assert coupling.gain_sigma_basis == STATED["gain_sigma_basis"]
        assert coupling.spread_is_declared

    def test_it_reaches_the_model_under_the_engines_own_key(self):
        """The half 0.1.10 would have missed. Parsing a key is not delivering
        it; the transition is what the engine reads."""
        transition = _transition(_file())
        assert transition["gain_sigma"] == pytest.approx(0.0002)
        assert transition["gain"] == pytest.approx(0.004)

    def test_its_basis_stays_in_the_file(self):
        """The engine has no field for a spread's basis and reports a key it
        does not read, so writing it into the transition would be a finding
        about this package rather than a record of the operator's."""
        transition = _transition(_file())
        assert "gain_sigma_basis" not in transition
        assert STATED["gain_sigma_basis"] not in json.dumps(transition)

    def test_without_one_the_model_says_nothing_about_a_spread(self):
        """Absent is not zero. A model that carried `gain_sigma: 0` would claim
        an exact gain, which is a far stronger statement than nobody said."""
        path = _file(gain_sigma=_DROP, gain_sigma_basis=_DROP)
        assert not load_supplemental(path).couplings[0].spread_is_declared
        assert "gain_sigma" not in _transition(path)


class TestEveryWayOfStatingOneThatIsNotOneIsRefused:
    """Each of these would load and generate a model whose band carries none
    of the gain's doubt -- from a file that reads as though it stated some."""

    @pytest.mark.parametrize("changes,because", [
        ({"gain": "estimate", "gain_basis": _DROP},
         "a spread on a withheld gain is a spread on no number"),
        ({"gain_sigma": 0}, "the engine reads zero as no spread at all"),
        ({"gain_sigma": -0.0002}, "a standard deviation is not negative"),
        ({"gain_sigma": "estimate"}, "a spread has no withheld form"),
        ({"gain_sigma": True}, "a boolean is not a number here"),
        ({"gain_sigma_basis": _DROP}, "a spread with nothing establishing it"),
        ({"gain_sigma_basis": "  "}, "a blank basis is no basis"),
        ({"gain_sigma": _DROP}, "a basis for a number that is not there"),
    ])
    def test_it_refuses(self, changes, because):
        with pytest.raises(SupplementalError):
            load_supplemental(_file(**changes))

    @pytest.mark.parametrize("literal", ["NaN", "Infinity"])
    def test_a_value_that_is_not_finite_is_refused(self, literal):
        """Python's JSON reader accepts both literals, so the check is ours."""
        path = _file()
        text = path.read_text(encoding="utf-8").replace("0.0002", literal)
        path.write_text(text, encoding="utf-8")
        with pytest.raises(SupplementalError, match="positive finite"):
            load_supplemental(path)

    def test_the_withheld_gain_refusal_says_why(self):
        with pytest.raises(SupplementalError, match="no number here"):
            load_supplemental(_file(gain="estimate", gain_basis=_DROP))


class TestAnOlderIdCarryingItNamesTheIdToUse:
    """Found by asking what a build WITHOUT this change does with a file that
    has it. Every build reading format 2 refuses a coupling key it does not
    know, so nothing is dropped -- but it refuses saying the format has no
    field for a spread, which is false of a file written for this one. Under
    format 3 the same build names the real cause: the file is newer than it."""

    def test_a_spread_under_format_2_is_refused(self):
        with pytest.raises(SupplementalError) as raised:
            load_supplemental(_file(PREVIOUS))
        assert FORMAT in str(raised.value), (
            "the refusal does not name the format to use instead")
        assert "gain_sigma" in str(raised.value)

    def test_a_basis_alone_under_format_2_names_it_too(self):
        with pytest.raises(SupplementalError) as raised:
            load_supplemental(_file(PREVIOUS, gain_sigma=_DROP))
        assert FORMAT in str(raised.value)

    def test_a_key_no_format_carries_is_not_sent_to_a_newer_id(self):
        """Naming an id is the repair only when an id carries the key. A typo
        told to change its format would be sent somewhere that refuses it
        again."""
        with pytest.raises(SupplementalError) as raised:
            load_supplemental(_file(PREVIOUS, gain_sigma=_DROP,
                                    gain_sigma_basis=_DROP, gain_sigmaa=1.0))
        assert "does not read" in str(raised.value)
        assert "Declare format" not in str(raised.value)


class TestNothingFormat2SaidChanges:

    def test_a_format_2_coupling_loads_exactly_as_before(self):
        path = _file(PREVIOUS, gain_sigma=_DROP, gain_sigma_basis=_DROP)
        coupling = load_supplemental(path).couplings[0]
        assert coupling.gain == pytest.approx(0.004)
        assert not coupling.spread_is_declared

    def test_format_3_reads_every_coupling_key_format_2_did(self):
        """A key may be added; none may vanish. A block that loaded under an
        earlier id has to keep loading under the newest."""
        newest = COUPLING_KEYS_BY_FORMAT[FORMAT]
        for name, keys in COUPLING_KEYS_BY_FORMAT.items():
            assert keys <= newest, (name, sorted(keys - newest))

    def test_the_formats_that_carry_couplings_are_the_ones_with_a_key_set(self):
        """Every accepted id that carries `couplings:` declares what a coupling
        under it may say; an id missing here would refuse every coupling key."""
        from presence_audit.supplemental import KEYS_BY_FORMAT

        carrying = {f for f in ACCEPTED_FORMATS if "couplings" in KEYS_BY_FORMAT[f]}
        assert carrying == set(COUPLING_KEYS_BY_FORMAT), (
            sorted(carrying ^ set(COUPLING_KEYS_BY_FORMAT)))
