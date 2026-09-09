"""Two domains, one process, nothing registered.

The vocabulary used to be resolved from process-global state, so the answer to
*which domain is this* was a property of the interpreter rather than of the
call. One consequence is obvious and was documented -- two installed verticals
are refused rather than ranked. The other was not: a harness that wanted to run
two verticals could not, in one process, at all.

`vocabulary=` on the public entry points is the fix, and it is deliberately NOT
a parameter threaded through the twenty-six places that read the registry. It
sets a context-local for the duration of the call, so the scope of the ambient
lookup moves from the process to the call and every internal reader keeps
working unchanged.

What is asserted here is the property, not the mechanism: two vocabularies,
one process, different answers, no registration -- and the same again in two
threads at once, because a context is per-thread and a module global is not.
"""

from __future__ import annotations

import threading

import pytest

from presence_audit import vocabulary as V
from presence_audit.conformance import (Capture, DeclarationSource,
                                        SAMPLE_CAPTURE, SAMPLE_DECLARATION)
from presence_audit.diff import compare


class Audits:
    """Treats the sample declaration's types as the thing being audited."""

    kinds = ("point", "other")
    count_keys = {"other": "other"}
    noun = ("point", "points")
    def classify(s, t): return "point" if t in ("speed", "distance") else "other"
    def is_auditable(s, kind): return kind == "point"
    def is_expected_live(s, t): return s.classify(t) == "point"
    def template_pattern(s, name): return None
    def same_point(s, old, new): return True
    def point_changes(s, old, new, *, comparable=False): return []
    def capture_changes(s, before, after): return []
    def captures_comparable(s, before, after): return False
    def capture_findings(s, capture): return []
    def peer_groups(s, declaration): return []
    def report_sections(s): return {}


class AuditsNothing(Audits):
    """Same protocol, opposite judgement: nothing here is its business."""

    noun = ("widget", "widgets")
    def classify(s, t): return "other"


@pytest.fixture(autouse=True)
def _no_registration():
    """Every test here runs with an EMPTY registry, and puts back whatever the
    session had. An empty registry is the condition being tested: if anything
    were registered, the calls below could be passing on the registration."""
    previous = V._REGISTERED
    V.reset()
    yield
    V.reset()
    if previous is not None:
        V.register(previous)


def _declared_absent(vocabulary):
    report = compare(DeclarationSource(SAMPLE_DECLARATION),
                     Capture(SAMPLE_CAPTURE), vocabulary=vocabulary)
    return report.counts()


class TestTwoVocabulariesInOneProcess:

    def test_the_registry_really_is_empty(self):
        """NON-VACUITY, and the whole point: every assertion below is about
        what happens with nothing registered, and would prove nothing if
        something were."""
        assert not V.registered()

    def test_the_two_vocabularies_disagree_at_all(self):
        """And the second non-vacuity. If both answered the same, the tests
        below would pass against an implementation that ignored the argument
        entirely -- which is exactly the failure they exist to catch."""
        one = _declared_absent(Audits())
        two = _declared_absent(AuditsNothing())
        assert one != two, (
            f"the two vocabularies produce identical counts {one}, so nothing "
            f"below can tell whether the argument was read")

    def test_each_call_answers_in_its_own_domain(self):
        audits = _declared_absent(Audits())
        nothing = _declared_absent(AuditsNothing())
        assert audits["declared"] > 0
        assert audits["matched"] > 0, (
            "the auditing vocabulary matched nothing, so it is not exercising "
            "the path the other one is being compared against")
        assert nothing["matched"] == 0 or nothing["other"] > audits["other"], (
            f"the vocabulary that audits nothing produced {nothing}, which "
            f"does not differ from {audits} in the way it should")

    def test_nothing_was_registered_by_any_of_it(self):
        _declared_absent(Audits())
        assert not V.registered(), (
            "passing a vocabulary registered it, so the next caller in this "
            "process inherits a domain they never chose -- which is the "
            "failure the argument exists to avoid")

    def test_without_a_vocabulary_and_without_a_registration_it_refuses(self):
        """The behaviour that must NOT change. An empty registry is an error,
        never a default: a run that classifies nothing and reports cleanly is
        worse than a crash."""
        with pytest.raises(V.VocabularyNotRegistered):
            compare(DeclarationSource(SAMPLE_DECLARATION), Capture(SAMPLE_CAPTURE))


class TestTheRegisteredVocabularyStillWorks:

    def test_a_registration_is_used_when_no_argument_is_given(self):
        V.register(Audits())
        assert compare(DeclarationSource(SAMPLE_DECLARATION),
                       Capture(SAMPLE_CAPTURE)).counts()["matched"] > 0

    def test_an_argument_wins_for_its_call_and_only_for_its_call(self):
        registered = Audits()
        V.register(registered)
        before = V.current()
        _declared_absent(AuditsNothing())
        assert V.current() is registered is before, (
            "the call's vocabulary outlived the call and replaced the "
            "registered one")


class TestTwoDomainsAtTheSameTime:
    """The property a module global cannot have at all."""

    def test_two_threads_each_see_their_own(self):
        answers = {}
        barrier = threading.Barrier(2)

        def run(name, supplied):
            barrier.wait()                  # both inside the call together
            answers[name] = _declared_absent(supplied)

        threads = [threading.Thread(target=run, args=("audits", Audits())),
                   threading.Thread(target=run, args=("nothing", AuditsNothing()))]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        assert set(answers) == {"audits", "nothing"}, answers
        assert answers["audits"] != answers["nothing"], (
            f"both threads got {answers['audits']}, so one of them saw the "
            f"other's vocabulary -- which is the bug a context-local exists to "
            f"prevent and a module global guarantees")

    def test_the_threads_really_overlapped(self):
        """Before believing the isolation result, prove the two calls were
        actually in flight together. Run one after the other, a module global
        would pass this test too."""
        inside = []
        barrier = threading.Barrier(2, timeout=5)

        def run(supplied):
            with V.using(supplied):
                barrier.wait()              # raises BrokenBarrier if alone
                inside.append(V.noun()[0])

        threads = [threading.Thread(target=run, args=(Audits(),)),
                   threading.Thread(target=run, args=(AuditsNothing(),))]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        assert sorted(inside) == ["point", "widget"], (
            f"both threads read {inside} while inside each other's block")


class TestTheLibraryCanRunWithNoRegistryAtAll:
    """D2, in the form that does not break anybody.

    *Demote the registry to CLI resolution* means the library path reads no
    global state. Making that unconditional would require every caller to pass
    `vocabulary=`, and two published verticals do not -- so the fallback stays
    and a flag turns it off. A consumer who has finished migrating sets it and
    their suite goes red on whatever still relies on ambient state, which is
    the only way to find those calls.

    Here it is used the other way round: to assert that the library really can
    answer with the registry unreachable, rather than to assert it from the
    shape of the code.
    """

    def test_the_flag_makes_a_registration_unusable(self):
        """Non-vacuity for everything below: if the flag did nothing, the
        passing tests would be passing on the registration."""
        V.register(Audits())
        with V.requiring_explicit():
            with pytest.raises(V.VocabularyNotRegistered):
                compare(DeclarationSource(SAMPLE_DECLARATION),
                        Capture(SAMPLE_CAPTURE))

    def test_the_refusal_says_the_flag_is_why(self):
        """A caller who set it in CI and forgot needs to be told that, not
        told they registered nothing when they plainly did."""
        V.register(Audits())
        with V.requiring_explicit():
            with pytest.raises(V.VocabularyNotRegistered) as raised:
                V.current()
        assert V.REQUIRE_EXPLICIT in str(raised.value), str(raised.value)

    def test_compare_answers_with_the_registry_unreachable(self):
        V.register(Audits())
        with V.requiring_explicit():
            counts = compare(DeclarationSource(SAMPLE_DECLARATION),
                             Capture(SAMPLE_CAPTURE),
                             vocabulary=AuditsNothing()).counts()
        assert counts["declared"] > 0, counts

    def test_the_whole_conformance_kit_runs_with_it_off(self):
        """The broadest statement available: the kit drives `compare`,
        `compare_walks` and the report through their public entry points, and
        it passes with nothing registered and the fallback refused."""
        from presence_audit import conformance

        with V.requiring_explicit():
            assert not V.registered()
            assert conformance.check_the_core() == []

    def test_the_flag_is_off_by_default(self):
        """It has to stay off. Two published verticals register and pass
        nothing, and a default that broke them would make the argument a
        removal rather than an addition."""
        import os

        assert V.REQUIRE_EXPLICIT not in os.environ or \
            os.environ[V.REQUIRE_EXPLICIT] in ("", "0")
        V.register(Audits())
        assert compare(DeclarationSource(SAMPLE_DECLARATION),
                       Capture(SAMPLE_CAPTURE)).counts()["declared"] > 0
