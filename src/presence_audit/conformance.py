"""A conformance kit a vertical can run against its own vocabulary.

**What it proves.** That the core reaches for nothing the protocol does not
declare, and that a vocabulary reaches for nothing the protocol does not declare
on the objects it is handed. Both halves are driven by stand-ins that implement
`protocols` and NOTHING ELSE -- no `__iter__`, no `__len__`, no convenience a
concrete type happens to have. A fixture that adds a member to get past a call
site proves the core can serve a domain that already knows what the document does
not say, which is not the claim.

That is not hypothetical. The core called `.points` on a capture while the
protocol did not declare it, and every test passed: the one vertical in the tree
happened to have the member. It was found by a SECOND real vertical, months
later. The stand-ins below are what makes it findable on the first run.

**What it cannot prove, and this is the important paragraph.** It cannot tell you
the protocol is SUFFICIENT. A stand-in is written from the protocol, so it can
only ever discover that something reached past the document -- never that the
document is missing something a real domain needs. Those are two different
failures:

* **The core exceeds the protocol.** Caught here. The `.points` case.
* **The protocol is insufficient.** NOT caught here, and no fixture written from
  the protocol ever will be, because it is written to the same document that is
  wrong. Only a real domain, with real data, finds this -- and finding it is the
  falsifiable question a third vertical exists to answer.

A green run means *nothing has reached past the contract*. It does not mean the
contract is enough for you. If you are the third vertical, the interesting result
is the one this kit cannot give you.

**Running it.**

    python -m presence_audit.conformance your_package.vertical:register

The argument is the same spec `--plugin` and `PRESENCE_AUDIT_PLUGINS` take, and
it is resolved by the same loader, so a spec that works here works there. With no
argument the core half runs alone.
"""

from __future__ import annotations

import sys
from typing import Any, List

from . import diff, protocols, regression, vocabulary
from .plugins import PluginError, load_spec

__all__ = ["CapturedPoint", "Capture", "DeclaredPoint", "DeclarationSource",
           "ReferenceVocabulary", "SAMPLE_CAPTURE", "SAMPLE_DECLARATION",
           "check_the_core", "check_a_vocabulary", "main"]


# --------------------------------------------------------------------------
# Stand-ins. Exactly the protocol, deliberately.
# --------------------------------------------------------------------------

class CapturedPoint:
    """`protocols.CapturedPoint` and nothing else."""

    def __init__(self, node, entries):
        self._node, self._entries = node, entries

    name = property(lambda s: s._node)
    path = property(lambda s: s._node)

    @property
    def reading(self):
        good = [e.get("v") for e in self._entries if e.get("q") == "good"]
        return good[-1] if good else None

    is_reading = property(lambda s: any(e.get("q") == "good" for e in s._entries))
    state = property(lambda s: s._entries[-1].get("q") if s._entries else None)
    thresholds = property(lambda s: {})
    units = property(lambda s: None)
    is_enabled = property(lambda s: True)


class Capture:
    """`protocols.Capture` and nothing else.

    No `__iter__` and no `__len__`, on purpose. Adding either would move a
    requirement somewhere no reader of the protocol can find it.
    """

    def __init__(self, walk):
        index, stamps = {}, []
        for sample in walk.get("samples") or []:
            stamps.append(sample.get("t"))
            for node, reading in (sample.get("nodes") or {}).items():
                index.setdefault(node, []).append(reading)
        self._index, self._stamps = index, [s for s in stamps if s]

    points = property(lambda s: [CapturedPoint(n, e) for n, e in s._index.items()])
    captured_at = property(lambda s: s._stamps[-1] if s._stamps else None)
    complete = property(lambda s: bool(s._index))
    errors = property(lambda s: ())


class DeclaredPoint:
    """`protocols.DeclaredPoint` and nothing else."""

    def __init__(self, asset, tag, spec):
        self._asset, self._tag, self._spec = asset, tag, spec

    name = property(lambda s: s._spec["node"])
    type = property(lambda s: s._spec.get("class"))
    display_name = property(lambda s: f"{s._asset['id']}.{s._tag}")
    source = property(lambda s: "register.yaml")
    expects_reading = property(lambda s: None)
    disabled = property(lambda s: bool(s._spec.get("excluded")))
    thresholds = property(lambda s: ())
    is_templated = property(lambda s: False)


class DeclarationSource:
    """`protocols.DeclarationSource` and nothing else."""

    def __init__(self, register):
        self._register = register

    @property
    def points(self):
        return [DeclaredPoint(a, t, spec)
                for a in self._register.get("assets") or []
                for t, spec in (a.get("tags") or {}).items()]

    sources = property(lambda s: ("register.yaml",))
    anomalies = property(lambda s: ())
    unreadable = property(lambda s: ())


REFERENCE_KINDS = ("point", "not_a_point", "unrecognised")


class ReferenceVocabulary:
    """A vocabulary belonging to no shipped vertical, for the core half.

    Its `protocol_version` is DECLARED, so registering it runs the version gate
    rather than taking the absent path around it. A kit that skips the check it
    demonstrates proves the check exists and nothing else.
    """

    protocol_version = protocols.PROTOCOL_VERSION
    kinds = property(lambda s: REFERENCE_KINDS)
    count_keys = property(lambda s: {"not_a_point": "not_a_point"})

    def classify(s, declared_type):
        return "point" if declared_type in ("speed", "distance") else "unrecognised"

    def is_auditable(s, kind): return kind == "point"
    def is_expected_live(s, declared_type): return s.classify(declared_type) == "point"
    def template_pattern(s, name): return None
    def same_point(s, old, new): return True
    def point_changes(s, old, new, *, comparable=False): return []
    def capture_changes(s, before, after): return []
    def captures_comparable(s, before, after): return False
    def capture_findings(s, capture): return []
    def peer_groups(s, declaration): return []
    def report_sections(s): return {}


#: Three states in one fixture, deliberately: one reading, one present and not
#: reading, one absent, plus one the declaration excludes and one the capture
#: carries undeclared. A fixture that cannot produce all three cannot tell a
#: working core from one that answers the same way every time.
SAMPLE_CAPTURE = {"samples": [
    {"t": "2026-09-07T00:00:00Z", "nodes": {
        "line1.spindle": {"v": 1490.0, "q": "good"},
        "line1.gap":     {"v": None,   "q": "bad"},
        "line1.rogue":   {"v": 3.0,    "q": "good"}}},
    {"t": "2026-09-07T00:00:05Z", "nodes": {
        "line1.spindle": {"v": 1495.0, "q": "good"},
        "line1.gap":     {"v": None,   "q": "bad"},
        "line1.rogue":   {"v": 3.1,    "q": "good"}}}]}

SAMPLE_DECLARATION = {"assets": [{"id": "line1", "type": "mill", "tags": {
    "spindle": {"node": "line1.spindle", "class": "speed"},
    "gap":     {"node": "line1.gap",     "class": "distance"},
    "absent":  {"node": "line1.absent",  "class": "speed"},
    "retired": {"node": "line1.retired", "class": "speed", "excluded": True}}}]}


#: The three states, as `DiffReport.counts()` spells them. Named here because
#: this kit's whole subject is that the answer is three-valued -- but checked
#: for PRESENCE before value, so a rename in the core reports as a rename
#: rather than as a state that came back empty.
THREE_STATES = ("reading", "present_not_reading", "declared_absent")


# --------------------------------------------------------------------------
# The two halves.
# --------------------------------------------------------------------------

def check_the_core() -> List[str]:
    """Drive the core with protocol-only objects. Problems, or an empty list."""
    problems: List[str] = []
    previous = vocabulary._REGISTERED
    vocabulary.reset()
    try:
        vocabulary.register(ReferenceVocabulary())
        declaration = DeclarationSource(SAMPLE_DECLARATION)
        capture = Capture(SAMPLE_CAPTURE)
        try:
            report = diff.compare(declaration, capture)
        except AttributeError as reached:
            return [f"compare() reached for a member the protocol does not "
                    f"declare: {reached}"]
        counts = report.counts()
        if counts.get("declared", 0) <= 0:
            problems.append("compare() found nothing to declare; the kit's own "
                            "fixture cannot refute anything")

        # MEMBERSHIP FIRST, then the value. Written the other way round, this
        # read a key that does not exist, got the default, and reported *the
        # absent state came back empty* -- which is a claim about the core and
        # was really a claim about the spelling in this file. A missing key and
        # an empty state are different facts and must not share a message.
        missing = [key for key in THREE_STATES if key not in counts]
        if missing:
            problems.append(f"the report carries no {missing} key, so the "
                            f"three-valued answer cannot be read at all")
        empty = [key for key in THREE_STATES
                 if key in counts and not counts[key]]
        if empty:
            problems.append(f"the three-valued answer did not discriminate: "
                            f"{empty} came back empty, so a core that answered "
                            f"the same way every time would pass")
        try:
            regression.compare_walks(capture, Capture(SAMPLE_CAPTURE))
        except AttributeError as reached:
            problems.append(f"compare_walks() reached for a member the protocol "
                            f"does not declare: {reached}")
    finally:
        vocabulary.reset()
        if previous is not None:
            vocabulary.register(previous)
    return problems


#: The members a vocabulary is handed OBJECTS through, rather than strings.
#:
#: **Reaching past the protocol on these is NOT a defect, and the first version
#: of this kit called it one.** `Vocabulary.same_point` and its neighbours are
#: typed `(old: object, new: object)`; the core passes through whatever the
#: caller gave `compare()`, which for a vertical is its OWN capture type. A
#: vocabulary is entitled to expect it. Run against a published vertical, the
#: first version reported five confident failures on code that is correct --
#: precise, high, and about the wrong subject.
#:
#: What the reach DOES tell an author is that their vocabulary cannot be driven
#: by a foreign capture. That is worth knowing and is reported as an
#: observation, not a problem, and it does not change the exit code.
_OBJECT_MEMBERS = ("same_point", "captures_comparable", "point_changes",
                   "capture_changes", "capture_findings", "peer_groups")

#: Members taking a string or nothing. These CAN be judged: a classifier that
#: answers outside its own range is wrong whoever calls it.
_STRING_MEMBERS = ("classify", "is_auditable", "is_expected_live",
                   "template_pattern")


def check_a_vocabulary(supplied: Any):
    """Exercise a vocabulary with what the kit can honestly hand it.

    Returns `(problems, observations)`. A problem is a claim about the
    vocabulary being WRONG; an observation is a fact about it that its author
    may not know and that no rule forbids.
    """
    problems: List[str] = []
    notes: List[str] = []
    declaration = DeclarationSource(SAMPLE_DECLARATION)
    capture = Capture(SAMPLE_CAPTURE)
    points = capture.points
    if len(points) < 2:
        return (["the kit's own capture carries fewer than two points, so the "
                 "pairwise members below were never really called"], notes)
    one, two = points[0], points[1]

    calls = {
        "same_point": lambda v: v.same_point(one, two),
        "captures_comparable": lambda v: v.captures_comparable(capture, capture),
        "point_changes": lambda v: v.point_changes(one, two),
        "capture_changes": lambda v: v.capture_changes(capture, capture),
        "capture_findings": lambda v: v.capture_findings(capture),
        "peer_groups": lambda v: v.peer_groups(declaration),
    }
    for member in _OBJECT_MEMBERS + _STRING_MEMBERS:
        if not hasattr(supplied, member):
            problems.append(f"declares no {member!r}, which the protocol lists "
                            f"as required")

    for member in _OBJECT_MEMBERS:
        if not hasattr(supplied, member):
            continue
        try:
            calls[member](supplied)
        except AttributeError as reached:
            notes.append(f"{member}() expects a capture type of its own: "
                         f"{reached}. Permitted -- it means this vocabulary "
                         f"cannot be driven by a foreign capture, which is "
                         f"worth knowing and is not a fault")
        except Exception as error:                          # noqa: BLE001
            notes.append(f"{member}() raised {type(error).__name__} on the "
                         f"kit's objects: {error}")

    kinds = tuple(getattr(supplied, "kinds", ()) or ())
    if not kinds:
        problems.append("offers no kinds, so `classify` has no range to answer in")
    elif hasattr(supplied, "classify"):
        for declared_type in (None, "", "speed", "a-type-no-domain-has"):
            try:
                answer = supplied.classify(declared_type)
            except Exception as error:                      # noqa: BLE001
                problems.append(f"classify({declared_type!r}) raised "
                                f"{type(error).__name__}: {error}")
                continue
            if answer not in kinds:
                problems.append(f"classify({declared_type!r}) answered "
                                f"{answer!r}, outside its own kinds "
                                f"{list(kinds)} -- a classifier that can answer "
                                f"outside its range is not one")

    if hasattr(supplied, "is_auditable"):
        auditable = []
        for kind in kinds:
            try:
                if supplied.is_auditable(kind):
                    auditable.append(kind)
            except Exception as error:                      # noqa: BLE001
                problems.append(f"is_auditable({kind!r}) raised "
                                f"{type(error).__name__}: {error}")
        if kinds and not auditable:
            problems.append(f"audits none of its own kinds {list(kinds)}, so "
                            f"every declared point is set aside and the audit "
                            f"reports cleanly over nothing")

    declared = getattr(supplied, "protocol_version", None)
    if declared is not None and declared != protocols.PROTOCOL_VERSION:
        problems.append(f"declares protocol version {declared!r}; this core "
                        f"serves {protocols.PROTOCOL_VERSION}")
    return problems, notes


def main(argv=None) -> int:
    """`python -m presence_audit.conformance [spec]`. 0 clean, 1 problems, 2 could not run."""
    argv = list(sys.argv[1:] if argv is None else argv)
    problems = check_the_core()
    for problem in problems:
        print(f"core: {problem}")
    if not problems:
        print("core: reached for nothing the protocol does not declare")

    if argv:
        spec = argv[0]
        previous = vocabulary._REGISTERED
        vocabulary.reset()
        try:
            load_spec(spec, origin="conformance")
            supplied = vocabulary.current()
        except PluginError as refused:
            print(f"vertical: could not run: {refused}")
            return 2
        except vocabulary.VocabularyNotRegistered:
            print(f"vertical: could not run: {spec} registered no vocabulary")
            return 2
        else:
            found, notes = check_a_vocabulary(supplied)
            for note in notes:
                print(f"vertical: note: {note}")
            for problem in found:
                print(f"vertical: {problem}")
            if not found:
                print("vertical: answers the protocol correctly")
            problems += found
        finally:
            vocabulary.reset()
            if previous is not None:
                vocabulary.register(previous)
    else:
        print("vertical: not checked; pass a spec to check one")

    print("\nA green run means nothing reached past the contract. It does not "
          "mean the contract is enough for your domain -- see this module's "
          "docstring for the failure it cannot see.")
    return 1 if problems else 0


if __name__ == "__main__":                                  # pragma: no cover
    sys.exit(main())
