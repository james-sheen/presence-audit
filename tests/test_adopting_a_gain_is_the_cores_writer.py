"""Adopting a fitted gain, written by the package that owns the format.

The writer was built inside the first vertical that needed it and nothing in it
belonged to that domain; it lives beside the format now, so the keys it sets and
the loader that reads them cannot drift apart. What it must keep, whoever calls
it: a declared number is never overwritten, a proposal the replay did not justify
is refused unless forced -- and forcing is stamped, two ways for two facts -- and
a file that reads as adopted IS adopted, or is restored.

The fitted payload is written by hand here, in the engine's shape. Whether the
engine fits the number is asserted where the engine is installed; what is
asserted here is what the WRITER does with a proposal.
"""

from __future__ import annotations

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

from presence_audit import adopt
from presence_audit.generator import GeneratedPoint, Manifest
from presence_audit.supplemental import FORMAT, load_supplemental

DRIVER, DRIVEN = "DRIVER_POINT", "DRIVEN_POINT"
WHEN = datetime(2026, 9, 26, 12, 0, tzinfo=timezone.utc)
BY = "a-vertical 1.2.3"


def _manifest():
    return Manifest(domain_id="d", points=[
        GeneratedPoint(entity_type="driver_t", declared_name=DRIVER, source="f",
                       upper=(None, None), lower=(None, None)),
        GeneratedPoint(entity_type="driven_t", declared_name=DRIVEN, source="f",
                       upper=(40.0, 45.0), lower=(None, None))])


def _described(**row):
    fitted = {"edge": "driver_t->driven_t", "gain": -0.0025, "n": 298,
              "r_squared": 0.42, "interval": [-0.003, -0.002],
              "response_model": "exponential", "declared_gain": None,
              "replay": {"status": "replayed", "corpus": "bench", "detected_before": 1,
                         "detected_after": 2, "confirmed": 3, "delta": 1},
              "gain_sigma": 0.0002, "gain_sigma_assumes_independent_residuals": True}
    fitted.update(row)
    return {"model": {"proposed_transitions": {"fitted": [fitted]}}}


def _file(fmt=FORMAT, gain="estimate") -> Path:
    doc = {"format": fmt, "provenance": "a bench", "sampling_interval_s": 300,
           "couplings": [{"from": DRIVER, "to": DRIVEN, "propagation_delay_s": 300,
                          "time_constant_s": 600, "gain": gain,
                          **({"gain_basis": "a datasheet"} if gain != "estimate" else {}),
                          "basis": "the first drives the second"}]}
    path = Path(tempfile.mkdtemp()) / "supplemental.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    return path


def _proposal(**row):
    return adopt.find(adopt.proposals(_described(**row), _manifest(),
                                      grid_seconds=300.0), f"{DRIVER} -> {DRIVEN}")


class TestTheProposalIsNamedInTheFilesWords:

    def test_the_generated_types_map_back_to_the_declared_names(self):
        proposal = _proposal()
        assert (proposal.driver, proposal.driven) == (DRIVER, DRIVEN)
        assert proposal.id == f"{DRIVER} -> {DRIVEN}"

    def test_an_edge_the_file_cannot_name_is_left_out(self):
        assert adopt.proposals(_described(edge="x->y"), _manifest(), grid_seconds=300) == []


class TestTheGate:

    def test_a_replay_that_caught_more_needs_no_stamp(self):
        assert adopt.check(_proposal(), force=False) is None

    def test_a_replay_that_caught_nothing_more_is_refused_then_stamped(self):
        flat = _proposal(replay={"status": "replayed", "corpus": "bench",
                                 "detected_before": 2, "detected_after": 2,
                                 "confirmed": 3, "delta": 0})
        with pytest.raises(adopt.AdoptionRefused, match="changes nothing"):
            adopt.check(flat, force=False)
        assert adopt.check(flat, force=True) == adopt.ADOPTED_WITHOUT_REPLAY_GAIN

    def test_no_corpus_is_a_different_refusal_and_a_different_stamp(self):
        untested = _proposal(replay={"status": "replay_unavailable",
                                     "reason": "no surprises corpus"})
        with pytest.raises(adopt.AdoptionRefused, match="no corpus"):
            adopt.check(untested, force=False)
        assert adopt.check(untested, force=True) == adopt.ADOPTED_UNTESTED

    def test_a_declared_number_is_refused_with_no_override(self):
        declared = _proposal(declared_gain=0.004)
        for force in (False, True):
            with pytest.raises(adopt.AdoptionRefused, match="already declares"):
                adopt.check(declared, force=force)

    def test_the_command_names_its_own_flag(self):
        untested = _proposal(replay={"status": "replay_unavailable", "reason": "r"})
        with pytest.raises(adopt.AdoptionRefused, match="--override-it"):
            adopt.check(untested, force=False, override="--override-it")


class TestTheBasisNamesWhoWroteIt:

    def test_the_calling_distribution_is_in_the_basis(self):
        basis = adopt.basis_for(_proposal(), when=WHEN, by=BY)
        assert basis.startswith(f"adopted_from_proposal {DRIVER} -> {DRIVEN} at "
                                f"2026-09-26T12:00:00+00:00 by {BY}")
        assert "detected 1 -> 2 of 3 confirmed (delta +1)" in basis

    def test_a_forced_adoption_says_which_refusal_it_overrode(self):
        basis = adopt.basis_for(_proposal(), when=WHEN, by=BY,
                                stamp=adopt.ADOPTED_UNTESTED)
        assert f"{adopt.ADOPTED_UNTESTED}: --force was given" in basis


class TestTheWriteIsProvedBeforeItIsKept:

    def test_the_gain_and_its_spread_land_and_read_back(self):
        path = _file()
        proposal = _proposal()
        written = adopt.write(path, proposal, adopt.basis_for(proposal, when=WHEN, by=BY),
                              adopt.spread_basis_for(proposal, when=WHEN, by=BY))
        coupling = load_supplemental(path).couplings[0]
        assert coupling.gain == -0.0025 and coupling.gain_sigma == 0.0002
        assert written.format_raised_to is None

    def test_a_format_that_cannot_carry_the_spread_is_raised_to_the_oldest_that_can(self):
        path = _file(fmt="presence-audit/supplemental/2")
        proposal = _proposal()
        written = adopt.write(path, proposal, "b", "sb")
        assert written.format_raised_to == "presence-audit/supplemental/3"
        assert json.loads(path.read_text())["format"] == "presence-audit/supplemental/3"

    def test_a_file_with_no_such_coupling_is_refused_and_untouched(self):
        path = _file()
        before = path.read_text()
        proposal = adopt.proposals(_described(edge="driven_t->driver_t"), _manifest(),
                                   grid_seconds=300.0)[0]
        with pytest.raises(adopt.AdoptionRefused, match="no coupling"):
            adopt.write(path, proposal, "b")
        assert path.read_text() == before

    def test_a_write_the_loader_refuses_is_restored(self):
        path = _file()
        before = path.read_text()
        proposal = _proposal(gain=0.0)            # the format refuses a zero gain
        with pytest.raises(adopt.AdoptionRefused, match="did not load back"):
            adopt.write(path, proposal, "b")
        assert path.read_text() == before


def test_the_module_imports_only_itself_and_the_stdlib():
    """The engine must not be needed to write a number the engine proposed: the
    payload is data, and this is Stage 1 code."""
    import ast
    tree = ast.parse(Path(adopt.__file__).read_text(encoding="utf-8"))
    roots = {(n.module or "").split(".")[0] for n in ast.walk(tree)
             if isinstance(n, ast.ImportFrom) and n.level == 0}
    roots |= {a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import)
              for a in n.names}
    assert "arbiter_engine" not in roots
