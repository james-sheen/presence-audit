"""The compose rule, and the floors that must never arrive here.

Two verticals had written this rule out separately. One had it as a function
with the empty case handled and values outside the three normalised; the other
composed with a bare `max()` over values it happened to control. Both are
correct today and they are not the same rule -- `max()` of nothing raises, and
`max(0, 137)` is `137`, which is not an exit code any contract defines.

That is what a shared rule is for. What must NOT follow it here are the floors:
which finding class or decline reason floors at which code is a judgement about
a domain, and this package cannot see one.
"""

from __future__ import annotations

import ast
import itertools
import pathlib

import pytest

from presence_audit import exit_contract as E

SOURCE = (pathlib.Path(__file__).resolve().parents[1]
          / "src" / "presence_audit" / "exit_contract.py").read_text(encoding="utf-8")

CODES = (E.CLEAN, E.FINDINGS, E.INCOMPLETE)


class TestNormalise:

    @pytest.mark.parametrize("code", CODES)
    def test_a_real_code_passes_through_with_its_raw_value(self, code):
        assert E.normalise(code) == (code, code)

    @pytest.mark.parametrize("code", [3, 137, -1, 255])
    def test_any_other_integer_reads_as_incomplete_and_keeps_the_raw(self, code):
        assert E.normalise(code) == (E.INCOMPLETE, code), (
            "an out-of-range code was clamped and forgotten; the raw value is "
            "the most informative thing that run produced")

    @pytest.mark.parametrize("code", [None, "1", 1.0, object(), [], {}])
    def test_a_non_integer_reads_as_incomplete(self, code):
        assert E.normalise(code)[0] == E.INCOMPLETE

    @pytest.mark.parametrize("code", [True, False])
    def test_a_bool_reads_as_incomplete_and_not_as_its_int_value(self, code):
        """`True` is an `int` and would otherwise sail through as *something
        got worse* -- a claim nobody made. This is the case a `code in (0,1,2)`
        test gets wrong on its own, because `True == 1`."""
        assert E.normalise(code)[0] == E.INCOMPLETE, (
            f"{code!r} normalised to {E.normalise(code)[0]}, so a caller "
            f"passing a boolean gets a verdict instead of a refusal")


class TestCompose:

    def test_composing_nothing_is_incomplete(self):
        """The case that makes this a function rather than `max()`. A battery
        whose legs all failed to be collected composes nothing, and reading
        that as clean is the failure the whole contract exists to prevent."""
        assert E.compose() == E.INCOMPLETE

    @pytest.mark.parametrize("legs", list(itertools.product(CODES, repeat=3)))
    def test_the_worst_leg_wins_over_every_combination(self, legs):
        """Exhaustive over three legs: twenty-seven cases, not a sample."""
        assert E.compose(*legs) == max(legs)

    def test_two_outranks_one_specifically(self):
        """Named on its own because it is the pair the rule exists to order,
        and a `min` would pass every test above that used equal legs."""
        assert E.compose(E.FINDINGS, E.INCOMPLETE) == E.INCOMPLETE
        assert E.compose(E.INCOMPLETE, E.FINDINGS) == E.INCOMPLETE

    def test_one_outranks_clean(self):
        assert E.compose(E.CLEAN, E.FINDINGS) == E.FINDINGS

    def test_an_out_of_range_leg_does_not_escape_into_the_result(self):
        """`max()` returns 137 here. That is the hole a bare max leaves, and
        the reason a vertical composing with one is not composing this rule."""
        assert E.compose(E.CLEAN, 137) == E.INCOMPLETE
        assert E.compose(E.FINDINGS, 137) == E.INCOMPLETE

    def test_a_single_leg_is_itself(self):
        for code in CODES:
            assert E.compose(code) == code


class TestTheMeaningsAreComplete:

    def test_every_code_has_a_word_and_no_word_has_no_code(self):
        assert set(E.MEANING) == set(CODES), (
            f"MEANING covers {sorted(E.MEANING)} and the codes are "
            f"{sorted(CODES)}; a code with no word prints as a bare number")

    def test_the_words_are_distinct(self):
        assert len(set(E.MEANING.values())) == len(E.MEANING)


class TestNoFloorsArrivedHere:
    """E2, asserted rather than promised.

    A floor is a domain judgement. The risk is not that somebody argues for
    putting one here -- it is that one arrives as a convenience, defaulted
    once by whoever needed it, and is then inherited by every vertical after
    them without anybody deciding.
    """

    def test_the_module_exports_only_the_contract(self):
        assert set(E.__all__) == {"CLEAN", "FINDINGS", "INCOMPLETE", "MEANING",
                                  "normalise", "compose"}, sorted(E.__all__)

    def test_no_public_name_here_is_about_classes_or_floors(self):
        """Structural, over the module's own top-level names. A floor table
        arrives named for what it is."""
        tree = ast.parse(SOURCE)
        names = []
        for node in tree.body:
            if isinstance(node, ast.Assign):
                names += [t.id for t in node.targets if isinstance(t, ast.Name)]
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                names.append(node.target.id)
            elif isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                names.append(node.name)
        suspect = [n for n in names if not n.startswith("_")
                   and any(word in n.lower() for word in ("floor", "class", "severity"))]
        assert suspect == [], (
            f"{suspect} looks like a domain judgement living in the package "
            f"that cannot see a domain. Floors belong to the vertical that can "
            f"justify them")

    def test_that_check_can_produce_a_positive(self):
        """The predicate has to be able to see one, or its silence is empty."""
        tree = ast.parse("FINDING_CLASS_FLOORS = {}\ndef floor_of(x): pass\n")
        names = [n.name if isinstance(n, ast.FunctionDef) else
                 n.targets[0].id for n in tree.body]
        assert [n for n in names
                if any(w in n.lower() for w in ("floor", "class", "severity"))]

    def test_the_docstring_says_where_the_floors_live(self):
        assert "floor" in E.__doc__.lower()
        assert "domain judgement" in E.__doc__.lower(), (
            "the module does not say WHY the floors are elsewhere, so the next "
            "person to want one here has nothing to read")
