"""A run over nothing says so, at every door the core owns.

An empty input is where a presence audit most easily reports *clean*: nothing
declared absent, nothing changed, nothing attested -- every count zero, and zero
reads exactly like a healthy system. Four doors let that through, or crashed on
it, measured against every vertical that uses this core:

* `compare` quoted the first error of an incomplete capture that recorded
  none, which the protocol calls honest -- and raised `IndexError`, a traceback
  that exits `1`, which this family reads as FINDINGS. The conformance kit's
  own stand-in produces exactly that capture when it holds no sample.
* `feed` of no reports returned an empty result indistinguishable from a feed
  where every point was skipped.
* `compare_walks` of two captures holding no point reported no changes, and the
  text report said every point reported before is reported now.
* `validate_attestation` accepted an artifact whose run put nothing in front of
  the engine.

Each is now said, in a place a caller can read, and none of them is scored
here: the exit code stays the caller's to give, by the compose rule's own
contract.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from presence_audit import vocabulary as V                     # noqa: E402
from presence_audit.attestation import validate_attestation    # noqa: E402
from presence_audit.conformance import (                       # noqa: E402
    Capture, DeclarationSource, ReferenceVocabulary, SAMPLE_CAPTURE,
    SAMPLE_DECLARATION)
from presence_audit.diff import compare                        # noqa: E402
from presence_audit.feeder import DetectOutcome, FeedResult, feed  # noqa: E402
from presence_audit.generator import generate                  # noqa: E402
from presence_audit.regression import compare_walks            # noqa: E402
from presence_audit.report import (                            # noqa: E402
    detect_as_text, regression_as_json, regression_as_text)


@pytest.fixture
def reference():
    previous = V._REGISTERED
    V.reset()
    V.register(ReferenceVocabulary())
    try:
        yield
    finally:
        V._REGISTERED = previous


class _Nothing:
    """A capture that finished and found nothing: `protocols.Capture`, and no
    more. Complete, because a surface can be read in full and hold no point."""

    points = property(lambda s: [])
    captured_at = property(lambda s: None)
    complete = property(lambda s: True)
    errors = property(lambda s: ())


class _Incomplete(_Nothing):
    """Incomplete, and recording no error: the protocol's honest *declining to
    answer*, which is where the claim of completeness lives instead."""

    complete = property(lambda s: False)


class TestAnIncompleteCaptureWithNoErrorToQuote:

    def test_the_kits_own_empty_capture_is_reported_not_raised(self, reference):
        """The incident, on the kit's stand-in: an empty sample capture is
        incomplete and records no error, and quoting its first error raised."""
        report = compare(DeclarationSource(SAMPLE_DECLARATION),
                         Capture({"samples": []}))
        assert report.absence_withheld
        incomplete = [f for f in report.findings if f.kind == "walk_incomplete"]
        assert len(incomplete) == 1
        assert "records no failed fetch" in incomplete[0].detail
        assert not [f for f in report.findings if f.kind == "declared_absent"]

    def test_a_capture_with_an_error_still_quotes_it(self, reference):
        class _Failed(_Incomplete):
            errors = property(lambda s: (("/node/7", "timed out"),))

        report = compare(DeclarationSource(SAMPLE_DECLARATION), _Failed())
        detail = next(f.detail for f in report.findings
                      if f.kind == "walk_incomplete")
        assert "first error was /node/7 (timed out)" in detail


class TestAFeedOfNothing:

    def test_no_reports_is_marked_as_nothing_fed(self, reference):
        _, manifest = generate(DeclarationSource(SAMPLE_DECLARATION),
                               domain_id="nothing")
        result = feed(object(), manifest, [])
        assert result.reports == 0
        assert result.fed_nothing

    def test_a_report_is_counted_and_is_not_nothing(self, reference):
        declaration = DeclarationSource(SAMPLE_DECLARATION)
        _, manifest = generate(declaration, domain_id="something")
        report = compare(declaration, Capture(SAMPLE_CAPTURE))

        class _Session:
            def add_entity(self, *args, **kwargs):
                pass

            def add_observations(self, *args, **kwargs):
                pass

            def add_relationship(self, *args, **kwargs):
                pass

        result = feed(_Session(), manifest, [report])
        assert result.reports == 1
        assert not result.fed_nothing

    def test_the_detect_text_says_nothing_was_fed(self, reference):
        assert "NOTHING FED" in detect_as_text(DetectOutcome(), FeedResult())
        assert "NOTHING FED" not in detect_as_text(DetectOutcome(),
                                                   FeedResult(reports=1))

    def test_a_default_result_says_nothing_was_fed(self):
        """The dataclass default is the empty feed, so a caller that builds
        one itself does not get a result claiming a report arrived."""
        assert FeedResult().fed_nothing


class TestAComparisonOfNothing:

    def test_two_empty_captures_compare_nothing(self, reference):
        report = compare_walks(_Nothing(), _Nothing())
        assert report.compared_nothing
        assert report.changes == []

    def test_the_text_does_not_say_every_point_is_still_reported(self, reference):
        text = regression_as_text(compare_walks(_Nothing(), _Nothing()),
                                  before="a.json", after="b.json")
        assert "Nothing compared" in text
        assert "reported before is reported now" not in text

    def test_the_json_carries_it(self, reference):
        payload = json.loads(regression_as_json(
            compare_walks(_Nothing(), _Nothing()), before="a.json", after="b.json"))
        assert payload["compared_nothing"] is True

    def test_one_side_holding_points_is_a_comparison(self, reference):
        report = compare_walks(Capture(SAMPLE_CAPTURE), _Nothing())
        assert not report.compared_nothing
        assert report.changes

    def test_a_capture_compared_with_itself_still_reads_clean(self, reference):
        capture = Capture(SAMPLE_CAPTURE)
        report = compare_walks(capture, capture)
        assert not report.compared_nothing
        text = regression_as_text(report, before="a.json", after="a.json")
        assert "Nothing compared" not in text
        assert json.loads(regression_as_json(
            report, before="a.json", after="a.json"))["compared_nothing"] is False


def _artifact(**checked):
    return {"format": "presence-audit/attestation/2", "target": "t",
            "engine": {"schema_version": 1, "boundary": None},
            "checked": dict(checked), "findings": [], "not_checked": [],
            "evidence": [], "unattested": [], "unread_feeds": []}


class TestAnAttestationOfNothing:

    def test_a_run_with_no_entities_attests_nothing(self):
        problems = validate_attestation(_artifact(invariants=0, entities=0))
        assert any("checked.entities is 0" in p for p in problems), problems

    def test_a_clean_run_over_entities_is_valid(self):
        assert validate_attestation(_artifact(invariants=12, entities=4)) == []

    def test_an_artifact_that_predates_the_count_is_not_refused_for_it(self):
        """An artifact with no `checked` at all cannot say, and says nothing:
        refusing it would make an older file wrong for lacking a newer field."""
        artifact = _artifact()
        del artifact["checked"]
        assert validate_attestation(artifact) == []
