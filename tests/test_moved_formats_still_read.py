"""Two format names moved distributions. The SHAPE did not.

`attestation.py` and `supplemental.py` emitted `bmc-sensor-audit/...` because
that is where they used to live. They emit `presence-audit/...` now. An artifact
already on disk carries the old name and is still exactly the same document, so
refusing it would be inventing an incompatibility to match a package rename --
and one of those artifacts is read by a live downstream tool.

So: emit one, accept both. These tests are what make that true rather than
intended, and they are the reason the extraction is not a breaking change for
anybody holding an older file.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from presence_audit import attestation, supplemental

OLD_ATTESTATION = "bmc-sensor-audit/attestation/1"
OLD_SUPPLEMENTAL = "bmc-sensor-audit/supplemental/1"


class TestTheEmittedNameIsTheNewOne:
    def test_attestation(self):
        assert attestation.ATTESTATION_FORMAT == "presence-audit/attestation/1"

    def test_supplemental(self):
        assert supplemental.FORMAT == "presence-audit/supplemental/1"

    def test_the_documented_example_shows_what_is_emitted(self):
        """A docstring showing the old name reads as current and outlives the
        change. The example a reader copies has to be the one that is written."""
        assert OLD_SUPPLEMENTAL not in supplemental.load_supplemental.__module__ or True
        src = Path(supplemental.__file__).read_text(encoding="utf-8")
        block = src.split("## The file", 1)[1].split('"""', 1)[0]
        assert supplemental.FORMAT in block
        assert OLD_SUPPLEMENTAL not in block


class TestTheOldNameStillReads:
    def test_an_attestation_written_before_the_move_is_accepted(self):
        artifact = {"format": OLD_ATTESTATION}
        problems = attestation.validate_attestation(artifact)
        assert not [p for p in problems if "format is" in p], (
            f"the old format name was refused: {problems}")

    def test_an_attestation_written_after_the_move_is_accepted(self):
        artifact = {"format": attestation.ATTESTATION_FORMAT}
        problems = attestation.validate_attestation(artifact)
        assert not [p for p in problems if "format is" in p]

    def test_a_supplemental_written_before_the_move_is_accepted(self, tmp_path):
        p = tmp_path / "s.json"
        p.write_text(json.dumps({"format": OLD_SUPPLEMENTAL,
                                 "provenance": "a person"}), encoding="utf-8")
        supplemental.load_supplemental(str(p))          # must not raise

    def test_a_supplemental_written_after_the_move_is_accepted(self, tmp_path):
        p = tmp_path / "s.json"
        p.write_text(json.dumps({"format": supplemental.FORMAT,
                                 "provenance": "a person"}), encoding="utf-8")
        supplemental.load_supplemental(str(p))


class TestAnUnknownNameIsStillRefused:
    """The acceptance widened by exactly two strings, not into a wildcard.

    Without this the tests above are satisfied by a build that accepts anything,
    and a presence audit that reads a document it does not understand is the
    failure the format id exists to prevent.
    """

    def test_attestation(self):
        problems = attestation.validate_attestation({"format": "something/else/9"})
        assert [p for p in problems if "format is" in p], (
            "an unknown format was accepted")

    def test_supplemental(self, tmp_path):
        p = tmp_path / "s.json"
        p.write_text(json.dumps({"format": "something/else/9"}), encoding="utf-8")
        with pytest.raises(supplemental.SupplementalError):
            supplemental.load_supplemental(str(p))

    def test_the_accepted_sets_are_exactly_two_each(self):
        """A pin on the SIZE, so a third name cannot be added without this
        failing and somebody having to say why it is there."""
        assert len(attestation.ACCEPTED_ATTESTATION_FORMATS) == 2
        assert len(supplemental.ACCEPTED_FORMATS) == 2
