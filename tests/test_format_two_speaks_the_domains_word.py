"""Format 2: a report in the core's own word, and in the vertical's.

A format-2 report keys each record on `point`, adds the vertical's own word for
the thing it audits, and spells each change kind in that word. A vertical with no
noun of its own reads `point` throughout. The vertical whose word the published
format was named after gets back exactly the kinds it always emitted -- which is
what lets it, and everything downstream of it, move to format 2 without a single
reader of its output noticing.

Through the window the published key is still written beside the others; 0.2.0
stops writing it wherever it is not the vertical's own word.
"""

from __future__ import annotations

import json

import pytest

from presence_audit import attestation, diff, regression, report, vocabulary

from test_the_old_names_still_read import Words

TAGS = Words(("tag", "tags"))
NONE_OF_ITS_OWN = Words(None)
FIRST = Words(("sensor", "sensors"))
TWO_WORDS = Words(("operating unit", "operating units"))


def _changes():
    return regression.RegressionReport(
        changes=[regression.Change(regression.PUBLISHED_KINDS["point_removed"], "A-1", "gone"),
                 regression.Change("threshold_moved", "B-2", "moved")],
        before_count=3, after_count=2)


def _regression(words):
    return json.loads(report.regression_as_json(_changes(), before="a", after="b",
                                                vocabulary=words, spelled=True))


def _diff(words):
    built = diff.DiffReport(findings=[diff.Finding("declared_absent", "A-1", "d")])
    return json.loads(report.as_json(built, vocabulary=words, spelled=True))


class TestTheRecordKeys:

    def test_a_record_leads_with_point_and_carries_the_domains_word(self):
        record = _diff(TAGS)["findings"][0]
        assert list(record)[:3] == ["kind", "point", "tag"]
        assert record["point"] == record["tag"] == "A-1"

    def test_a_vertical_with_no_word_of_its_own_reads_point(self):
        record = _diff(NONE_OF_ITS_OWN)["findings"][0]
        assert record["point"] == "A-1" and "point_" not in json.dumps(record)

    def test_a_two_word_noun_is_one_key(self):
        assert _diff(TWO_WORDS)["findings"][0]["operating_unit"] == "A-1"

    def test_the_published_key_is_still_written_through_the_window(self):
        assert _diff(TAGS)["findings"][0]["sensor"] == "A-1"

    def test_the_report_says_which_format_it_is(self):
        assert _diff(TAGS)["format"] == report.REPORT_FORMAT


class TestTheChangeKinds:

    def test_a_kind_naming_a_point_is_spelled_in_the_domains_word(self):
        payload = _regression(TAGS)
        assert [c["kind"] for c in payload["changes"]] == ["tag_removed", "threshold_moved"]
        assert payload["counts"] == {"tag_removed": 1, "threshold_moved": 1}

    def test_the_first_vertical_gets_back_exactly_what_it_emitted(self):
        """The whole reason format 2 can reach its downstream unnoticed."""
        payload = _regression(FIRST)
        assert payload["changes"][0]["kind"] == "sensor_removed"
        assert payload["counts"]["sensor_removed"] == 1
        assert payload["changes"][0]["sensor"] == "A-1"

    def test_a_vertical_with_no_word_reads_the_neutral_kind(self):
        assert _regression(NONE_OF_ITS_OWN)["changes"][0]["kind"] == "point_removed"

    def test_the_counts_before_and_after_are_keyed_the_same_way(self):
        payload = _regression(TAGS)
        assert (payload["points_before"], payload["tags_before"],
                payload["sensors_before"]) == (3, 3, 3)

    @pytest.mark.parametrize("kind", ["point_removed", "sensor_removed"])
    def test_either_spelling_in_spells_the_same_way_out(self, kind):
        with vocabulary.using(TAGS):
            assert vocabulary.spelled_kind(kind) == "tag_removed"

    def test_a_kind_naming_no_point_is_left_alone(self):
        with vocabulary.using(TAGS):
            assert vocabulary.spelled_kind("threshold_moved") == "threshold_moved"


class TestTheAttestation:

    def test_format_two_is_written_on_request_and_validates(self):
        class Evidence:
            def __init__(self, entries): self._entries = entries
            def to_dict(self): return {"meta": {"source": "live"}, "evidence": self._entries}

        def attest(session, problem_type):
            return Evidence([{"entity_id": "T", "problem_type": problem_type,
                              "boundary": "engine-side evidence only",
                              "evidence": {"value": 1}}])

        from presence_audit.generator import GeneratedPoint, Manifest
        manifest = Manifest(domain_id="d", points=[GeneratedPoint(
            entity_type="T", declared_name="A-1", source="f",
            upper=(1.0, 2.0), lower=(None, None))])
        envelope = {"findings": [{"entity_id": "T", "problem_type": "x"}],
                    "not_checked": [], "checked": {}, "meta": {"schema_version": 1}}
        with vocabulary.using(TAGS):
            artifact = attestation.build_attestation(
                None, envelope, {}, manifest, target="t", attest_fn=attest,
                spelled=True)
        assert artifact["format"] == attestation.ATTESTATION_FORMAT_2
        assert artifact["findings"][0]["point"] == artifact["findings"][0]["tag"] == "A-1"
        assert attestation.validate_attestation(artifact) == []
