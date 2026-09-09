"""The one contract this package holds with an engine, and it had no owner.

`feed()` reads an envelope back from a session, and everything the feeder knows
is keyed to that envelope's SHAPE -- which of `findings` and `not_checked` a
result lands in, the `problem_type` split, `reason` as the decline vocabulary.
The shape is versioned by the engine, separately from its release number, and
`schema_mismatch()` is what refuses a shape this build cannot parse.

**Nothing in this repository tested any of that.** Measured before writing:
`grep -rn "schema_mismatch\\|ENVELOPE_SCHEMA_VERSION" tests/` returned nothing.
The rule was covered -- thoroughly, including the case below that looks like an
oversight and is not -- in `bmc-sensor-audit`'s suite, which is a CONSUMER of
this package. So the package that owns the rule could not fail on it, and the
package that could was one release behind whatever this tree said.

The other half of the same gap: `factory-line-audit` reads the same envelope
with its own copy of the constant and a stricter rule, refusing what this
package admits. That is not a defect -- its pin starts above the engines this
one is being lenient about -- but neither reader could see the other, and the
constant was not exported for either to share. Exporting it is what makes the
difference a decision rather than an accident.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

import presence_audit
from presence_audit import feeder

ROOT = pathlib.Path(__file__).resolve().parents[1]
INIT = (ROOT / "src" / "presence_audit" / "__init__.py").read_text(encoding="utf-8")

_ABSENT = object()


def _how_the_root_binds(name: str) -> set:
    """Which statement kinds bind `name` at the package root, from the AST."""
    kinds = set()
    for node in ast.parse(INIT).body:
        if isinstance(node, ast.ImportFrom):
            if any(alias.asname == name or alias.name == name for alias in node.names):
                kinds.add("import")
        elif isinstance(node, ast.Assign):
            if any(isinstance(t, ast.Name) and t.id == name for t in node.targets):
                kinds.add("assign")
    return kinds


class TestTheConstantHasOneHome:
    """A re-export is a second NAME for one value. It becomes a second VALUE
    the day somebody types the number instead of importing it, and both would
    read correct in isolation."""

    def test_the_root_exports_this_one(self):
        assert "ENVELOPE_SCHEMA_VERSION" in presence_audit.__all__, (
            "the constant is the contract a vertical author has to know about, "
            "and it is not reachable without knowing which module holds it")

    def test_there_are_exports_to_check(self):
        """NON-VACUITY for the parametrised check below: an empty `__all__`
        would collect zero cases and report as a pass."""
        assert presence_audit.__all__, "the package root exports nothing"

    @pytest.mark.parametrize("name", presence_audit.__all__)
    def test_every_exported_name_is_imported_rather_than_restated(self, name):
        """The structural half, over EVERY export rather than the one this
        file is about -- the next constant re-exported here inherits the check
        instead of needing its own. Comparing values would pass just as
        happily on a literal that happens to agree today."""
        binds = _how_the_root_binds(name)
        assert binds == {"import"}, (
            f"the package root binds {name} by {binds or 'nothing'}. A literal "
            f"here is a second record of one fact, and the two agree until the "
            f"first time only one of them is edited")

    def test_that_check_can_produce_a_positive(self):
        """Before believing a negative, prove the probe can produce one: the
        predicate has to be able to SEE an assignment, or its silence about
        this name means nothing."""
        assert _how_the_root_binds("__version__") == {"assign"}, (
            "the predicate cannot see a name the root assigns, so it cannot "
            "distinguish an import from a restatement")

    def test_the_two_names_carry_the_same_value(self):
        assert presence_audit.ENVELOPE_SCHEMA_VERSION is feeder.ENVELOPE_SCHEMA_VERSION


class TestSchemaMismatchAnswersInThreeStates:
    """`accepted`, `refused`, and `accepted because the field is absent`.

    Two outcomes would collapse the third into the second and refuse an engine
    this package supports; reading `!= 1` alone would also blame the wrong
    thing for whichever it was.
    """

    def _envelope(self, version=_ABSENT, **rest):
        envelope = {"checked": {}, "findings": [], "not_checked": [], **rest}
        if version is not _ABSENT:
            envelope["meta"] = {"schema_version": version, "source": "live"}
        return envelope

    def test_the_version_this_build_parses_is_accepted(self):
        assert feeder.schema_mismatch(
            self._envelope(feeder.ENVELOPE_SCHEMA_VERSION)) is None

    @pytest.mark.parametrize("version", [2, 0, None, "1", 1.5])
    def test_any_other_version_is_refused(self, version):
        """`"1"` and `1.5` are the cases a `!=` gets right and an `int()`
        coercion gets wrong -- a string that looks like the right number is
        still a different wire contract. `None` as a VALUE is a stamped field
        carrying nothing, which is not the same fact as an absent one."""
        why = feeder.schema_mismatch(self._envelope(version))
        assert why is not None, f"schema_version {version!r} was accepted"

    @pytest.mark.parametrize("version", [2, 0, None, "1", 1.5])
    def test_the_refusal_names_both_numbers(self, version):
        """A refusal that names neither side sends a reader to guess which of
        the two moved."""
        why = feeder.schema_mismatch(self._envelope(version))
        assert str(version) in why, f"the refusal does not name {version!r}"
        assert str(feeder.ENVELOPE_SCHEMA_VERSION) in why, (
            "the refusal does not name the version this build parses")

    def test_an_absent_version_is_not_a_mismatch(self):
        """**Absent is not wrong**, and this is the assertion the whole
        three-state shape exists for. Engines from before the field existed
        ship this same envelope shape unstamped. The rule is about the SHAPE
        rather than about which releases any particular pin admits today --
        every vertical's floor has since moved above them, and that is a fact
        about the verticals, not about what this reader can parse."""
        assert feeder.schema_mismatch(self._envelope()) is None

    @pytest.mark.parametrize("meta", [None, {}, "meta", 1, []])
    def test_an_envelope_with_no_usable_meta_is_not_a_mismatch(self, meta):
        """Same rule one level out: a missing or unreadable `meta` is an
        unstamped envelope, not a moved contract."""
        assert feeder.schema_mismatch({"meta": meta}) is None

    def test_these_checks_are_reading_the_real_rule(self):
        """NON-VACUITY. Every assertion above would pass against a function
        that returned None unconditionally, except the refusals -- so this
        pins that the two directions are both live in one place."""
        accepted = feeder.schema_mismatch(
            self._envelope(feeder.ENVELOPE_SCHEMA_VERSION))
        refused = feeder.schema_mismatch(
            self._envelope(feeder.ENVELOPE_SCHEMA_VERSION + 1))
        assert accepted is None and refused is not None, (
            "schema_mismatch answers the same way to a version it parses and "
            "one it does not, so every check in this class is decoration")
