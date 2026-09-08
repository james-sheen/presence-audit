"""The report's nouns come from the vertical, and nothing in here is spelled.

WHAT WENT WRONG. This package is the domain-free half of a bridge, and its
report told every reader about their `Sensor coverage`, their `firmware` and
their `Redfish interface` -- one vertical's words, hard-coded into forty
sentences of shared code. A factory line running the core was told its weld
stations were sensors. The `Vocabulary` protocol had thirteen members and not
one of them supplied a noun, so there was nothing to ask even if the report had
thought to.

Worse, and quieter: the summary block named two count keys directly,
`not_a_sensor` and `unrecognised_type`. Those are declared by a vertical through
`count_keys`, so a vertical whose keys were called anything else had those counts
in the JSON and MISSING from the text. A shorter list with no sign that anything
was left out.

WHAT THESE TESTS ASK. Not *does the word `sensor` appear* -- that is a word list,
and the header of `test_it_names_no_domain.py` explains why this package does not
keep one. They render the SAME report under two different verticals and require
the output to differ in the places the domain owns, and to carry each vertical's
own words and neither's other. A hard-coded noun fails that no matter which word
it is.
"""

from __future__ import annotations

import pytest

from presence_audit import report, vocabulary
from presence_audit.diff import DiffReport, Finding


class Vertical:
    """A vocabulary that is entirely a fixture, parameterised by its words."""

    def __init__(self, noun, kind, key, label, note):
        self._noun, self._kind, self._key = noun, kind, key
        self._label, self._note = label, note

    @property
    def kinds(self): return ("auditable", self._kind)
    @property
    def count_keys(self): return {self._kind: self._key}
    @property
    def noun(self): return self._noun
    def count_labels(self): return {self._key: (self._label, self._note)}
    def classify(self, declared_type): return "auditable"
    def is_auditable(self, kind): return kind == "auditable"
    def is_expected_live(self, declared_type): return True
    def template_pattern(self, declared_name): return None
    def same_point(self, old, new): return True
    def captures_comparable(self, before, after): return True
    def point_changes(self, old, new, *, comparable=False): return ()
    def capture_changes(self, before, after): return ()
    def capture_findings(self, capture): return ()
    def peer_groups(self, declaration): return ()
    def report_sections(self): return {}


class Excluded:
    """One declaration set aside, as the report's detail lines read it.

    A stand-in with exactly the two attributes those lines touch. The first
    version of this fixture used integers and the second used an empty list --
    the empty one made the count ZERO, which is correctly not printed, so the
    test failed against working code. A fixture can refute a true claim as
    easily as it can confirm a false one.
    """

    def __init__(self, name, type_):
        self.display_name, self.type = name, type_


class Silent(Vertical):
    """A vertical published before `noun` and `count_labels` existed.

    Both members are OPTIONAL, and this is what that has to mean: an older
    vertical keeps working. It answers nothing, so the core must fall back
    rather than raise or reach for another domain's word.
    """
    noun = None
    count_labels = None


ONE = Vertical(("widget", "widgets"), "spare", "spare_widgets",
               "spares", "declared, and not the kind this audit is about")
TWO = Vertical(("valve", "valves"), "manual", "manual_valves",
               "hand-operated", "no actuator to read")


def _render(vertical, *, target="line-1"):
    vocabulary.reset()
    vocabulary.register(vertical)
    built = DiffReport()
    built.findings = [Finding("threshold_missing", "X-1", "a detail", "d.json", "/p/1")]
    built.not_sensor_kinds = {vertical.kinds[1]: [Excluded("A-1", "spare")]}
    return report.as_text(built, target=target)


@pytest.fixture(autouse=True)
def _clean():
    yield
    vocabulary.reset()


class TestTheNounReachesTheOutput:
    def test_each_vertical_gets_its_own_word(self):
        assert "Widget coverage" in _render(ONE)
        assert "Valve coverage" in _render(TWO)

    def test_and_never_the_other_ones(self):
        """The half that a hard-coded noun would still pass. Asserting the right
        word appears says nothing on its own: a report that printed BOTH would
        satisfy it."""
        assert "valve" not in _render(ONE).lower()
        assert "widget" not in _render(TWO).lower()

    def test_the_headline_of_a_finding_carries_it_too(self):
        """Not only the banner. The headlines were a module-level dict, which is
        why they could not have carried a noun before: the dict was built at
        import, and a vertical registers afterwards."""
        assert "live widget" in _render(ONE)
        assert "live valve" in _render(TWO)

    def test_two_verticals_do_not_render_the_same_report_identically(self):
        """The blunt version of all of the above, and the one that cannot be
        satisfied by a coincidence: if any word the domain owns were hard-coded,
        these two would agree."""
        assert _render(ONE) != _render(TWO)


class TestTheVerticalsOwnCountsArePrinted:
    def test_a_key_no_core_code_knows_about_still_appears(self):
        """The silent half of the defect. These counts were in the JSON and not
        in the text, for every vertical whose keys were not the two the core
        named."""
        rendered = _render(ONE)
        assert "spares" in rendered, rendered

    def test_with_the_domains_own_note_beside_it(self):
        assert "not the kind this audit is about" in _render(ONE)

    def test_and_the_other_domains_note_is_not_there(self):
        assert "no actuator to read" not in _render(ONE)


class TestAVerticalThatSuppliesNeither:
    """Both members are optional. This is what that costs and what it must not."""

    def test_it_still_renders(self):
        assert "coverage" in _render(Silent(("x", "y"), "spare", "spare_x", "l", "n"))

    def test_in_the_protocols_own_word(self):
        rendered = _render(Silent(("x", "y"), "spare", "spare_x", "l", "n"))
        assert f"{vocabulary.DEFAULT_NOUN[0].capitalize()} coverage" in rendered

    def test_and_the_unlabelled_count_is_visible_rather_than_dropped(self):
        """Ugly beats invisible. The failure being fixed is a count that was
        silently absent, so a key with no label prints under the key itself."""
        built = DiffReport()
        built.not_sensor_kinds = {"spare": [Excluded("A-1", "spare")]}
        vocabulary.reset()
        vocabulary.register(Silent(("x", "y"), "spare", "spare_x", "l", "n"))
        assert "spare_x" in report.as_text(built)


class TestEveryKindHasAHeadline:
    """The invariant a CONSUMER was checking by importing a private name.

    It is the core that owns both the order and the headlines, so it is the core
    that should fail when they disagree. Asking from downstream meant the check
    ran only where someone had thought to write it, and it broke the moment the
    headlines stopped being a dict.
    """

    def test_every_ranked_kind_is_titled(self):
        missing = [k for k in report.KIND_ORDER if k not in report.headlines()]
        assert missing == [], missing

    def test_every_ranked_change_is_titled(self):
        missing = [k for k in report.CHANGE_ORDER if k not in report.change_headlines()]
        assert missing == [], missing

    def test_the_two_lists_are_not_empty(self):
        """Non-vacuity: `all()` over nothing is True, and both assertions above
        are that shape."""
        assert len(report.KIND_ORDER) > 5 and len(report.CHANGE_ORDER) > 5
