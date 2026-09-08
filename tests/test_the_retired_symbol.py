"""The retired indicator symbol, and the paragraph that is allowed to name it.

Moved here with `generator.py`. It scans THIS package's source, so it could not
stay in `bmc-sensor-audit` once the module left -- it would have been scanning a
tree the symbol was no longer in, and passing for that reason.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


NEEDS_SRC = pytest.mark.skipif(
    not (ROOT / "src" / "presence_audit").is_dir(),
    reason="reads the package SOURCE; absent when running from an sdist or an "
           "installed package. Skipped with a reason rather than failed: a red "
           "here would say the generator is wrong when the tree is simply not "
           "the repository.")


@NEEDS_SRC
class TestTheRetiredMechanismLeavesOnlyItsExplanation:
    """A negative claim that was false because of the sentence making it.

    The generator's docstring tells a reviewer to grep `READING_LOW` rather than
    `neg`, because a word-level grep counts prose about a removal as an instance of
    the thing removed -- four consecutive reviews reported the transform as still
    present on exactly that evidence.

    The first draft of that advice said the symbol was "absent from the whole
    package", and naming it made that false: the sentence became the only
    occurrence. So the claim under test is not *the symbol never appears*, which is
    unmaintainable, but the one that matters -- **no code uses it**.

    Docstrings are stripped before asserting, which is the same discipline a
    `literal not in source` assertion has needed here before.
    """

    @staticmethod
    def _source_without_docstrings(path):
        """The module's text with every docstring removed.

        Walks the AST rather than pattern-matching quotes: a regex for triple-quoted
        blocks is defeated by nested quotes and by a string that merely looks like a
        docstring, and this assertion is only worth making if it is exact.
        """
        import ast
        text = path.read_text()
        tree = ast.parse(text)
        spans = []
        for node in ast.walk(tree):
            if not isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef,
                                     ast.AsyncFunctionDef)):
                continue
            body = getattr(node, "body", None)
            if not body:
                continue
            first = body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) \
                    and isinstance(first.value.value, str):
                spans.append((first.lineno, first.end_lineno))
        lines = text.splitlines()
        kept = [line for number, line in enumerate(lines, start=1)
                if not any(start <= number <= end for start, end in spans)]
        return "\n".join(kept)

    def test_no_code_uses_the_retired_symbol(self):
        src = ROOT / "src" / "presence_audit"
        offenders = []
        for path in sorted(src.rglob("*.py")):
            if "READING_LOW" in self._source_without_docstrings(path):
                offenders.append(str(path.relative_to(ROOT)))
        assert offenders == [], (
            f"{offenders} use READING_LOW outside a docstring; the mirrored "
            f"indicator was retired and nothing should reference it")

    def test_the_retired_symbol_survives_only_here(self):
        """One hit, in the paragraph that explains it. Nought would be ambiguous
        between *retired* and *you mistyped the symbol*."""
        src = ROOT / "src" / "presence_audit"
        hits = {str(p.relative_to(ROOT)): p.read_text().count("READING_LOW")
                for p in sorted(src.rglob("*.py")) if "READING_LOW" in p.read_text()}
        assert hits == {"src/presence_audit/generator.py": 1}, hits

    def test_the_docstring_stripper_actually_strips(self):
        """Non-vacuity. A stripper that returned the whole file would make the
        assertion above pass by never removing anything, and a stripper that
        returned nothing would make it pass by having nothing to find."""
        path = ROOT / "src" / "presence_audit" / "generator.py"
        stripped = self._source_without_docstrings(path)
        assert "If you got here by grepping" not in stripped, "nothing was stripped"
        assert "def generate(" in stripped, "the stripper removed code as well"
