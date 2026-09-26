"""Format 2: a report in the core's own word, and in the vertical's.

A format-2 report keys each record on `point`, adds the vertical's own word for
the thing it audits, and spells each change kind in that word. A vertical with no
noun of its own reads `point` throughout. The vertical whose word the published
format was named after gets back exactly the kinds it always emitted -- which is
what lets it, and everything downstream of it, move to format 2 without a single
reader of its output noticing.

Format 2 is what every writer produces from 0.2.0, and the old key is written
only where it is the vertical's own word. `spelled=False` keys a record on `point`
alone and leaves each kind in the core's word -- still format 2.
"""

from __future__ import annotations

import json

from presence_audit import attestation, diff, regression, report, vocabulary


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


TAGS = Words(("tag", "tags"))
NONE_OF_ITS_OWN = Words(None)
FIRST = Words(("sensor", "sensors"))
TWO_WORDS = Words(("operating unit", "operating units"))


def _changes():
    return regression.RegressionReport(
        changes=[regression.Change("point_removed", "A-1", "gone"),
                 regression.Change("threshold_moved", "B-2", "moved")],
        before_count=3, after_count=2)


def _regression(words, **spelled):
    return json.loads(report.regression_as_json(_changes(), before="a", after="b",
                                                vocabulary=words, **spelled))


def _diff(words, **spelled):
    built = diff.DiffReport(findings=[diff.Finding("declared_absent", "A-1", "d")])
    return json.loads(report.as_json(built, vocabulary=words, **spelled))


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

    def test_the_old_key_is_written_only_as_the_domains_own_word(self):
        assert "sensor" not in _diff(TAGS)["findings"][0]
        assert _diff(FIRST)["findings"][0]["sensor"] == "A-1"

    def test_the_report_says_which_format_it_is(self):
        assert _diff(TAGS)["format"] == report.REPORT_FORMAT

    def test_asking_for_it_is_the_same_as_the_default(self):
        """Callers written against 0.1.13 pass `spelled=True`; it still means this."""
        assert _diff(TAGS, spelled=True) == _diff(TAGS)

    def test_unspelled_is_point_alone_and_still_format_two(self):
        payload = _diff(TAGS, spelled=False)
        assert payload["format"] == report.REPORT_FORMAT
        assert list(payload["findings"][0])[:2] == ["kind", "point"]
        assert "tag" not in payload["findings"][0]


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
        assert (payload["points_before"], payload["tags_before"]) == (3, 3)
        assert "sensors_before" not in payload

    def test_a_change_carries_the_cores_word_and_the_report_spells_it(self):
        with vocabulary.using(TAGS):
            assert vocabulary.spelled_kind("point_removed") == "tag_removed"

    def test_unspelled_kinds_stay_in_the_cores_word(self):
        payload = _regression(TAGS, spelled=False)
        assert payload["changes"][0]["kind"] == "point_removed"
        assert payload["counts"] == {"point_removed": 1, "threshold_moved": 1}

    def test_a_kind_naming_no_point_is_left_alone(self):
        with vocabulary.using(TAGS):
            assert vocabulary.spelled_kind("threshold_moved") == "threshold_moved"


class TestTheAttestation:

    def test_format_two_is_written_by_default_and_validates(self):
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
                None, envelope, {}, manifest, target="t", attest_fn=attest)
        assert artifact["format"] == attestation.ATTESTATION_FORMAT
        assert attestation.ATTESTATION_FORMAT == attestation.ATTESTATION_FORMAT_2
        assert artifact["findings"][0]["point"] == artifact["findings"][0]["tag"] == "A-1"
        assert "sensor" not in artifact["findings"][0]
        assert attestation.validate_attestation(artifact) == []
        # An artifact written in format 1 is still on disk somewhere, and reads.
        older = dict(artifact, format=attestation.ATTESTATION_FORMAT_1)
        assert attestation.validate_attestation(older) == []
