"""The property this package exists to have, asserted rather than promised.

The extraction was done by IMPORT GRAPH: every module here reaches nothing
domain-specific. That is a fact about a moment unless something re-checks it, so
this file re-derives it on every run, from the tree, without a word list.

A word list was considered and rejected for the reason the engine's own gate
records: a transcribed vocabulary is stale the first time a domain is added, and
it has to be edited by the same person adding the thing it is meant to catch.
What is checked instead is STRUCTURAL -- this package declares no vertical, ships
no vocabulary, and imports nothing outside itself and the standard library.
"""

from __future__ import annotations

import ast
import pathlib
import sys

import pytest

SRC = pathlib.Path(__file__).resolve().parents[1] / "src" / "presence_audit"
MODULES = sorted(SRC.glob("*.py"))


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
