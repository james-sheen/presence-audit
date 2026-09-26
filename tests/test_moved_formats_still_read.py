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
        """The owner, and the newest accepted id -- as `test_supplemental` below
        pins it, for the reason given there: 0.2.0 moved the written id to /2."""
        assert attestation.ATTESTATION_FORMAT.startswith("presence-audit/attestation/")
        assert attestation.ATTESTATION_FORMAT == attestation.ACCEPTED_ATTESTATION_FORMATS[0]
        assert attestation.ATTESTATION_FORMAT_1 in attestation.ACCEPTED_ATTESTATION_FORMATS

    def test_supplemental(self):
        """The claim of this class is the OWNER, not the version.

        It pinned `presence-audit/supplemental/1` outright, so cutting `/2` reddened
        a test whose subject is that the emitted name is this package's own rather
        than the domain it was extracted from. Pinned on the prefix now, plus the
        absence of the old name -- which is the sentence the class is titled for and
        survives every later version.
        """
        assert supplemental.FORMAT.startswith("presence-audit/supplemental/")
        assert supplemental.FORMAT != OLD_SUPPLEMENTAL
        assert supplemental.FORMAT == supplemental.ACCEPTED_FORMATS[0], (
            "the emitted name is not the newest accepted one; a reader taking the "
            "head of that tuple as current would be wrong")

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

    def test_the_accepted_sets_are_pinned_by_size(self):
        """A pin on the SIZE, so a name cannot be added without this failing and
        somebody having to say why it is there.

        THE SUPPLEMENTAL SET WENT TO THREE, AND THIS IS THE SAYING-WHY. `/2` was
        cut because `couplings:` in `/1` is INVISIBLE to a build that predates it:
        measured, such a build loads the file without error, drops the block and
        reports the file as empty, so an operator who declared a coupling would
        get a clean run in which nothing they wrote was read. A reader cannot be
        taught to notice a key it has never heard of, so the notice goes in the
        one field every reader already checks. `/1` is still read, because its
        shape is a subset; a file combining `/1` with a coupling is refused.

        AND TO FOUR. `/3` carries a coupling's `gain_sigma`, a key inside a
        block. Every build reading `/2` already refuses a block key it does not
        know, so nothing would have been dropped -- but it refuses saying the
        format has no field for a spread, which is false of a file written for
        a build that has one. Under `/3` that build names the true cause, a file
        newer than itself. `/2` is still read: it is `/3` with no spread in it.

        AND TO FIVE, WITH THE ATTESTATION SET AT THREE. `/4` renames the two
        member keys a redundant group and a counter used -- the first vertical's
        words -- and carries two blocks no earlier id does, `fault_channels` and
        `actions`; an older build refuses a `/4` file by its id instead of
        dropping both blocks. `attestation/2` keys each record on `point` beside
        the published key. Every earlier id of both is still read, unchanged.
        """
        assert len(attestation.ACCEPTED_ATTESTATION_FORMATS) == 3
        assert len(supplemental.ACCEPTED_FORMATS) == 5
