"""The property this package exists to have, asserted rather than promised.

The extraction was done by IMPORT GRAPH: every module here reaches nothing
domain-specific. That is a fact about a moment unless something re-checks it, so
this file re-derives it on every run, from the tree, without a word list.

A word list was considered and rejected for the reason the engine's own gate
records: a transcribed vocabulary is stale the first time a domain is added, and
it has to be edited by the same person adding the thing it is meant to catch.
What is checked instead is STRUCTURAL.

WHAT THIS FILE USED TO MISS, AND WHY IT IS WORTH KNOWING. Its checks read
`src/presence_audit` and nothing else, while its opening sentence claimed a
property of the PACKAGE. A distribution is not only its modules: `readme` and
`license-files` in `pyproject.toml` put prose INSIDE the built wheel, and the
0.1.0 wheel shipped a NOTICE belonging to the distribution this one was
extracted from -- naming that distribution on its first line, describing a
hardware protocol this package does not implement, and attributing third-party
files to a directory that has never existed here. Every test below passed
throughout. The predicate was cheaper than the claim, and the gap it left was
exactly the most domain-specific text in the distribution.

So the prose that ships is now read too, by predicates derived the same way the
module checks are:

  * the NOTICE's first line must be THIS distribution's name, taken from the
    metadata rather than typed here;
  * every repository path the prose names must exist, with the set of paths
    derived from the actual top-level entries;
  * a NOTICE naming another distribution is making a claim about licensing, so
    the permitted names are this one plus whatever the dependency list declares
    -- which means adding a real dependency licenses naming it, in the same edit.

WHAT IS STILL OUT OF REACH, written down rather than left to be discovered: a
domain named in ordinary words. `OpenBMC` and `Redfish` are capitalised nouns
carrying no hyphen, no path and no backtick, and no structural predicate here
distinguishes them from any other proper noun a notice may legitimately carry.
The 0.1.0 defect is caught by the checks below because it also named a path and
a distribution. One that only prosed about a domain would not be.
"""

from __future__ import annotations

import ast
import pathlib
import re
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parents[1]
SRC = REPO / "src" / "presence_audit"
MODULES = sorted(SRC.glob("*.py"))
PYPROJECT = (REPO / "pyproject.toml").read_text(encoding="utf-8")


def _tree(path):
    return ast.parse(path.read_text(encoding="utf-8"))


def _imports(path):
    """Every module this file imports, absolute and relative alike."""
    out = set()
    for node in ast.walk(_tree(path)):
        if isinstance(node, ast.Import):
            out.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                out.add(".")            # inside this package
            elif node.module:
                out.add(node.module.split(".")[0])
    return out


def test_there_are_modules_to_check():
    """Non-vacuity. Every assertion below quantifies over this list, and `all()`
    of an empty sequence is True -- which would make this file a decoration."""
    assert len(MODULES) >= 10, f"only {len(MODULES)} module(s) found under {SRC}"


@pytest.mark.parametrize("path", MODULES, ids=lambda p: p.name)
def test_a_module_imports_only_itself_and_the_stdlib(path):
    """No third-party import, and no sibling distribution.

    This is what makes the package installable beside any vertical rather than
    dragging one in. `dependencies = []` in `pyproject.toml` is the same claim
    written down; this is the one that can fail.
    """
    external = {m for m in _imports(path)
                if m != "." and m not in sys.stdlib_module_names}
    assert external == set(), (
        f"{path.name} imports {sorted(external)}. If this package needs it, the "
        f"dependency list is now a lie; if a vertical needs it, it belongs there")


def test_no_module_puts_a_vocabulary_INTO_the_registry():
    """Shipping a default vertical would make every consumer inherit a domain
    they did not choose -- and it would be invisible, because registration is a
    side effect of import.

    The predicate is a call to the REGISTRY, resolved from the AST, not the text
    `register(`. The first version of this test looked for that text and flagged
    `plugins.py`, which calls a callable the CALLER supplied -- the loader doing
    its job. A check that fires on the mechanism instead of the act is the wrong
    question asked precisely.
    """
    offenders = []
    for path in MODULES:
        if path.name == "vocabulary.py":          # defines the registry
            continue
        for node in ast.walk(_tree(path)):
            if (isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "register"
                    and isinstance(node.func.value, ast.Name)
                    and "vocabulary" in node.func.value.id):
                offenders.append(f"{path.name}:{node.lineno}")
    assert offenders == [], (
        f"{offenders} put a vocabulary into the registry. This package ships no "
        f"vertical -- a vocabulary arrives from outside or not at all")


def test_the_declared_dependency_list_is_actually_empty():
    """The claim in packaging metadata, checked against the metadata.

    Asserted separately from the import test because the two can drift apart in
    both directions: a dependency can be declared and unused, or used and
    undeclared, and only the second one breaks at install time -- which is the
    one the import test above catches. This catches the other.
    """
    text = (SRC.parents[1] / "pyproject.toml").read_text(encoding="utf-8")
    block = text.split("dependencies = ", 1)[1].splitlines()[0]
    assert block.strip() == "[]", f"dependencies is {block.strip()}, not []"


# --------------------------------------------------------------------------
# The prose that ships inside the distribution.
# --------------------------------------------------------------------------

def _distribution_name() -> str:
    """This package's name, from the metadata. Never typed into this file --
    a name written twice is a name that will disagree with itself, and the
    NOTICE check below is precisely a test for two records having drifted."""
    found = re.search(r'^name\s*=\s*"([^"]+)"', PYPROJECT, re.M)
    assert found, "pyproject.toml declares no name"
    return found.group(1)


def _declared_dependency_names() -> set:
    """Every distribution this package declares, required or optional.

    This is the permission list for the NOTICE check, and it is derived so that
    adding a dependency licenses naming it IN THE SAME EDIT. A hand-kept list
    here would have to be updated by whoever adds the dependency -- the exact
    shape this file's header rejects.
    """
    blocks = []
    for found in re.finditer(r"^dependencies\s*=\s*\[", PYPROJECT, re.M):
        blocks.append(_bracketed(PYPROJECT, found.end() - 1))
    optional = re.search(r"^\[project\.optional-dependencies\]$", PYPROJECT, re.M)
    if optional:
        rest = PYPROJECT[optional.end():]
        table = rest.split("\n[", 1)[0]
        for found in re.finditer(r"=\s*\[", table):
            blocks.append(_bracketed(table, found.end() - 1))
    out = set()
    for block in blocks:
        for spec in re.findall(r'"([^"]+)"', block):
            name = re.split(r"[<>=!~;\s\[]", spec, 1)[0]
            if name:
                out.add(name.lower())
    return out


def _bracketed(text: str, start: int) -> str:
    """The `[...]` beginning at `start`, so a dependency list wrapped over
    several lines is read whole. Reading one line was the first version and it
    would silently permit nothing past the first entry."""
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "[":
            depth += 1
        elif text[i] == "]":
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
    return text[start:]


def _shipped_prose() -> list:
    """The non-code files the BUILT WHEEL carries, derived from the metadata
    that puts them there: `readme` becomes the distribution's description and
    `license-files` are copied into `.dist-info`. Deriving it means a third
    licence file is covered the day it is declared, not the day someone
    remembers this test exists."""
    names = []
    readme = re.search(r'^readme\s*=\s*"([^"]+)"', PYPROJECT, re.M)
    if readme:
        names.append(readme.group(1))
    licences = re.search(r'^license-files\s*=\s*\[([^\]]*)\]', PYPROJECT, re.M)
    if licences:
        names += re.findall(r'"([^"]+)"', licences.group(1))
    return [REPO / n for n in names if (REPO / n).is_file()]


def _paths_named_in(text: str) -> list:
    """Repository paths the prose mentions.

    The alternation is the repository's OWN top-level entries, so this cannot
    drift from the tree and cannot mistake a format id like
    `some-package/thing/1` for a path -- nothing named `some-package` is at the
    top level, so it is never a candidate in the first place.
    """
    tops = sorted(p.name for p in REPO.iterdir() if not p.name.startswith("."))
    if not tops:
        return []
    pattern = r"\b(?:%s)/[A-Za-z0-9_./-]*" % "|".join(re.escape(t) for t in tops)
    return [m.rstrip("./,;:") for m in re.findall(pattern, text)]


class TestTheProseThatShipsIsRead:
    """`src/` is not the distribution. These files travel inside the wheel."""

    def test_the_prose_set_is_not_empty_and_includes_the_notice(self):
        """NON-VACUITY, and it is not a formality here: every check below
        quantifies over this list, and the derivation could return nothing if a
        metadata key were renamed -- which would turn this whole class green and
        blind in one edit."""
        shipped = _shipped_prose()
        assert shipped, "no shipped prose found; the derivation reads nothing"
        assert any(p.name == "NOTICE" for p in shipped), (
            f"NOTICE is not among {[p.name for p in shipped]}, so the file that "
            f"was wrong in 0.1.0 would not be read")

    def test_the_notice_names_this_distribution(self):
        """The 0.1.0 defect in one line: the NOTICE opened with the name of the
        distribution this one was extracted from."""
        notice = REPO / "NOTICE"
        first = next(line.strip() for line in
                     notice.read_text(encoding="utf-8").splitlines() if line.strip())
        assert first == _distribution_name(), (
            f"NOTICE opens with {first!r}; this distribution is "
            f"{_distribution_name()!r}. A licence notice describes one "
            f"distribution and does not inherit")

    @pytest.mark.parametrize("path", _shipped_prose(), ids=lambda p: p.name)
    def test_it_names_no_path_that_is_missing(self, path):
        """A notice claiming redistributed content must point at content that
        ships. 0.1.0's attributed twelve third-party files to a directory this
        distribution has never contained -- an attribution for nothing, which is
        worse than a missing one because it reads as diligence."""
        missing = [p for p in _paths_named_in(path.read_text(encoding="utf-8"))
                   if not (REPO / p).exists()]
        assert missing == [], (
            f"{path.name} names {missing}, which do not exist. Either the file "
            f"describes content that is not here, or the content was removed "
            f"and the prose kept")

    def test_the_notice_names_no_distribution_outside_the_dependency_list(self):
        """In a NOTICE a named distribution is a claim about licensing.

        Scoped to the NOTICE deliberately. The README says *extracted from* and
        names its predecessor, which is honest provenance -- a check that refused
        it would be refusing the true sentence to catch the false one. Measured
        before scoping: the README's one hyphenated name is that sentence, and
        all three in 0.1.0's NOTICE were part of the inherited text.
        """
        text = (REPO / "NOTICE").read_text(encoding="utf-8")
        allowed = _declared_dependency_names() | {_distribution_name().lower()}
        named = {m.strip("`").lower()
                 for m in re.findall(r"`[a-z0-9]+(?:-[a-z0-9]+)+`", text)}
        assert named <= allowed, (
            f"the NOTICE names {sorted(named - allowed)}, which this package "
            f"neither is nor depends on. Naming it here claims a licensing "
            f"relationship; declare the dependency or drop the mention")

    def test_that_last_check_can_actually_fire(self):
        """Before believing a negative, prove the probe can produce a positive.
        The NOTICE currently backticks no hyphenated name at all, so the check
        above passes over an EMPTY set -- true, and true of a broken predicate
        too. This runs the same predicate over text that must fail it."""
        allowed = _declared_dependency_names() | {_distribution_name().lower()}
        sample = "attributed to `some-other-distribution` for no reason"
        named = {m.strip("`").lower()
                 for m in re.findall(r"`[a-z0-9]+(?:-[a-z0-9]+)+`", sample)}
        assert named and not named <= allowed, (
            "the predicate cannot see a distribution name it should refuse")
