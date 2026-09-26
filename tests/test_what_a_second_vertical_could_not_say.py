"""The thirteen things a second and a third vertical could not express.

Every case here was reported from outside, by somebody writing a vertical
against the published core and running into the wall rather than reading about
it. That provenance is why they are in one file: each one is a place where this
core's contract said one thing and its code did another, and the only reason the
gap had never fired is that the one fully worked vertical happened to satisfy
both halves by accident.

**Each test fails against the behaviour it replaces.** That was checked by
reverting each change and re-running, not assumed -- a guard for a defect that
cannot reproduce the defect is a guard nobody can trust.
"""
from __future__ import annotations

import json
import pathlib

import pytest

from presence_audit import attestation, conformance, diff, report, vocabulary
from presence_audit.regression import compare_walks, parse_prefix_map, prefix_pairs


class _Point:
    """A captured point, to the protocol and no further."""

    def __init__(self, name, path=None, reading=1.0, reads=True, kind="measurement"):
        self.name = name
        self.path = path or f"/p/{name}"
        self.reading = reading
        self.is_reading = reads
        self.type = kind
        self.disabled = False
        self.units = None
        self.thresholds: dict = {}


class _Rebuilding:
    """A capture that builds its point list on every read.

    Which the protocol allows -- `points` is typed `-> Iterable[CapturedPoint]`
    and promises nothing about identity -- and which the conformance kit's own
    stand-in does.
    """

    def __init__(self, points):
        self._points = list(points)
        self.complete = True

    @property
    def points(self):
        return [_Point(p.name, p.path, p.reading, p.is_reading, p.type)
                for p in self._points]


class TestACaptureComparedWithItself:
    """#4. Pairing was by `id()`, and the leftovers were computed from a second
    read of `points`."""

    def test_the_kits_own_sample_is_not_three_removed_and_three_added(self):
        same = conformance.Capture(conformance.SAMPLE_CAPTURE)
        counts = compare_walks(same, conformance.Capture(conformance.SAMPLE_CAPTURE),
                               vocabulary=conformance.ReferenceVocabulary()).counts()
        assert counts == {}, (
            f"the kit's own sample capture, compared with itself through the "
            f"kit's own vocabulary, reported {counts}")

    def test_a_capture_that_rebuilds_its_points_pairs_normally(self):
        points = [_Point("a"), _Point("b"), _Point("c")]
        counts = compare_walks(_Rebuilding(points), _Rebuilding(points),
                               vocabulary=conformance.ReferenceVocabulary()).counts()
        assert counts == {}, counts


class TestARenameForNamesThatCarryTheSeparator:
    """#5. Every OPC UA node id contains an equals sign."""

    def test_two_values_need_no_separator(self):
        assert prefix_pairs([("ns=2;s=", "ns=2;s=L1.")]) == [("ns=2;s=", "ns=2;s=L1.")]

    def test_the_string_form_still_reads_what_it_always_read(self):
        assert parse_prefix_map(["HMC_=GPU_", "=added."]) == [("HMC_", "GPU_"), ("", "added.")]

    def test_a_rename_declaring_nothing_is_refused_in_both_forms(self):
        with pytest.raises(ValueError):
            prefix_pairs([("", "")])
        with pytest.raises(ValueError):
            parse_prefix_map(["="])

    def test_the_string_form_says_what_it_cannot_express(self):
        with pytest.raises(ValueError) as refused:
            parse_prefix_map(["no-separator-here"])
        assert "prefix_pairs" in str(refused.value), (
            "the refusal does not name the form that can express it")


class TestTwoPointsAtOneAddress:
    """#13. `setdefault` keeps the first, and which one that is was the order
    the capture listed them in."""

    def _report(self, points):
        return diff.compare(conformance.DeclarationSource(conformance.SAMPLE_DECLARATION),
                            _Rebuilding(points),
                            vocabulary=conformance.ReferenceVocabulary())

    def test_the_discard_is_reported(self):
        kinds = [f.kind for f in self._report(
            [_Point("F-1", "/p/1"), _Point("F-1", "/p/2", reads=False)]).findings]
        assert "duplicate_address" in kinds, kinds

    def test_a_capture_with_one_point_per_address_gets_no_such_finding(self):
        """The control. Without it this passes on a check that fires always."""
        kinds = [f.kind for f in self._report([_Point("F-1"), _Point("F-2")]).findings]
        assert "duplicate_address" not in kinds, kinds

    def test_the_finding_says_how_many_and_why_it_matters(self):
        found = [f for f in self._report(
            [_Point("F-1", "/p/1"), _Point("F-1", "/p/2"), _Point("F-1", "/p/3")]).findings
            if f.kind == "duplicate_address"]
        assert len(found) == 1 and "3 points" in found[0].detail, found


class _Scoring:
    """A vocabulary whose own finding kind is not one of the core's."""

    kinds = ("thing",)
    count_keys: dict = {}
    noun = ("thing", "things")
    regression_kinds = ("substituted_value",)

    def classify(self, declared_type):
        return "thing"

    def is_auditable(self, kind):
        return True

    def is_expected_live(self, declared_type):
        return True

    def template_pattern(self, declared_name):
        return None

    def same_point(self, old, new):
        return True

    def captures_comparable(self, before, after):
        return False

    def point_changes(self, old, new, *, comparable=False):
        return ()

    def capture_changes(self, before, after):
        return ()

    def capture_findings(self, capture):
        return ()

    def peer_groups(self, declaration):
        return ()

    def count_labels(self):
        return {}

    def report_sections(self):
        return {}


class TestAKindTheCoreWouldNeverScore:
    """#7. `is_regression` read a frozen set of the core's own kinds."""

    def test_a_domains_own_kind_counts_when_it_says_so(self):
        with vocabulary.using(_Scoring()):
            assert diff.Finding("substituted_value", "n", "d").is_regression

    def test_a_domain_cannot_unscore_one_of_the_cores(self):
        with vocabulary.using(_Scoring()):
            assert diff.Finding("declared_absent", "n", "d").is_regression

    def test_a_vertical_that_declares_none_is_unaffected(self):
        with vocabulary.using(conformance.ReferenceVocabulary()):
            assert not diff.Finding("substituted_value", "n", "d").is_regression

    def test_the_change_scorer_agrees_with_the_finding_scorer(self):
        """Both modules carry a REGRESSION_KINDS of their own; a hook added to
        one and not the other leaves half the report scored blind."""
        from presence_audit.regression import Change
        with vocabulary.using(_Scoring()):
            assert Change("substituted_value", "n", "d").is_regression


class TestTheJsonReportAcceptsWhatTheTextReportAccepts:
    """#6. `as_json` read eleven members off a declaration source; `as_text`
    took a string, and the permissive one is what a person looks at."""

    def test_a_plain_string_source_survives_json(self):
        payload = report._source_as_json("register.yaml")
        assert payload["path"] == "register.yaml"
        assert payload["provenance"] == "register.yaml"
        assert json.dumps(payload)

    def test_an_object_source_is_unchanged(self):
        class Full:
            kind, path, platform, firmware = "walk", "/w.json", "p", "f"
            captured_at, derived_from = "t", "d"
            reviewed_by, reviewed_on, is_downgrade = "r", "2026-01-01", False
            supplied = ("A", "B")

            def provenance_line(self):
                return "a sentence"

        payload = report._source_as_json(Full())
        assert payload["format"] == "walk" and payload["provenance"] == "a sentence"
        assert payload["points_supplied"] == ["A", "B"]


class TestAMemberTheProtocolRequires:
    """#3. Eleven call sites read one unguarded, and the author got a bare
    `AttributeError` naming an attribute."""

    def test_the_refusal_names_the_member_and_the_kit(self):
        class Short:
            """Declares nothing. Which is what a vertical part-way through its
            first vocabulary looks like."""

        with vocabulary.using(Short()):
            with pytest.raises(vocabulary.PluginError) as refused:
                vocabulary.member("captures_comparable")
        assert "captures_comparable" in str(refused.value)
        assert "conformance" in str(refused.value)

    def test_a_member_that_is_there_is_simply_returned(self):
        with vocabulary.using(_Scoring()):
            assert vocabulary.member("classify")(None) == "thing"


class TestTheKitChecksTheMembersItUsedToSkip:
    """#1. Four of fifteen were in neither list, three of them read with a
    silent fallback."""

    @pytest.mark.parametrize("name,override", [
        ("noun as a plain string", {"noun": "widget"}),
        ("noun as a method", {"noun": lambda self: ("point", "points")}),
        ("count_keys as a method", {"count_keys": lambda self: {"gap": "gaps"}}),
        ("count_labels as a property",
         {"count_labels": property(lambda self: {"a": "A"})}),
        ("report_sections missing", {"report_sections": None}),
        ("regression_kinds as a bare string",
         {"regression_kinds": "substituted_value"}),
    ])
    def test_a_shape_the_core_turns_down_is_reported(self, name, override):
        broken = type("Broken", (conformance.ReferenceVocabulary,), override)()
        problems, _ = conformance.check_a_vocabulary(broken)
        assert problems, f"{name} passed the kit clean"

    def test_every_protocol_member_is_named_somewhere_in_the_kit(self):
        """The check that would have caught the four, and did catch a fifth:
        `regression_kinds` was added while closing this very issue."""
        import ast
        source = pathlib.Path(vocabulary.__file__).read_text()
        tree = ast.parse(source)
        cls = next(n for n in tree.body
                   if isinstance(n, ast.ClassDef) and n.name == "Vocabulary")
        members = [n.name for n in cls.body if isinstance(n, ast.FunctionDef)]
        kit = pathlib.Path(conformance.__file__).read_text()
        missing = [m for m in members if f'"{m}"' not in kit]
        assert missing == [], (
            f"{missing} are declared on the protocol and named nowhere in the "
            f"conformance kit, so a vertical can get them wrong and finish a "
            f"run clean")

    def test_the_reference_vocabulary_is_still_clean(self):
        """The control. Every case above would also pass if the kit reported
        problems for everything."""
        problems, _ = conformance.check_a_vocabulary(conformance.ReferenceVocabulary())
        assert problems == [], problems


class TestTheHookThatNeedsTheDeclaration:
    """#12. `capture_findings` received the capture alone, and its only caller
    holds the declaration."""

    def test_a_vocabulary_that_asks_for_it_is_given_it(self):
        seen = {}

        class Asking(_Scoring):
            def capture_findings(self, capture, *, declaration=None):
                seen["declaration"] = declaration
                return ()

        diff.compare(conformance.DeclarationSource(conformance.SAMPLE_DECLARATION),
                     conformance.Capture(conformance.SAMPLE_CAPTURE),
                     vocabulary=Asking())
        assert seen["declaration"] is not None

    def test_a_vocabulary_written_before_it_is_called_at_its_own_arity(self):
        seen = {}

        class Old(_Scoring):
            def capture_findings(self, capture):
                seen["called"] = True
                return ()

        diff.compare(conformance.DeclarationSource(conformance.SAMPLE_DECLARATION),
                     conformance.Capture(conformance.SAMPLE_CAPTURE),
                     vocabulary=Old())
        assert seen.get("called") is True


class TestTheArtifactAVerticalWrites:
    """#8, #9, #10 and #11, which are all one file's contract with its writer."""

    def test_a_manifest_that_translates_nothing_does_not_raise(self):
        row = attestation._finding(
            {"entity_id": "T-1", "problem_type": "orphaned_deliverable"}, None)
        assert row["statement"] == "orphaned_deliverable"

    def test_a_manifest_that_translates_is_still_asked(self):
        class Manifest:
            sensors = ()

            def translate_finding(self, finding):
                return "a domain sentence"

        row = attestation._finding({"entity_id": "T-1"}, Manifest())
        assert row["statement"] == "a domain sentence"

    def test_the_type_on_a_finding_is_the_engines_and_not_an_identifier(self):
        row = attestation._finding(
            {"entity_id": "T-1", "entity_type": "Deliverable"}, None)
        assert row["entity_type"] == "Deliverable"

    def test_two_declines_differing_only_by_indicator_are_two_rows(self):
        rows = [attestation._decline(
            {"entity_id": "T-1", "indicator": which, "axiom": "STABILITY",
             "reason": "insufficient_samples", "detail": "too few"}, None)
            for which in ("inlet_c", "outlet_c")]
        assert rows[0] != rows[1]
        assert {r["indicator"] for r in rows} == {"inlet_c", "outlet_c"}

    def test_the_arithmetic_behind_a_decline_survives(self):
        row = attestation._decline(
            {"entity_id": "T-1", "reason": "insufficient_samples", "observations": 5,
             "required": 10, "floor_unreachable_at_this_rate": True}, None)
        assert row["measurement"]["floor_unreachable_at_this_rate"] is True
        assert row["measurement"]["observations"] == 5

    def test_a_decline_with_nothing_extra_carries_no_empty_block(self):
        row = attestation._decline(
            {"entity_id": "T-1", "axiom": "A", "reason": "r", "detail": "d"}, None)
        assert "measurement" not in row

    def test_a_verdict_can_be_recorded_and_reads_back(self):
        block = attestation.verdict_block(2, scored_by="a vertical")
        assert block["exit_code"] == 2 and block["meaning"] == "could-not-complete"
        assert attestation._verdict_problems(block) == []

    def test_a_verdict_whose_word_disagrees_with_its_number_is_refused(self):
        assert attestation._verdict_problems(
            {"exit_code": 0, "meaning": "findings", "scored_by": "x"})

    def test_a_verdict_nobody_claims_is_refused(self):
        assert attestation._verdict_problems({"exit_code": 1, "meaning": "findings"})

    def test_an_artifact_written_before_the_slot_existed_still_validates(self):
        artifact = {"format": attestation.ATTESTATION_FORMAT, "target": "t",
                    "engine": {"schema_version": 1}, "checked": {}, "findings": [],
                    "not_checked": [], "evidence": [], "unattested": [],
                    "unread_feeds": []}
        assert attestation.validate_attestation(artifact) == []


class TestADomainThatIsNotTheOneTheKeysWereNamedAfter:
    """#2. The record key, and the one surface a vertical could not route
    around."""

    def test_a_domain_with_its_own_noun_gets_its_own_key(self):
        """And not another domain's: 0.2.0 stopped writing the old key beside it."""
        with vocabulary.using(_Scoring()):
            row = attestation._finding({"entity_id": "T-1"}, None)
        assert row["thing"] == "T-1" and row["point"] == "T-1"
        assert "sensor" not in row

    def test_the_vertical_the_old_key_was_named_after_keeps_it_once(self):
        class Named(_Scoring):
            noun = ("sensor", "sensors")

        with vocabulary.using(Named()):
            row = attestation._finding({"entity_id": "T-1"}, None)
        assert row["sensor"] == row["point"] == "T-1"
        assert list(row).count("sensor") == 1

    def test_the_change_headlines_use_the_noun_they_fetch(self):
        with vocabulary.using(_Scoring()):
            assert "thing" in report.change_headlines()["point_removed"]
