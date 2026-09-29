"""A live point the declaration switched off is reported whatever its reading's type.

The protocol types `CapturedPoint.reading` as `Optional[float]`, and the finding for a
declared-disabled point that is live printed it with `:g`. A vertical whose point
returned its figure as text -- one does, so a balance-sheet total keeps every digit --
took the whole run down there with a `ValueError`, and a live point carrying no number
did the same with a `TypeError`. Driven through the conformance kit's own stand-ins, so
what is tested is the protocol and nothing a concrete bridge happens to add.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from presence_audit import vocabulary as V  # noqa: E402
from presence_audit.conformance import (  # noqa: E402
    Capture, DeclarationSource, ReferenceVocabulary, SAMPLE_DECLARATION,
)
from presence_audit.diff import compare  # noqa: E402


@pytest.fixture(autouse=True)
def _vocabulary():
    V.reset()
    V.register(ReferenceVocabulary())
    yield
    V.reset()


def _switched_off_but_live(value):
    walk = {"samples": [{"t": "2026-09-29T00:00:00Z", "nodes": {
        "line1.spindle": {"v": 1490.0, "q": "good"},
        "line1.retired": {"v": value, "q": "good"}}}]}
    report = compare(DeclarationSource(SAMPLE_DECLARATION), Capture(walk))
    return [f for f in report.findings if f.kind == "disabled_in_config_but_live"]


@pytest.mark.parametrize("value, shown", [
    (5.0, "reporting 5"),
    (1490.25, "reporting 1490.25"),
    ("9007199254740995", "reporting 9007199254740995"),
    (None, "reporting a reading with no number"),
])
def test_the_finding_is_written_and_shows_the_value(value, shown):
    [finding] = _switched_off_but_live(value)
    assert finding.point == "line1.retired"
    assert shown in finding.detail


def test_a_number_still_reads_as_it_did():
    [finding] = _switched_off_but_live(3.0)
    assert finding.detail.endswith("the machine is reporting 3")
