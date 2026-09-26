"""The reading window: every renamed public name still reads, and says so.

This package's public names carried its first vertical's word for what it audits,
and 0.1.13 renamed them to the word the package has used about itself all along.
A consumer that has not moved yet must keep working through the 0.1 line: every
old keyword is accepted, every old attribute answers, and each says what replaced
it. 0.2.0 removes them, and a consumer's `<0.2` ceiling keeps that release out
until it has moved.

Every test here is one line of that promise, and this whole file is what 0.2.0
deletes.
"""

from __future__ import annotations

import json
import warnings

import pytest

from presence_audit import diff, generator, regression, report, supplemental

OLD_SUBJECT = "sensor"
OLD_SUBJECTS = "sensors"


class Words:
    """A vocabulary that is entirely a fixture: a noun and nothing else."""

    def __init__(self, noun):
        self._noun = noun

    kinds = ("auditable", "spare")
    count_keys = {"spare": "spares"}

    @property
    def noun(self): return self._noun
    def count_labels(self): return {"spares": ("spare", "not audited")}
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
    def regression_kinds(self): return ()
    def report_sections(self): return {}


def _one_warning(record, new: str) -> None:
    messages = [str(w.message) for w in record
                if issubclass(w.category, DeprecationWarning)]
    assert len(messages) == 1 and new in messages[0], messages


class TestTheOldKeywordIsAccepted:

    @pytest.mark.parametrize("cls", [diff.Finding, regression.Change])
    def test_a_record_built_under_the_old_keyword_is_the_same_record(self, cls):
        with warnings.catch_warnings(record=True) as record:
            warnings.simplefilter("always")
            old = cls(kind="x", detail="d", **{OLD_SUBJECT: "A-1"})
        _one_warning(record, "point")
        assert old == cls("x", "A-1", "d")

    @pytest.mark.parametrize("cls", [diff.Finding, regression.Change])
    def test_both_spellings_at_once_is_a_caller_bug(self, cls):
        with pytest.raises(TypeError, match="both 'point'"):
            cls(kind="x", point="A", detail="d", **{OLD_SUBJECT: "B"})

    def test_a_manifest_takes_the_old_keyword(self):
        point = generator.GeneratedPoint(entity_type="T", declared_name="A",
                                         source="f", upper=(1.0, 2.0),
                                         lower=(None, None))
        with warnings.catch_warnings(record=True) as record:
            warnings.simplefilter("always")
            manifest = generator.Manifest(domain_id="d", **{OLD_SUBJECTS: [point]})
        _one_warning(record, "points")
        assert manifest.points == [point]

    def test_the_supplemental_records_take_their_old_keywords(self):
        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            group = supplemental.RedundantGroup(basis="b", **{OLD_SUBJECTS: ("A", "B")})
            counter = supplemental.Counter(basis="b", **{OLD_SUBJECT: "C"})
        assert group.points == ("A", "B") and counter.point == "C"


class TestTheOldAttributeAnswers:

    def test_a_finding_and_a_change_answer_under_the_old_name(self):
        for record in (diff.Finding("x", "A-1", "d"), regression.Change("x", "A-1", "d")):
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                assert getattr(record, OLD_SUBJECT) == "A-1"
            _one_warning(caught, "point")

    def test_a_manifest_answers_and_its_list_is_the_same_list(self):
        manifest = generator.Manifest(domain_id="d")
        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            assert getattr(manifest, OLD_SUBJECTS) is manifest.points

    def test_the_excluded_kinds_answer_both_ways(self):
        built = diff.DiffReport()
        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            setattr(built, "not_" + OLD_SUBJECT + "_kinds", {"spare": ["A"]})
            assert getattr(built, "not_" + OLD_SUBJECT + "_kinds") == {"spare": ["A"]}
        assert built.not_point_kinds == {"spare": ["A"]}

    def test_the_old_class_name_imports(self):
        with warnings.catch_warnings(record=True) as record:
            warnings.simplefilter("always")
            cls = getattr(generator, "Generated" + OLD_SUBJECT.capitalize())
        _one_warning(record, "GeneratedPoint")
        assert cls is generator.GeneratedPoint


class TestTheDefaultOutputDidNotMove:
    """Format 1 is the default through the window, byte for byte: a reader
    switching on its keys and kinds sees nothing change until it asks for 2."""

    def test_a_record_still_carries_the_published_key_and_no_new_one(self):
        built = diff.DiffReport(findings=[diff.Finding("declared_absent", "A-1", "d")])
        payload = json.loads(report.as_json(built, vocabulary=Words(("widget", "widgets"))))
        record = payload["findings"][0]
        assert record[OLD_SUBJECT] == "A-1" and record["widget"] == "A-1"
        assert "point" not in record and "format" not in payload

    def test_a_change_still_carries_the_published_kind(self):
        built = regression.RegressionReport(changes=[regression.Change(
            regression.PUBLISHED_KINDS["point_removed"], "A-1", "gone")])
        payload = json.loads(report.regression_as_json(built, before="a", after="b"))
        assert payload["changes"][0]["kind"] == OLD_SUBJECT + "_removed"
        assert payload["counts"] == {OLD_SUBJECT + "_removed": 1}
        assert OLD_SUBJECTS + "_before" in payload

    def test_either_spelling_of_a_kind_is_a_regression(self):
        for kind in ("point_removed", OLD_SUBJECT + "_removed"):
            assert regression.Change(kind, "A", "d").is_regression
