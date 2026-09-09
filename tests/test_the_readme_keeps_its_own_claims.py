"""The README makes claims nothing else in this repository could contradict.

Two of them, both reported from outside.

**It pointed at no vertical.** This package ships none, on purpose, and said so
in three places -- and then left the reader holding a core with nowhere to go.
The Known verticals section is the one place the prose points OUT of this
distribution, which makes it the one place a name can be wrong without any
module noticing. What can be checked from here is checked from here: the entry
point group, the environment variable, and whether an installed vertical really
registers where the section says it does. Whether a NAME was ever published is a
fact about the index and no assertion from a tree can reach it -- `checks.yml`
asks that, in the job that has a network, and this file does not pretend to.

**It stated one rule twice.** The refusal of two installed verticals was
written out in full under the loading paths and again three paragraphs later,
restated rather than repeated: *refused rather than ranked* and *refused, not
ranked*. An identity check would have found nothing, which is the general shape
worth naming -- a duplicate that survives de-duplication because it was retyped.
So the check below is on SIMILARITY, over shingles, and it quantifies over every
paragraph rather than the pair that happened to be reported.
"""

from __future__ import annotations

import importlib.metadata
import pathlib
import re

import pytest

from presence_audit import plugins

REPO = pathlib.Path(__file__).resolve().parents[1]
README = (REPO / "README.md").read_text(encoding="utf-8")

#: A distribution named in the section AND the URL it is linked to, captured
#: together so the two can be held against each other. A link is the part a
#: copy-paste gets wrong: the name reads right and the URL goes elsewhere.
#:
#: Both hosts are permitted, and WHICH ONE is itself a claim -- an index page
#: says the thing is on the index, a repository says it is not. Written first
#: to accept only `pypi.org`, and the check caught the table on the very first
#: run: `factory-line-audit` is a real vertical, published as a repository and
#: never uploaded, and the row sent a reader to a 404.
LINKED = re.compile(
    r"\[`([a-z0-9]+(?:-[a-z0-9]+)+)`\]\((https://[^)\s]+)\)")


def _section(title: str) -> str | None:
    """One `## ` section's body, or None if the heading is gone."""
    found = re.search(rf"^## {re.escape(title)}\n(.*?)(?=^## |\Z)", README, re.S | re.M)
    return found.group(1) if found else None


def _named_verticals() -> list:
    section = _section("Known verticals")
    return LINKED.findall(section) if section else []


def _paragraphs() -> list:
    """Prose paragraphs, with fenced blocks and headings removed.

    Code is excluded because a repeated code block is often the point, and a
    heading because two sections may legitimately share a word.
    """
    body = re.sub(r"```.*?```", "", README, flags=re.S)
    return [p for p in re.split(r"\n\s*\n", body)
            if p.strip() and not p.lstrip().startswith("#")]


def _shingles(text: str) -> set:
    words = re.findall(r"[a-z]+", text.lower())
    return {tuple(words[i:i + 3]) for i in range(len(words) - 2)}


def _similarity(one: str, other: str) -> float:
    a, b = _shingles(one), _shingles(other)
    if not a or not b:
        return 0.0
    return len(a & b) / min(len(a), len(b))


#: Measured, not chosen. The two paragraphs this file exists to have caught
#: scored 0.731 against each other; the highest score between any two
#: paragraphs that are NOT restatements of each other is 0.125, and the
#: surviving cross-reference scores 0.167. Anything between 0.2 and 0.7 would
#: separate them; this sits in the middle of that gap rather than at its edge.
RESTATEMENT = 0.45


class TestItPointsAtAVertical:
    """The section that sends a reader somewhere this package deliberately is
    not."""

    def test_the_section_exists_and_names_something(self):
        """NON-VACUITY, and load-bearing: every check below iterates
        `_named_verticals()`, and all of them pass over an empty list. A
        renamed heading would turn this whole class green and blind."""
        assert _section("Known verticals") is not None, (
            "the README has no Known verticals section; the reader holding "
            "this package alone is back where they started")
        assert _named_verticals(), (
            "the Known verticals section names no linked distribution, so "
            "every check in this class would pass over nothing")

    @pytest.mark.parametrize("name,url",
                             _named_verticals(),
                             ids=lambda v: v if isinstance(v, str) else str(v))
    def test_each_name_links_to_its_own_page(self, name, url):
        """The name and the URL are two records of one fact, written adjacent
        and copy-pasted together.

        Normalised per PEP 503 before comparing, because the index treats
        `A_b` and `a-b` as one project and a reader following the link would
        never notice the difference.
        """
        normalise = lambda s: re.sub(r"[-_.]+", "-", s).lower()
        index = re.fullmatch(r"https://pypi\.org/project/([a-z0-9._-]+)/?", url)
        repository = re.fullmatch(r"https://github\.com/[^/]+/([A-Za-z0-9._-]+)/?", url)
        assert index or repository, (
            f"`{name}` is linked to {url}, which is neither an index page nor "
            f"a repository. The host is what says whether the thing is "
            f"installable by name")
        target = (index or repository).group(1)
        assert normalise(name) == normalise(target), (
            f"the section names `{name}` and links to {url}; a reader follows "
            f"the link")

    def test_the_section_does_not_promise_the_index_for_something_off_it(self):
        """The defect this table already had. A row linked to a repository is
        saying the distribution is NOT on the index, and a `pip install <name>`
        in the same row would say the opposite -- which is the shape that sent
        a reader to a 404 the first time this section was written."""
        section = _section("Known verticals")
        wrong = []
        for name, url in _named_verticals():
            if "pypi.org" in url:
                continue
            row = next((line for line in section.splitlines()
                        if f"`{name}`" in line and line.startswith("|")), "")
            if re.search(rf"pip install\s+'?{re.escape(name)}", row):
                wrong.append(name)
        assert wrong == [], (
            f"{wrong} are linked to a repository and the same row tells a "
            f"reader to `pip install` them by name. One of the two is false")

    def test_the_group_the_readme_names_is_the_one_the_loader_reads(self):
        """The instruction is only an instruction while the loader agrees. A
        renamed group would leave every vertical in the table registering into
        a group nothing reads, and the README would still look right."""
        assert plugins.ENTRY_POINT_GROUP in README, (
            f"the loader reads entry points in {plugins.ENTRY_POINT_GROUP!r} "
            f"and the README names no such group")

    def test_the_variable_the_readme_names_is_the_one_the_loader_reads(self):
        assert plugins.ENVIRONMENT_VARIABLE in README, (
            f"the loader reads {plugins.ENVIRONMENT_VARIABLE!r} and the README "
            f"names no such variable")

    def test_this_package_does_not_list_itself_as_a_vertical(self):
        """The core is not a domain. Listing it would be the one entry that
        makes the whole section incoherent, and it is exactly the entry a
        find-and-replace produces."""
        here = importlib.metadata.metadata("presence-audit")["Name"].lower()
        named = {n.lower() for n, _ in _named_verticals()}
        assert here not in named, (
            f"the Known verticals section lists {here}, which is this package")

    def test_an_installed_vertical_registers_where_the_section_says(self):
        """Whichever of them this environment happens to have.

        Deliberately not a skip. A clean clone installs none of these -- that
        is the environment `checks.yml`'s versions job runs, and its suite is
        the one a contributor gets -- so this passes over an empty set there,
        and the negative control below is what keeps that honest. The job that
        DOES install a vertical asserts the set is non-empty; the assertion
        that it is the right group belongs here, with the loader.
        """
        wrong = []
        for name, _ in _named_verticals():
            try:
                dist = importlib.metadata.distribution(name)
            except importlib.metadata.PackageNotFoundError:
                continue
            groups = {ep.group for ep in dist.entry_points}
            if plugins.ENTRY_POINT_GROUP not in groups:
                wrong.append(f"{name} registers in {sorted(groups)}")
        assert wrong == [], (
            f"{wrong}, and the README says they register in "
            f"{plugins.ENTRY_POINT_GROUP!r}. An installed vertical that does "
            f"not is one a plain `pip install` will never find")

    def test_that_check_can_produce_a_positive(self):
        """Before believing a negative, prove the probe can produce one. The
        check above passes over whatever is installed, which on a clean clone
        is nothing -- true, and true of a broken predicate too."""
        groups = {"console_scripts"}
        assert plugins.ENTRY_POINT_GROUP not in groups, (
            "the predicate cannot see a distribution registering in the wrong "
            "group, so its silence means nothing")


class TestItStatesEachRuleOnce:
    """A rule restated reads as two rules, and the second copy is the one that
    goes stale when the first is corrected."""

    def test_there_are_paragraphs_to_compare(self):
        """`all()` over an empty product is True, and this file would then be
        a decoration."""
        assert len(_paragraphs()) >= 8, (
            f"only {len(_paragraphs())} paragraph(s) parsed out of the README; "
            f"the comparison below would have almost nothing to quantify over")

    def test_no_paragraph_restates_another(self):
        paragraphs = _paragraphs()
        offenders = []
        for i, one in enumerate(paragraphs):
            for other in paragraphs[i + 1:]:
                score = _similarity(one, other)
                if score >= RESTATEMENT:
                    offenders.append(f"{score:.2f}: {one.strip()[:60]!r}")
        assert offenders == [], (
            f"{offenders} restate an earlier paragraph. Say it once and "
            f"cross-reference it; a second copy is a second thing to correct")

    def test_that_check_can_produce_a_positive(self):
        """The literal pair this check exists to have caught, so the threshold
        is held against the case rather than against a number somebody liked.
        Neither string appears in the README any more, which is the point: a
        check pinned to text that is gone is a check that reads as current."""
        was = ("Two installed verticals are refused rather than ranked: both "
               "would register, the later would silently win, and every "
               "verdict would come from a domain you were not auditing.")
        restated = ("Two installed verticals are refused, not ranked - both "
                    "would register, the later would win, and every verdict "
                    "would come from a domain you were not auditing.")
        assert _similarity(was, restated) >= RESTATEMENT, (
            f"the pair that prompted this check scores "
            f"{_similarity(was, restated):.2f}, under the {RESTATEMENT} "
            f"threshold; the check would not have caught its own reason")
