"""How a vertical gets in, and the two ways that went wrong.

Both defects below were found in `bmc-sensor-audit` by installing a real second
vertical and running the command -- not by reading. They travel with the loader,
so they are pinned here now.

Everything is driven by stub vocabularies. This package has no vertical to test
against, which is the property, so a test that needed one would be testing the
wrong package.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from presence_audit import plugins, vocabulary
from presence_audit.vocabulary import PluginError


def _vocab(word):
    class _V:
        kinds = (word,)
        count_keys: dict = {}
        def classify(self, t): return word
        def is_auditable(self, kind): return True
        def is_expected_live(self, t): return True
        def template_pattern(self, name): return None
        def same_point(self, old, new): return True
        def captures_comparable(self, before, after): return False
        def point_changes(self, old, new, *, comparable=False): return ()
        def capture_changes(self, before, after): return ()
        def capture_findings(self, capture): return ()
        def peer_groups(self, declaration): return ()
        def report_sections(self): return {}
    return _V


class _Point:
    def __init__(self, name, value, register):
        self.name, self.value, self._r = name, value, register
    def load(self): return self._r


@pytest.fixture(autouse=True)
def _empty_registry():
    previous = vocabulary._REGISTERED
    vocabulary.reset()
    yield
    vocabulary._REGISTERED = previous


class TestNothingIsRegisteredByDefault:
    def test_the_registry_starts_empty_and_says_so(self):
        """The property this whole package is for, at its bluntest. A default
        vertical here would be inherited by every consumer silently."""
        with pytest.raises(Exception) as raised:
            vocabulary.current()
        assert "presence_audit.plugins" in str(raised.value), (
            "the refusal should name how to supply one")

    def test_loading_nothing_registers_nothing(self):
        plugins.load_all(entry_points=False, environment=False)
        assert not vocabulary.registered()


class TestTwoInstalledVerticalsAreRefusedRatherThanRanked:
    """Registration REPLACES, so two entry points meant the later silently won
    and every verdict came from a domain the caller was not auditing. No test
    could catch it while exactly one vertical existed in the world."""

    @pytest.fixture
    def two(self, monkeypatch):
        points = [_Point("alpha", "alpha.mod:register",
                         lambda: vocabulary.register(_vocab("a")())),
                  _Point("beta", "beta.mod:register",
                         lambda: vocabulary.register(_vocab("b")()))]
        monkeypatch.setattr(plugins, "_entry_points", lambda: points)
        return points

    def test_two_entry_points_refuse_and_name_both(self, two):
        with pytest.raises(PluginError) as raised:
            plugins.load_all(environment=False)
        message = str(raised.value)
        assert "alpha.mod:register" in message and "beta.mod:register" in message

    def test_one_entry_point_still_loads(self, two, monkeypatch):
        """Non-vacuity: a refusal that also fired on one vertical would be worse
        than the defect it replaces."""
        monkeypatch.setattr(plugins, "_entry_points", lambda: two[:1])
        plugins.load_all(environment=False)
        assert vocabulary.current().kinds == ("a",)


class TestTheEnvironmentVariableCanNameACallable:
    """`os.pathsep` is `:` on POSIX -- the same character that introduces a
    callable -- so a spec naming one used to be split down the middle and
    reported as a missing module named after the half it was handed."""

    def test_a_spec_with_an_explicit_callable_survives(self, monkeypatch):
        monkeypatch.setattr(plugins.os, "pathsep", ":")
        assert plugins.environment_specs("a.mod:register") == ["a.mod:register"]

    def test_two_specs_each_naming_a_callable(self, monkeypatch):
        monkeypatch.setattr(plugins.os, "pathsep", ":")
        assert plugins.environment_specs("a.mod:register:b.mod:register") == [
            "a.mod:register", "b.mod:register"]

    def test_two_modules_without_callables_stay_two(self, monkeypatch):
        monkeypatch.setattr(plugins.os, "pathsep", ":")
        assert plugins.environment_specs("a.mod:b.mod") == ["a.mod", "b.mod"]

    def test_the_one_pair_the_grammar_cannot_tell_apart(self, monkeypatch):
        """Recorded as a test so the limit is a measurement, not a caveat: two
        DOTLESS names cannot be told from one module and a callable when the
        separator IS the callable marker."""
        monkeypatch.setattr(plugins.os, "pathsep", ":")
        assert plugins.environment_specs("alpha:beta") == ["alpha:beta"]

    @pytest.mark.parametrize("spec, target, attribute", [
        ("mod.a", "mod.a", "register"),
        ("mod.a:go", "mod.a", "go"),
        ("walk.py", "walk.py", "register"),
        (r"C:\walk.py", r"C:\walk.py", "register"),
        (r"C:\walk.py:go", r"C:\walk.py", "go"),
    ])
    def test_a_spec_splits_from_the_right(self, spec, target, attribute):
        assert plugins.split_spec(spec) == (target, attribute)


class TestTheSeamIsNamedAfterThisPackage:
    def test_the_group_and_the_variable_moved_with_the_code(self):
        """A group still named after the distribution this was extracted FROM
        would silently keep working for that one vertical and be undiscoverable
        for every other -- the worst of both."""
        assert plugins.ENTRY_POINT_GROUP == "presence_audit.plugins"
        assert plugins.ENVIRONMENT_VARIABLE == "PRESENCE_AUDIT_PLUGINS"


class TestTheRefusalTellsTheTruthAboutItself:
    """The message a user is guaranteed to see, checked against the constants.

    A run with no vertical registered prints this and nothing else, so it is the
    most-read string in the package -- and it named `BMC_SENSOR_AUDIT_PLUGINS`,
    the pre-extraction variable, all through 0.1.0. Setting it does nothing. The
    rename moved the constant; a second copy of its value sat in a message
    nothing compared against it.
    """

    def test_it_names_the_variable_that_actually_works(self):
        from presence_audit import plugins, vocabulary
        vocabulary.reset()
        with pytest.raises(vocabulary.VocabularyNotRegistered) as raised:
            vocabulary.current()
        assert plugins.ENVIRONMENT_VARIABLE in str(raised.value)
        assert plugins.ENTRY_POINT_GROUP in str(raised.value)

    def test_it_carries_no_second_copy_of_either_name(self):
        """The pin that survives the next rename. Asserting the message
        CONTAINS the right names would still pass if the value were spelled out
        again beside the import -- so this asserts the source does not spell
        them, which is the property that made the defect impossible to have."""
        import inspect
        from presence_audit import plugins, vocabulary
        body = inspect.getsource(vocabulary.current)
        # The import line is the one place either name may appear. Everything
        # else is a second copy.
        #
        # The first version of this assertion looked for `"NAME"` -- the name as
        # a whole quoted token -- and would have passed over the defect it was
        # written for, because that one had the name EMBEDDED in a longer
        # sentence: `"BMC_SENSOR_AUDIT_PLUGINS environment variable, or by ..."`.
        # Verified by putting the defect back: the token form did not fire.
        elsewhere = "\n".join(line for line in body.splitlines()
                              if " import " not in line)
        for literal in (plugins.ENVIRONMENT_VARIABLE, plugins.ENTRY_POINT_GROUP):
            assert literal not in elsewhere, (
                f"{literal!r} is spelled inside current() rather than read from "
                f"plugins. That is how the message came to name a variable that "
                f"does nothing: the rename moved the constant and could not "
                f"reach a copy of its value")
