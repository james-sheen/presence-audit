"""The kit a vertical author runs, tested as the artifact it is.

It used to be four classes in `test_a_foreign_domain_runs_on_the_core.py`. That
made the conformance oracle real and unreachable at the same time: a vertical
author could not run it, and if they had copied it, the copy and the original
would have drifted with nothing holding them together. Promoting it into the
package is a move plus an entry point.

What is asserted here is the part the move introduced. The kit REGISTERS a
vocabulary to drive the core, which is the one thing this package promises not
to do to anybody -- so the promise it has to keep instead is that it puts back
exactly what it found, including when what it found was nothing.
"""

from __future__ import annotations

import pathlib
import subprocess
import sys

import pytest

from presence_audit import conformance, protocols
from presence_audit import vocabulary as V

ROOT = pathlib.Path(__file__).resolve().parents[1]


class Broken:
    """Wrong in the two ways the kit is meant to name, and correct otherwise."""

    kinds = ("a", "b")
    count_keys = {}
    def classify(self, declared_type): return "not_a_kind_of_mine"
    def is_auditable(self, kind): return False
    def is_expected_live(self, declared_type): return True
    def template_pattern(self, name): return None
    def same_point(self, old, new): return True
    def point_changes(self, old, new, *, comparable=False): return []
    def capture_changes(self, before, after): return []
    def captures_comparable(self, before, after): return False
    def capture_findings(self, capture): return []
    def peer_groups(self, declaration): return []
    def report_sections(self): return {}


class ExpectsItsOwnTypes:
    """Correct, and coupled to a capture type of its own -- which is what every
    real vertical is, and what the kit's first version called a failure."""

    kinds = ("a",)
    count_keys = {}
    def classify(self, declared_type): return "a"
    def is_auditable(self, kind): return True
    def is_expected_live(self, declared_type): return True
    def template_pattern(self, name): return None
    def same_point(self, old, new): return old.resource == new.resource
    def point_changes(self, old, new, *, comparable=False): return []
    def capture_changes(self, before, after): return []
    def captures_comparable(self, before, after): return before.fields_observed
    def capture_findings(self, capture): return []
    def peer_groups(self, declaration): return []
    def report_sections(self): return {}


@pytest.fixture(autouse=True)
def _leave_the_registry_as_found():
    previous = V._REGISTERED
    yield
    V.reset()
    if previous is not None:
        V.register(previous)


class TestItPutsBackWhatItFound:
    """The promise the move made necessary."""

    def test_importing_it_registers_nothing(self):
        """The defect the package's own structural check exists for, asked of
        the module that had to be exempted from it."""
        V.reset()
        import importlib
        importlib.reload(conformance)
        assert not V.registered(), (
            "importing the kit put a vocabulary in the registry, so every "
            "consumer who imports it inherits a domain they did not choose")

    def test_an_empty_registry_is_empty_afterwards(self):
        V.reset()
        conformance.check_the_core()
        assert not V.registered(), (
            "the kit left its reference vocabulary registered, so a caller who "
            "ran it is now auditing a factory line they never asked about")

    def test_a_registered_vocabulary_survives_a_run(self):
        mine = ExpectsItsOwnTypes()
        V.reset()
        V.register(mine)
        conformance.check_the_core()
        assert V.current() is mine, (
            "the kit replaced the caller's vocabulary with its own; every "
            "verdict after this point comes from the wrong domain")


class TestItAnswersAboutTheCore:

    def test_the_shipped_core_passes_its_own_kit(self):
        problems = conformance.check_the_core()
        assert problems == [], problems

    def test_the_fixture_produces_all_three_states(self):
        """NON-VACUITY of the kit's own data. A fixture that cannot produce
        three answers cannot tell a working core from one that says the same
        thing every time -- and the kit's discrimination check would then be
        measuring the fixture, not the core."""
        V.reset()
        V.register(conformance.ReferenceVocabulary())
        from presence_audit.diff import compare
        counts = compare(conformance.DeclarationSource(conformance.SAMPLE_DECLARATION),
                         conformance.Capture(conformance.SAMPLE_CAPTURE)).counts()
        for state in conformance.THREE_STATES:
            assert counts.get(state), f"{state} is empty in the kit's own fixture"

    def test_the_state_keys_are_the_ones_the_report_uses(self):
        """The kit names three keys. It read one that does not exist on its
        first run and reported *the absent state came back empty*, which is a
        claim about the core and was really about the spelling here."""
        V.reset()
        V.register(conformance.ReferenceVocabulary())
        from presence_audit.diff import compare
        counts = compare(conformance.DeclarationSource(conformance.SAMPLE_DECLARATION),
                         conformance.Capture(conformance.SAMPLE_CAPTURE)).counts()
        missing = [k for k in conformance.THREE_STATES if k not in counts]
        assert missing == [], (
            f"the kit checks {missing}, which the report does not carry")


class TestItAnswersAboutAVocabulary:

    def test_a_broken_one_is_refused_and_told_why(self):
        problems, _ = conformance.check_a_vocabulary(Broken())
        joined = " ".join(problems)
        assert "outside its own kinds" in joined, problems
        assert "audits none of its own kinds" in joined, problems

    def test_a_correct_one_passes(self):
        problems, notes = conformance.check_a_vocabulary(
            conformance.ReferenceVocabulary())
        assert problems == [], problems
        assert notes == [], notes

    def test_expecting_its_own_capture_types_is_a_note_and_not_a_problem(self):
        """The correction that matters most in this file.

        The kit's first version reported five confident failures against a
        PUBLISHED vertical whose code is correct: `Vocabulary.same_point` is
        typed `(old: object, new: object)`, and the core passes through whatever
        the caller handed `compare()`, so a vocabulary is entitled to expect its
        own capture. A check that fires precisely, and high, against the wrong
        subject is worse than one that stays quiet.
        """
        problems, notes = conformance.check_a_vocabulary(ExpectsItsOwnTypes())
        assert problems == [], (
            f"a vocabulary coupled to its own capture type was reported as "
            f"WRONG: {problems}")
        assert notes, (
            "and it produced no observation either, so the author learns "
            "nothing about the coupling the kit did detect")

    def test_a_wrong_protocol_version_is_a_problem(self):
        broken = Broken()
        broken.protocol_version = protocols.PROTOCOL_VERSION + 1
        problems, _ = conformance.check_a_vocabulary(broken)
        assert any("protocol version" in p for p in problems), problems


class TestTheCommandLine:
    """`python -m presence_audit.conformance`, run as a user runs it."""

    def _run(self, *args, path=None):
        env = {"PATH": "/usr/bin:/bin", "PYTHONPATH": str(ROOT / "src")}
        if path:
            env["PYTHONPATH"] += ":" + str(path)
        return subprocess.run(
            [sys.executable, "-m", "presence_audit.conformance", *args],
            capture_output=True, text=True, env=env)

    def test_with_no_argument_it_checks_the_core_and_says_so(self):
        done = self._run()
        assert done.returncode == 0, done.stdout + done.stderr
        assert "not checked" in done.stdout, done.stdout

    def test_an_unresolvable_spec_exits_two_and_not_one(self):
        """*Could not run* is not *found problems*. A kit that returns the
        failure code for an import error tells a consumer their vertical is
        broken when what broke was the invocation."""
        done = self._run("no_such_module_at_all:register")
        assert done.returncode == 2, (done.returncode, done.stdout, done.stderr)
        assert "could not run" in done.stdout, done.stdout

    def test_a_broken_vertical_exits_one(self, tmp_path):
        module = tmp_path / "brokenvertical.py"
        module.write_text(
            "".join(line + chr(10) for line in (
                "from presence_audit import vocabulary",
                "import sys, pathlib",
                "sys.path.insert(0, " + repr(str(ROOT / "tests")) + ")",
                "from test_the_conformance_kit import Broken",
                "def register():",
                "    vocabulary.register(Broken())")),
            encoding="utf-8")
        done = self._run("brokenvertical:register", path=tmp_path)
        assert done.returncode == 1, (done.returncode, done.stdout, done.stderr)
        assert "outside its own kinds" in done.stdout, done.stdout


class TestItSaysWhatItCannotDo:
    """C2. The limit has to be legible next to the capability, or the kit gets
    trusted for the half it cannot see."""

    def test_the_docstring_names_the_incident_it_does_catch(self):
        doc = conformance.__doc__
        assert ".points" in doc, (
            "the kit does not name the case it exists to have caught, so a "
            "reader cannot tell what class of defect it finds")

    def test_the_docstring_says_it_cannot_prove_the_protocol_sufficient(self):
        doc = conformance.__doc__.lower()
        assert "insufficient" in doc or "sufficient" in doc, doc[:200]
        assert "only a real domain" in doc, (
            "the kit does not say who CAN answer the question it cannot, so "
            "its silence reads as coverage")
