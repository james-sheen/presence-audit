"""What a finding SAYS, against what the axiom did.

**The defect this file was written for.** A QC certificate rendered from a real
machine carried, verbatim, *MB_U73_THERM_LOCAL is BELOW its lower critical bound
of 0.0*, and the measurement printed beside it read `value: 0.0, threshold:
0.0`. Zero is not below zero. The verdict was right -- the BMC's own health field
said Critical for that sensor -- and the sentence was false, on a document whose
entire job is to be believed about one unit.

Both of the engine's comparisons are inclusive, and its own comment says why:
*the threshold names the edge of acceptable, not the first unacceptable value*.
So the floor and the ceiling had the same defect and only the floor was ever
seen, because a reading lands exactly on a declared bound about as often as a
board declares one at zero -- which bletchley does, for six sensors, and QEMU
reports exactly 0.0 for any tmp421 nobody has driven.

**Nothing here had ever tested this method.** Its only coverage was in a
consumer's suite, which is where the wording was pinned rather than questioned.
"""

from __future__ import annotations

import pytest

from presence_audit.generator import (BOUND_OF_PROBLEM, COMPARISON_PROBLEMS,
                                      GeneratedSensor, Manifest)

READING = "reading"


@pytest.fixture
def manifest():
    return Manifest(domain_id="d", sensors=[GeneratedSensor(
        entity_type="MB_U73_THERM_LOCAL", declared_name="MB_U73_THERM_LOCAL",
        source="board.json", upper=(49.0, 50.0), lower=(1.0, 0.0))])


def _say(manifest, problem_type, severity="critical"):
    return manifest.translate_finding(
        {"entity_id": "MB_U73_THERM_LOCAL", "severity": severity,
         "problem_type": f"{problem_type}:{READING}",
         "reason": f"{READING} said something"})


class TestAComparisonIsInclusiveAndSaysSo:
    @pytest.mark.parametrize("problem_type,severity,expected", [
        ("below_critical_threshold", "critical", "at or BELOW its lower critical bound of 0.0"),
        ("below_warning_threshold", "warning", "at or BELOW its lower warning bound of 1.0"),
        ("threshold_exceeded", "critical", "at or above its upper critical bound of 50.0"),
        ("threshold_warning", "warning", "at or above its upper warning bound of 49.0"),
    ], ids=["floor-critical", "floor-warning", "ceiling-critical", "ceiling-warning"])
    def test_every_comparison_arm(self, manifest, problem_type, severity, expected):
        assert _say(manifest, problem_type, severity) == (
            f"MB_U73_THERM_LOCAL is {expected}")

    def test_the_word_that_was_wrong_is_no_longer_asserted_alone(self, manifest):
        """The negative of the case that found it: the sentence must not claim
        strict inequality when the axiom fires on equality."""
        said = _say(manifest, "below_critical_threshold")
        assert "is BELOW" not in said, said
        assert "at or BELOW" in said

    def test_the_side_is_still_right(self, manifest):
        """A correction to the strictness must not move a finding across the band."""
        assert "lower" in _say(manifest, "below_critical_threshold")
        assert "upper" in _say(manifest, "threshold_exceeded")


class TestTheSetIsTheAxiomsAndNotAGuess:
    def test_every_comparison_arm_is_classified_to_a_side(self):
        assert COMPARISON_PROBLEMS <= set(BOUND_OF_PROBLEM)

    def test_the_arms_left_out_are_exactly_the_two_that_project(self):
        """`approaching_limit` and `approaching_floor` fire on a slope while the
        reading is still inside the band. They are not comparisons and must not
        be described as breaches -- which this build still does. See
        `translate_finding` for why that is not corrected in the same commit."""
        assert set(BOUND_OF_PROBLEM) - COMPARISON_PROBLEMS == {
            "approaching_limit", "approaching_floor"}

    @pytest.mark.parametrize("problem_type,expected", [
        ("approaching_limit",
         "MB_U73_THERM_LOCAL has not reached its upper critical bound of 50.0 "
         "and is trending toward it"),
        ("approaching_floor",
         "MB_U73_THERM_LOCAL has not reached its lower critical bound of 0.0 "
         "and is trending toward it"),
    ], ids=["ceiling", "floor"])
    def test_a_projection_is_not_rendered_as_a_breach(self, manifest,
                                                      problem_type, expected):
        """The second defect, and the worse one.

        Both projecting arms fire only while the reading has NOT reached the
        critical bound -- the axiom guards them with `current <
        critical_threshold` and `current > lower_critical`. Rendered with the
        breach sentence they said the opposite of what happened: *is above its
        upper high bound* for a value under the bound.
        """
        assert _say(manifest, problem_type, severity="high") == expected

    @pytest.mark.parametrize("problem_type", ["approaching_limit", "approaching_floor"])
    def test_a_projection_never_claims_a_breach_in_either_direction(
            self, manifest, problem_type):
        """The negative, so the sentence cannot drift back into one."""
        said = _say(manifest, problem_type, severity="high")
        assert "BELOW" not in said and "above its upper" not in said
        assert "at or" not in said

    def test_the_bound_it_names_is_the_one_the_arm_projects_at(self, manifest):
        """`high` is the severity both arms carry and this package maps no such
        level, which is why the old sentence printed a level and no number. The
        threshold either arm computes time-to is the CRITICAL one, whatever the
        severity says, so that is the bound worth naming."""
        assert "50.0" in _say(manifest, "approaching_limit", severity="high")
        assert "49.0" not in _say(manifest, "approaching_limit", severity="high")

    def test_a_domain_with_no_critical_bound_omits_the_number(self):
        """Rather than printing None, which is the shape of the defect this
        method already carries a comment about for severities."""
        bare = Manifest(domain_id="d", sensors=[GeneratedSensor(
            entity_type="P", declared_name="P", source="s.json",
            upper=(9.0, None), lower=(None, None))])
        assert bare.translate_finding(
            {"entity_id": "P", "severity": "high",
             "problem_type": f"approaching_limit:{READING}",
             "reason": "r"}) == "P has not reached its upper critical bound and is trending toward it"


class TestWhatItStillWillNotGuess:
    def test_an_unrecognised_arm_keeps_the_engines_own_words(self, manifest):
        said = _say(manifest, "some_future_arm")
        assert "BELOW" not in said and "above its upper" not in said
        assert "MB_U73_THERM_LOCAL" in said

    def test_an_unrecognised_severity_omits_the_bound_rather_than_asserting_one(
            self, manifest):
        said = _say(manifest, "below_critical_threshold", severity="high")
        assert said == "MB_U73_THERM_LOCAL is at or BELOW its lower high bound"
