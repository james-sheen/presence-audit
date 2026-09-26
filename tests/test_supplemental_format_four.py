"""Supplemental format 4: the member keys in the core's word, and two new blocks.

A redundant group lists its `points` and a counter names its `point`; earlier ids
read the words they were published with, exactly as before. `fault_channels`
tell the engine which way a failure travels -- often the opposite way to a
coupling -- and become causal rules with an edge under each; `actions` say what
an operator can set, and become templates `plan` and `rollout` can act with.
Neither block exists in an earlier id, so an older build refuses a /4 file by its
id rather than dropping both.
"""

from __future__ import annotations

import json
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from presence_audit import conformance, generator
from presence_audit.feeder import feed
from presence_audit.supplemental import (FORMAT, SupplementalError,
                                         load_supplemental)


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


FAN, HEATED, SPARE = "FAN_POINT", "HEATED_POINT", "SPARE_POINT"
BOUNDED = [_Threshold("upper", "warning", 40.0), _Threshold("upper", "critical", 45.0)]


def _file(**blocks) -> Path:
    doc = {"format": FORMAT, "provenance": "a bench", **blocks}
    path = Path(tempfile.mkdtemp()) / "supplemental.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    return path


def _generate(path: Path):
    return generator.generate(
        _Declaration(points=[_Point(FAN, "speed"), _Point(HEATED, "distance", BOUNDED),
                             _Point(SPARE, "distance", BOUNDED)]),
        domain_id="bench", supplemental=load_supplemental(path),
        vocabulary=conformance.ReferenceVocabulary())


CHANNEL = {"from": FAN, "to": HEATED, "basis": "the fan cools what the second reads"}
ACTION = {"name": "set_fan", "point": FAN, "effect": "set",
          "basis": "the controller takes an override"}


class TestTheMemberKeys:

    def test_the_new_keys_read(self):
        loaded = load_supplemental(_file(
            redundant_groups=[{"points": [HEATED, SPARE], "basis": "one die"}],
            counters=[{"point": SPARE, "basis": "only climbs"}]))
        assert loaded.redundant_groups[0].points == (HEATED, SPARE)
        assert loaded.counters[0].point == SPARE

    def test_the_old_keys_are_not_the_new_formats(self):
        with pytest.raises(SupplementalError):
            load_supplemental(_file(counters=[{"sensor": SPARE, "basis": "b"}]))

    def test_an_older_id_reads_its_published_keys_as_it_always_did(self):
        loaded = load_supplemental(_file(
            format="presence-audit/supplemental/3",
            redundant_groups=[{"sensors": [HEATED, SPARE], "basis": "one die"}],
            counters=[{"sensor": SPARE, "basis": "only climbs"}]))
        assert loaded.redundant_groups[0].points == (HEATED, SPARE)
        assert loaded.counters[0].point == SPARE


class TestAFaultChannel:

    def test_it_becomes_a_causal_rule_between_the_generated_types(self):
        model, manifest = _generate(_file(fault_channels=[CHANNEL]))
        rules = model["domain"]["relationship_rules"]
        assert rules == [{"type": generator.FAULT_RELATION,
                          "source_type": manifest.type_for(FAN),
                          "target_type": manifest.type_for(HEATED),
                          "edge_direction": "causal"}]
        assert generator.FAULT_RELATION in model["domain"]["relationship_types"]
        assert manifest.channeled == [(FAN, HEATED)]

    def test_a_point_with_no_bounds_is_modelled_because_a_channel_names_it(self):
        """The fan carries no thresholds, so the ordinary rule excludes it -- and
        a cause the engine has no entity for can explain nothing."""
        assert _generate(_file())[1].type_for(FAN) is None
        model, manifest = _generate(_file(fault_channels=[CHANNEL]))
        assert manifest.type_for(FAN) in model["domain"]["entity_types"]

    def test_a_weight_travels_only_with_its_basis(self):
        weighted = {**CHANNEL, "weight": 0.6, "weight_basis": "a service record"}
        rule = _generate(_file(fault_channels=[weighted]))[0]["domain"]["relationship_rules"][0]
        assert rule["causal"] == {"weight": 0.6}
        with pytest.raises(SupplementalError, match="weight_basis"):
            load_supplemental(_file(fault_channels=[{**CHANNEL, "weight": 0.6}]))

    @pytest.mark.parametrize("weight", [0, 1.5, -0.1, True, "high"])
    def test_a_weight_is_a_chance(self, weight):
        with pytest.raises(SupplementalError):
            load_supplemental(_file(fault_channels=[
                {**CHANNEL, "weight": weight, "weight_basis": "b"}]))

    def test_a_channel_to_itself_is_refused(self):
        with pytest.raises(SupplementalError, match="both ends"):
            load_supplemental(_file(fault_channels=[{**CHANNEL, "to": FAN}]))

    def test_the_feeder_puts_an_edge_under_the_rule(self):
        """A causal rule is about two TYPES; the engine's graph needs an edge
        between two entities, exactly as a coupling's fit does."""
        from test_a_declared_coupling_becomes_an_edge import (
            _Declared, _Live, _Match, _RecordingSession, _Report)

        _, manifest = _generate(_file(fault_channels=[CHANNEL]))
        session = _RecordingSession()
        result = feed(session, manifest, [_Report(matches=[
            _Match(_Declared(FAN), _Live(3000.0)),
            _Match(_Declared(HEATED), _Live(41.0))])])
        assert (manifest.type_for(FAN), generator.FAULT_RELATION,
                manifest.type_for(HEATED)) in session.relationships
        assert result.channeled == [(FAN, HEATED)] and not result.channels_not_fed

    def test_an_endpoint_not_reading_is_reported_not_wired(self):
        from test_a_declared_coupling_becomes_an_edge import (
            _Declared, _Live, _Match, _RecordingSession, _Report)

        _, manifest = _generate(_file(fault_channels=[CHANNEL]))
        session = _RecordingSession()
        result = feed(session, manifest, [_Report(matches=[
            _Match(_Declared(FAN), _Live(None)),
            _Match(_Declared(HEATED), _Live(41.0))])])
        assert not [r for r in session.relationships if r[1] == generator.FAULT_RELATION]
        assert result.channels_not_fed[0]["missing"] == [FAN]


class TestAnAction:

    def test_it_becomes_a_template_the_engine_reads(self):
        model, manifest = _generate(_file(actions=[ACTION]))
        assert model["domain"]["action_templates"] == [{
            "name": "set_fan", "applies_to": manifest.type_for(FAN),
            "parameters_schema": {"value": {"type": "number",
                                            "entity_property": generator.READING}},
            "effect": "set", "settle_s": 0.0,
            "source": "the controller takes an override"}]
        assert manifest.actions == ["set_fan"]

    def test_an_unknown_effect_is_refused(self):
        with pytest.raises(SupplementalError, match="effect"):
            load_supplemental(_file(actions=[{**ACTION, "effect": "toggle"}]))


class TestAnOlderIdRefusesTheNewBlocks:

    @pytest.mark.parametrize("block", ["fault_channels", "actions"])
    def test_by_its_id_rather_than_dropping_them(self, block):
        with pytest.raises(SupplementalError, match=FORMAT):
            load_supplemental(_file(format="presence-audit/supplemental/3",
                                    **{block: [CHANNEL if block == "fault_channels"
                                               else ACTION]}))


def test_a_file_without_the_new_blocks_generates_what_it_always_did():
    """Counted only where declared: the manifest of a file with neither block
    carries no key for them, so every existing manifest is byte for byte as it
    was."""
    _, manifest = _generate(_file())
    assert "channeled" not in manifest.to_dict() and "actions" not in manifest.to_dict()
    assert "fault_channels" not in manifest.counts()
