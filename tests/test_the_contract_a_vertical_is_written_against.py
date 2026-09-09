"""The contract a vertical implements, and the number that says which revision.

This package's whole argument is that a vertical supplies the domain and the
core supplies nothing. What was never written down is WHICH REVISION of that
arrangement a given vertical was written against -- so a vertical built against
a future core and a vertical built against this one register identically, and
the first sign of the difference is a wrong answer in a report.

`PROTOCOL_VERSION` is that number, and the shape of the check is the one this
module already argued for twice. `noun`, `count_labels` and `report_sections`
are OPTIONAL members precisely because they arrived after two verticals were
published, and requiring them would have made an addition a breaking change.
Requiring the version declaration would be the same mistake in a new place, so
declaring it is optional too: **absent is admitted, declared-and-different is
refused.** Both numbers are named in the refusal, because either side can be
the one that moved.

WHAT THIS CANNOT DO, written down rather than left to be discovered. A version
number catches a vertical that KNOWS it was written against something else. It
cannot catch a vertical written against this revision that is wrong about it,
and it cannot catch the core exceeding its own protocol -- that is what
`test_a_foreign_domain_runs_on_the_core.py` is for, and the two answer
different questions.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

from presence_audit import PROTOCOL_VERSION, protocols, vocabulary

ROOT = pathlib.Path(__file__).resolve().parents[1]
README = (ROOT / "README.md").read_text(encoding="utf-8")
VOCABULARY_SOURCE = (ROOT / "src" / "presence_audit" / "vocabulary.py").read_text(
    encoding="utf-8")


class Minimal:
    """The smallest thing `register` accepts. Deliberately not a fixture from
    another file: a vocabulary that satisfies more than it has to would leave
    the reason for each refusal below ambiguous."""

    kinds = ("thing",)
    count_keys = {}


def _with(version):
    made = Minimal()
    made.protocol_version = version
    return made


@pytest.fixture(autouse=True)
def _empty_registry():
    """The registry is process-global, and these tests put things in it."""
    vocabulary.reset()
    yield
    vocabulary.reset()


class TestRegistrationAnswersInThreeStates:

    def test_a_vertical_declaring_this_revision_registers(self):
        vocabulary.register(_with(PROTOCOL_VERSION))
        assert vocabulary.registered()

    def test_a_vertical_declaring_nothing_registers(self):
        """The two published verticals are this case, and both must keep
        working. A required declaration would make the guarantee a breaking
        change -- the trap `noun` was shaped to avoid."""
        assert not hasattr(Minimal(), "protocol_version")
        vocabulary.register(Minimal())
        assert vocabulary.registered()

    @pytest.mark.parametrize("declared", [2, 0, None, "1", 1.5])
    def test_a_vertical_declaring_another_revision_is_refused(self, declared):
        """`None` is here on purpose and is NOT the absent case: an attribute
        set to nothing is a vertical that declared and got it wrong, which is
        a different fact from one that never spoke. `"1"` and `1.5` are the
        pair a coercion would wave through."""
        with pytest.raises(vocabulary.PluginError):
            vocabulary.register(_with(declared))
        assert not vocabulary.registered(), (
            "the refusal left the vocabulary registered, so a caller that "
            "catches the error runs against a vertical the core refused")

    @pytest.mark.parametrize("declared", [2, 0, None, "1", 1.5])
    def test_the_refusal_names_both_numbers(self, declared):
        with pytest.raises(vocabulary.PluginError) as raised:
            vocabulary.register(_with(declared))
        message = str(raised.value)
        assert str(declared) in message, f"the refusal does not name {declared!r}"
        assert str(PROTOCOL_VERSION) in message, (
            "the refusal does not name the revision this core serves, so a "
            "reader cannot tell which side moved")

    def test_the_check_is_not_admitting_everything(self):
        """NON-VACUITY. Every passing case above would also pass against a
        `register` that never refuses anything, and the refusals would not --
        so both directions are pinned here in one place."""
        vocabulary.register(_with(PROTOCOL_VERSION))
        assert vocabulary.registered()
        vocabulary.reset()
        with pytest.raises(vocabulary.PluginError):
            vocabulary.register(_with(PROTOCOL_VERSION + 1))


class TestTheConstantSaysWhatItIsFor:

    def test_it_is_exported_from_the_package_root(self):
        assert "PROTOCOL_VERSION" in __import__("presence_audit").__all__

    def test_the_registry_reads_the_constant_rather_than_a_copy(self):
        """Structural. The check would pass just as well against a literal in
        `vocabulary.py` that agrees with `protocols.py` today, and the two
        would part company the first time only one was edited."""
        tree = ast.parse(VOCABULARY_SOURCE)
        imported = any(
            isinstance(node, ast.ImportFrom)
            and any(alias.name == "PROTOCOL_VERSION" for alias in node.names)
            for node in tree.body)
        assigned = any(
            isinstance(node, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == "PROTOCOL_VERSION"
                    for t in node.targets)
            for node in tree.body)
        assert imported and not assigned, (
            f"vocabulary.py imports PROTOCOL_VERSION: {imported}; assigns its "
            f"own: {assigned}. The revision has one home, and it is the module "
            f"that holds the contract")


class TestTheReadmeCountsTheMembersItClaims:
    """The sentence a vertical author sizes the job from.

    It said **thirteen** while the protocol had fifteen. Nothing held it to
    anything, so it went stale the first time a member was added and read
    correct in every review since. A number in prose with no owner is a claim
    that stops being true silently.
    """

    WORDS = {"twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15,
             "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19}

    def _members(self):
        tree = ast.parse(VOCABULARY_SOURCE)
        cls = next(node for node in tree.body
                   if isinstance(node, ast.ClassDef) and node.name == "Vocabulary")
        return [node.name for node in cls.body
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]

    def _claimed(self):
        for word, number in self.WORDS.items():
            if f"{word.capitalize()} members" in README:
                return number
        return None

    def test_the_readme_states_a_count_at_all(self):
        """NON-VACUITY. If the sentence is rephrased past this predicate the
        check goes green over nothing, which is how the number rotted in the
        first place."""
        assert self._claimed() is not None, (
            "the README no longer states a member count in a form this test "
            "can read; either restore the sentence or delete this check, but "
            "do not leave it passing over a claim it cannot see")

    def test_it_matches_what_the_protocol_actually_declares(self):
        members = self._members()
        assert self._claimed() == len(members), (
            f"the README claims {self._claimed()} members and "
            f"`vocabulary.Vocabulary` declares {len(members)}: {members}")

    def test_the_count_is_read_from_the_class_and_not_from_here(self):
        """The derivation has to be able to move. A hand-kept list here would
        need editing by the same person adding the member it is meant to
        catch -- the shape this repository rejects in writing."""
        assert len(self._members()) >= 10, (
            f"only {len(self._members())} member(s) parsed out of the class; "
            f"the comparison above would be against a broken derivation")
