"""A whole domain, driving this package end to end.

In `bmc-sensor-audit` this file asserted that the core could serve a domain it
was not written for. Here that framing is gone, because this package was written
for no domain at all -- so what it now asserts is simply that the thing works:
one vocabulary, one capture shape, one declaration shape, and a three-valued
answer that discriminates.

The original framing is kept in the paragraph below because it is still the
reason the file exists.

A domain this package was not written for, running on its neutral core.

No BMC anything: a factory-line vocabulary, factory-line data in its own shape
-- time-ordered samples of many nodes, and an asset register -- adapted onto the
protocols, driven through the same `compare()` the presence audit is written in.

This is the measurement the neutral-core work exists to produce. If it stops
passing, the core has stopped being shared and is only this domain's code with
an indirection.

The stand-ins below implement the published protocols and NOTHING ELSE -- no
`__iter__`, no `__len__`, no convenience the concrete BMC types happen to have.
That is the point of them. A fixture that adds a member to get past a call site
proves the core can serve a domain that already knows what the document does not
say, which is not the claim.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from presence_audit import PROTOCOL_VERSION
from presence_audit import protocols as P
from presence_audit import vocabulary as V
from presence_audit.diff import compare
from presence_audit.regression import compare_walks

# THE STAND-INS ARE IMPORTED, NOT DEFINED. They used to live in this file, which
# meant the kit under test and the kit a vertical author could run were two
# different pieces of code with nothing holding them together. They now ship in
# `presence_audit.conformance`, and this file drives the shipped copy -- so the
# thing that is tested is the thing that is published.
from presence_audit.conformance import (                    # noqa: E402
    REFERENCE_KINDS as KINDS,
    CapturedPoint as _P,
    Capture as _C,
    DeclaredPoint as _D,
    DeclarationSource as _DS,
    ReferenceVocabulary as FactoryLineVocabulary,
    SAMPLE_CAPTURE as WALK,
    SAMPLE_DECLARATION as REGISTER,
)

V.reset(); V.register(FactoryLineVocabulary())


@pytest.fixture
def factory_line_registered():
    """The vocabulary alone, for tests that drive an entry point themselves."""
    previous = V._REGISTERED
    V.reset()
    V.register(FactoryLineVocabulary())
    try:
        yield
    finally:
        V._REGISTERED = previous


@pytest.fixture
def foreign_report():
    previous = V._REGISTERED
    V.reset()
    V.register(FactoryLineVocabulary())
    try:
        yield compare(_DS(REGISTER), _C(WALK))
    finally:
        V._REGISTERED = previous


class TestTheCoreServesADomainItWasNotWrittenFor:
    def test_it_produces_a_three_valued_presence_diff(self, foreign_report):
        kinds = {f.kind for f in foreign_report.findings}
        assert kinds == {"declared_unreadable", "declared_absent",
                         "undeclared_present"}, (
            f"the core did not produce a presence diff for this domain: {kinds}")

    def test_each_of_the_three_lands_on_the_right_tag(self, foreign_report):
        by_kind = {f.kind: f.point for f in foreign_report.findings}
        assert by_kind["declared_unreadable"] == "line1.gap"
        assert by_kind["declared_absent"] == "line1.absent"
        assert by_kind["undeclared_present"] == "line1.rogue"

    def test_the_excluded_tag_is_not_judged(self, foreign_report):
        """`line1.retired` is excluded by the register. Four tags are declared;
        three are audited. A core that counted four would be judging a point the
        domain set aside."""
        assert foreign_report.counts()["declared"] == 3

    def test_this_domain_declares_the_revision_it_was_written_against(self):
        """NON-VACUITY for the check below, and for the module-scope
        registration this whole file runs on: an undeclared version takes the
        absent path, which is admitted, so the gate would never run here."""
        assert hasattr(FactoryLineVocabulary, "protocol_version"), (
            "the foreign vocabulary declares no protocol version, so "
            "registering it exercises none of the version check")
        assert FactoryLineVocabulary.protocol_version == PROTOCOL_VERSION

    def test_the_same_domain_declaring_another_revision_is_refused(self):
        """The gate, run against the vocabulary this file already registers.
        A refusal proved on a throwaway object proves it about the object;
        this proves it about the one the rest of the file depends on."""
        wrong = FactoryLineVocabulary()
        wrong.protocol_version = PROTOCOL_VERSION + 1
        try:
            with pytest.raises(V.PluginError):
                V.register(wrong)
        finally:
            V.reset()
            V.register(FactoryLineVocabulary())

    def test_the_adapter_offers_ONLY_protocol_members(self):
        """The load-bearing assertion.

        If this adapter carried a member the protocol does not declare, the run
        above would prove the core works against THIS package's names rather
        than against the protocol. It offered `sensors` and
        `disabled_in_config` once, and the core read them; those reads are gone
        and so are the shims.
        """
        import ast
        import inspect as _inspect
        declared = set()
        for cls in (_P, _C, _D, _DS):
            declared |= {n for n in vars(cls) if not n.startswith("_")}
        allowed = set()
        for node in ast.parse(_inspect.getsource(P)).body:
            if isinstance(node, ast.ClassDef):
                allowed |= {x.name for x in node.body
                            if isinstance(x, ast.FunctionDef)}
        extra = declared - allowed
        assert not extra, (
            f"the foreign adapter offers non-protocol members {sorted(extra)}, "
            f"so this file proves less than it claims")


class TestTheProtocolIsTheWholeContract:
    """Every neutral entry point, driven by stand-ins that are ONLY the protocol.

    `compare()` has the foreign-domain suite above. `compare_walks()` had
    nothing: it is in the same neutral band, takes the same `Capture`, and no
    test drove it with anything but the concrete BMC walk -- which carries
    members the protocol does not declare, so it could not have noticed needing
    them. A band is claimed neutral per module; it has to be checked per module.
    """

    def test_compare_reads_points_on_both_arguments(self, factory_line_registered):
        report = compare(_DS(REGISTER), _C(WALK))
        assert report.counts()["declared"] > 0, (
            "a declaration implementing exactly the protocol produced nothing")

    def test_compare_walks_reads_points_on_both_captures(self, factory_line_registered):
        report = compare_walks(_C(WALK), _C(WALK))
        assert report.before_count == report.after_count == len(_C(WALK).points)
        assert report.before_count > 0, "the fixture cannot refute anything empty"

    @pytest.mark.parametrize("member", ["__iter__", "__len__"])
    def test_the_stand_ins_really_lack_the_members_the_concrete_types_have(self, member):
        """The assertion the two tests above are only meaningful because of.

        If a later edit adds either member back to these stand-ins for
        convenience, both tests keep passing while testing nothing, and the
        requirement moves back somewhere no reader of the protocol can find it.
        """
        for cls in (_C, _DS):
            assert not hasattr(cls, member), (
                f"{cls.__name__} defines {member}, which `core/protocols.py` does "
                f"not declare -- so these tests no longer measure the protocol")

