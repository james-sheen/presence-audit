"""What a vertical must supply, and the registry it supplies it through.

The neutral machinery classifies declared points and reports how many fell into
each class. Both of those need a vocabulary, and the vocabulary is the domain:
one bridge's kinds split its readings from everything else, another's are assets
and fixtures. So it is supplied, not imported.

**The count keys are part of this, and that is not obvious.** The report a
consumer reads carries per-kind counts under key names taken from the domain. If
the vertical supplied only the classifier, the neutral code would still have to
name the keys, and naming them is the leak. So a vocabulary supplies the names of
its own kinds AND the names they are reported under.

**An empty registry is an error, never a default.** A registry that is quiet when
nothing registered produces a run that classifies nothing and reports cleanly,
which is worse than a crash: everything imports, nothing works, and the first
sign is a wrong answer in somebody's report.
"""

from __future__ import annotations

import contextlib
import contextvars
import os
from typing import Mapping, Optional, Protocol, Sequence

from . import _renames

from .protocols import PROTOCOL_VERSION


class PluginError(RuntimeError):
    """A vertical was named and could not be loaded, or registered nothing."""


class VocabularyNotRegistered(RuntimeError):
    """Asked for the vocabulary before any vertical supplied one."""


class Vocabulary(Protocol):
    """The domain half of a presence audit."""

    @property
    def kinds(self) -> Sequence[str]:
        """Every class a declared point can fall into. Must be non-empty."""

    @property
    def count_keys(self) -> Mapping[str, str]:
        """Kind -> the key it is reported under, for the kinds worth reporting.

        A partial mapping is allowed: a kind absent from it is classified and not
        counted separately. That is how the shipped report keeps exactly the keys
        it has always had.
        """

    def classify(self, declared_type: Optional[str]) -> str:
        """Which kind a declared point's type falls into. Must return a member
        of `kinds` -- a classifier that can answer outside its own vocabulary is
        not one."""

    def is_auditable(self, kind: str) -> bool:
        """Whether points of this kind are the ones the audit is about.

        Asked directly rather than inferred from `count_keys`. In this
        distribution's own vertical the countable kinds happen to be exactly the
        non-auditable ones, so inferring it would agree here and quietly disagree
        for a vertical that reports a kind it also audits -- a second path giving
        the same answer, where only the reason is wrong.
        """

    def is_expected_live(self, declared_type: Optional[str]) -> bool:
        """Whether a point of this type should be producing a value at all."""

    def template_pattern(self, declared_name: str) -> object:
        """A matcher for a declared name carrying substitutions, or None.

        None means *this name is not a template, or its variables are not ones
        this domain knows* -- and an unrecognised variable must never be
        wildcarded into a match-anything pattern.
        """

    def same_point(self, old: object, new: object) -> bool:
        """Whether two captures at one address describe the same point.

        A domain with no evidence to the contrary says yes: refusing a pairing
        needs a reason, and *no reason found* is not one.
        """

    def captures_comparable(self, before: object, after: object) -> bool:
        """Whether two captures support this domain's extra per-point
        comparisons. False means those comparisons are SKIPPED, never that they
        ran and found nothing."""

    def point_changes(self, old: object, new: object, *,
                      comparable: bool = False) -> Sequence[object]:
        """What changed about one point, in terms only this domain has."""

    def capture_changes(self, before: object, after: object) -> Sequence[object]:
        """What changed about the capture as a whole."""

    def capture_findings(self, capture: object,
                         *, declaration: object = None) -> Sequence[object]:
        """Findings only this domain can produce from its own capture.

        The diff pairs a declaration against a capture and reports what it
        finds. A domain may see more in its own capture than that pairing can --
        two interfaces disagreeing about one point, say -- and those findings
        belong beside the diff's own rather than in a separate report nobody
        reads. A domain with nothing extra to say returns an empty sequence.

        `declaration` is what the row was DECLARED as, and it is passed only to
        a vocabulary whose signature accepts it. Without it a finding can only
        be derived from the captured row, and a row that looks wrong on its own
        terms may be a declared kind this audit does not judge -- a meeting
        reported as an unowned item of work, because nothing reachable from the
        capture said it was a meeting. Taking it is OPTIONAL: every vertical
        published before this takes the capture alone and keeps working.
        """

    def peer_groups(self, declaration: object) -> Sequence[Mapping[str, object]]:
        """Which declared points this domain considers redundant readings of one
        thing, as candidate groups.

        The generator pairs points it is told are peers; it does not know how a
        domain decides that. One groups by physical part and channel, another
        might group by a name prefix, and neither belongs in the generator.

        A domain with no notion of redundancy returns an empty sequence.
        """

    @property
    def noun(self) -> Sequence[str]:
        """What this domain calls one of the things audited: (singular, plural).

        Used verbatim in the human report, which otherwise has to pick a word --
        and the word it picked was this distribution's predecessor's. A factory
        line was told about its coverage in a word from a different domain, in
        every heading and every sentence of its own report.

        OPTIONAL, and that is a decision rather than laziness: this member
        arrived after two verticals were published, so requiring it would make a
        lexical improvement a breaking change. A vertical that does not supply
        one gets `DEFAULT_NOUN`, the word this protocol uses about itself
        throughout -- neutral and true, rather than another domain's.
        """

    def count_labels(self) -> Mapping[str, Sequence[str]]:
        """Report key -> (label, note) for the counts `count_keys` contributes.

        The note is the parenthetical after the number, or the empty string. Both
        are this domain's words: the core cannot say what its keys mean.

        OPTIONAL. A key with no label is printed under the key itself, which is
        ugly and visible -- the failure being fixed is the invisible one. The
        core used to name two keys from this distribution's predecessor
        directly, so a vertical whose keys were called anything else had those
        counts silently missing from the text report while the JSON carried
        them.
        """

    def regression_kinds(self) -> Sequence[str]:
        """Which of this domain's OWN finding and change kinds are regressions.

        `capture_findings` and `point_changes` let a domain produce kinds only it
        can see, and the exit code scored them against a frozen set of the core's
        own -- so a vertical could put a real defect in the report and still
        compose a clean verdict. The one fully worked vertical happened to emit a
        kind the core already scored, which is why it took a second one to see.

        OPTIONAL, and UNIONED with the core's set rather than replacing it: a
        vocabulary may say which of its kinds count, and may not decide that a
        point declared and absent does not.
        """

    def report_sections(self) -> Mapping[str, object]:
        """Extra top-level report keys this domain contributes, name -> builder.

        Each builder takes the capture and returns a JSON-serialisable payload.
        A vertical with nothing to add returns an empty mapping, and the report
        simply has no such key -- rather than a key holding an empty object,
        which reads as *checked and found nothing*.
        """


_REGISTERED: Optional[Vocabulary] = None

#: The vocabulary for the CURRENT CALL, when a caller supplied one explicitly.
#:
#: A `ContextVar` rather than a module global, and rather than a parameter
#: threaded through every private helper. The registry is read from twenty-six
#: places across six modules, most of them inside functions no caller names, so
#: a parameter would have changed every internal signature to give the public
#: entry points one keyword. What actually needed to change is the SCOPE of the
#: ambient lookup: from the process to the call.
#:
#: The consequence is the property the design could not have before. Two
#: vocabularies can run in one process at the same time, in different threads or
#: different tasks, each seeing its own -- because a context is per-thread and
#: per-task, and this variable is looked up in it rather than in the module.
_ACTIVE: contextvars.ContextVar = contextvars.ContextVar(
    "presence_audit_vocabulary", default=None)


@contextlib.contextmanager
def using(supplied: Optional[Vocabulary]):
    """Make `supplied` the vocabulary for the duration of this block.

    `None` is a no-op rather than an error, so a public entry point can pass
    its optional `vocabulary=` argument straight through without branching --
    and a caller who supplies nothing gets exactly the behaviour they had.

    Nothing is registered. The registry is not touched, not read and not
    restored, because it was never written: a caller who was relying on their
    own registration still has it when this returns, including when the block
    raises.
    """
    if supplied is None:
        yield None
        return
    token = _ACTIVE.set(supplied)
    try:
        yield supplied
    finally:
        _ACTIVE.reset(token)


#: The name of the flag that turns the registry fallback OFF.
REQUIRE_EXPLICIT = "PRESENCE_AUDIT_REQUIRE_EXPLICIT_VOCABULARY"


def _explicit_required() -> bool:
    """Whether this process refuses the registry fallback.

    **Read at call time, not at import.** An import-time read cannot be turned
    on by a test without reloading the module, and a setting that is awkward to
    exercise is one nobody exercises.

    OFF by default and it stays off: two published verticals register and pass
    nothing, and the whole point of `vocabulary=` was to add a way, not to
    remove one. Turning it on is how a consumer proves they have finished
    migrating -- their suite goes red on the calls that still rely on ambient
    state, which is the only way to find them.
    """
    return os.environ.get(REQUIRE_EXPLICIT, "") not in ("", "0")


@contextlib.contextmanager
def requiring_explicit(required: bool = True):
    """Turn the fallback off for a block. For a suite proving it has migrated."""
    previous = os.environ.get(REQUIRE_EXPLICIT)
    os.environ[REQUIRE_EXPLICIT] = "1" if required else "0"
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop(REQUIRE_EXPLICIT, None)
        else:
            os.environ[REQUIRE_EXPLICIT] = previous


def _supplied() -> Optional[Vocabulary]:
    """The vocabulary in force: the call's, or the registry's, or none.

    Every reader goes through this. Written once because the alternative is
    four copies of the same precedence rule, and a precedence rule written four
    times is one that will disagree with itself.
    """
    active = _ACTIVE.get()
    if active is not None:
        return active
    return None if _explicit_required() else _REGISTERED


def register(vocabulary: Vocabulary) -> None:
    """Supply the vocabulary. Called by a vertical, never by the core.

    A vertical MAY declare `protocol_version`, the revision of the contract it
    was written against. Declaring it is optional and absence is admitted --
    the two verticals published before the constant existed declare nothing,
    and refusing them would make the guarantee itself a breaking change. What
    is refused is a vertical that declares a revision this core does not serve,
    because that vertical is telling you it expects something else and the
    failure it is heading for is a wrong answer rather than an error.
    """
    if hasattr(vocabulary, "protocol_version"):
        declared = vocabulary.protocol_version
        if declared != PROTOCOL_VERSION:
            raise PluginError(
                f"the vocabulary was written against protocol version "
                f"{declared!r} and this core serves {PROTOCOL_VERSION}. Both "
                f"numbers are named because either one can be the one that "
                f"moved, and running anyway would answer domain questions "
                f"against a contract neither side agreed to")
    if not vocabulary.kinds:
        raise PluginError(
            "the vocabulary offered no kinds; a classifier with an empty range "
            "cannot answer, and registering it would make that look like a pass")
    unknown = set(vocabulary.count_keys) - set(vocabulary.kinds)
    if unknown:
        raise PluginError(
            f"the vocabulary reports kinds it cannot produce: {sorted(unknown)}. "
            "A count key with no kind behind it is a column that is always zero")
    global _REGISTERED
    _REGISTERED = vocabulary


def current() -> Vocabulary:
    """The vocabulary in force, or a refusal that says how to supply one."""
    supplied = _supplied()
    if supplied is None:
        # Both names are READ from the module that defines them, never spelled
        # here. Spelled, this message named the variable this package used
        # before it was extracted -- a name that does nothing now -- in the one
        # string a user is guaranteed to see, since it is what a run with no
        # vertical prints. The rename moved the constant and could not reach a
        # copy of its own value. The dead name is not written out here either:
        # a package whose whole claim is that it names no domain should not
        # ship one in a comment about having stopped.
        # Imported inside the function: `plugins` imports this module, so the
        # dependency only runs one way at import time.
        from .plugins import ENTRY_POINT_GROUP, ENVIRONMENT_VARIABLE
        raise VocabularyNotRegistered(
            f"no vertical has registered a vocabulary. One is supplied by an "
            f"entry point in the group '{ENTRY_POINT_GROUP}', by the "
            f"{ENVIRONMENT_VARIABLE} environment variable, or by --plugin. "
            f"Running without one would classify nothing and report cleanly. "
            f"A caller who has one in hand can pass it as `vocabulary=` "
            f"instead, and register nothing" +
            (f". {REQUIRE_EXPLICIT} is set in this process, so a registered "
             f"vocabulary would not have been used either -- the argument is "
             f"the only way in" if _explicit_required() else ""))
    return supplied


def member(name: str):
    """A required member of the vocabulary in force, or a refusal naming it.

    `current().<member>` raises a bare `AttributeError` from whichever call site
    reached it first, so a vertical missing one learns an attribute name and
    nothing about where the contract is written down or how to see the rest of
    what it owes. Eleven call sites across four modules read a required member,
    and every one of them reads it through here.

    The three OPTIONAL members keep the accessors below, which fall back rather
    than refuse. That asymmetry is the point and is now stated: a member the
    protocol requires is a contract, and a member it offers is a courtesy.
    """
    supplied = current()
    try:
        return getattr(supplied, name)
    except AttributeError:
        raise PluginError(
            f"the vocabulary in force declares no {name!r}, which the protocol "
            f"lists as required. `python -m presence_audit.conformance <spec>` "
            f"names every member it is missing in one pass, which is the "
            f"answer an author needs -- this refusal can only name the one "
            f"that was reached first") from None


#: The noun the core falls back to. It is the word this module's own protocol
#: uses in every docstring above, so a vertical that supplies nothing gets prose
#: that is neutral and true rather than another domain's.
DEFAULT_NOUN = ("point", "points")


def noun() -> tuple:
    """The registered domain's (singular, plural), or `DEFAULT_NOUN`.

    Read through `getattr` because the member is optional: a vertical published
    before it existed answers nothing here and must keep working. A malformed
    answer falls back too -- a report is not the place to raise.
    """
    supplied = getattr(_supplied(), "noun", None)
    try:
        singular, plural = supplied
    except (TypeError, ValueError):
        return DEFAULT_NOUN
    if not isinstance(singular, str) or not isinstance(plural, str):
        return DEFAULT_NOUN
    return (singular, plural)


def count_keys() -> Mapping[str, str]:
    """The registered domain's kind -> report-key mapping, or empty.

    Defensive for the same reason as the others: the text report reads this and
    must not begin raising in a caller that renders without registering.
    """
    supplied = getattr(_supplied(), "count_keys", None)
    return supplied if isinstance(supplied, Mapping) else {}


def count_labels() -> Mapping[str, tuple]:
    """Report key -> (label, note) for this domain's extra counts, or empty."""
    supplied = getattr(_supplied(), "count_labels", None)
    if supplied is None:
        return {}
    try:
        given = supplied()
    except Exception:
        return {}
    if not isinstance(given, Mapping):
        return {}
    out = {}
    for key, value in given.items():
        if isinstance(value, str):
            out[str(key)] = (value, "")
            continue
        try:
            label, note = value
        except (TypeError, ValueError):
            continue
        out[str(key)] = (str(label), str(note))
    return out


def regression_kinds() -> frozenset:
    """The domain's own regression kinds, or empty.

    Defensive for the reason the other optional readers are: this is read while
    scoring a report, and a vertical published before the member existed answers
    nothing here and must keep composing a verdict.
    """
    supplied = getattr(_supplied(), "regression_kinds", None)
    if supplied is None:
        return frozenset()
    try:
        given = supplied() if callable(supplied) else supplied
        if isinstance(given, (str, bytes)):
            # A BARE STRING IS NOT A SEQUENCE OF KINDS, though Python will
            # happily iterate one into single characters -- so a vocabulary
            # naming its one regression kind without a comma would score every
            # letter of it and none of its actual kinds, quietly and forever.
            return frozenset()
        return frozenset(str(kind) for kind in given)
    except Exception:                                       # noqa: BLE001
        return frozenset()


def record_key(plural: bool = False) -> Optional[str]:
    """The domain's own word for a record key, or None when it is the default.

    None means *nothing to add*: the artifact keys were named after one domain
    before this package was domain-free, and that vertical's own noun is the
    word they were named after -- so for it this answers None and not one byte
    of its output moves.

    A key rather than a rename. "cert-generator" reads the published one out of
    a finding and "bmc-sensor-audit" reads several more, so renaming would break
    readers that are right to read what was published. Emitting the domain's key
    BESIDE the published one lets a line audit key on its own word while
    everything that already works keeps working -- the only shape that can land
    without a compatibility break.
    """
    word = noun()[1 if plural else 0]
    published = (_renames.PUBLISHED_SUBJECT, _renames.PUBLISHED_SUBJECTS)[1 if plural else 0]
    return None if word == published else word


def own_key(plural: bool = False) -> Optional[str]:
    """The domain's own word as a record key in format 2, or None for the core's.

    Format 2 keys every record on `point` first, so this is the word ADDED beside
    it -- `None` when the domain's word is `point` itself, which is what a
    vertical supplying no noun gets. Spaces become underscores: a key is read by
    a program, and a key with a space in it is one every reader has to quote.
    """
    word = noun()[1 if plural else 0].strip().lower().replace(" ", "_")
    neutral = DEFAULT_NOUN[1 if plural else 0]
    return None if word in ("", neutral) else word


def spelled_kind(kind: str) -> str:
    """A change kind naming a point, spelled in the domain's own word.

    `point_removed` for a domain with no noun of its own, and the domain's word
    in its place otherwise -- which gives the first vertical back exactly the
    kinds it has always emitted. Any kind that names no point is returned as it
    is. Read by the format-2 writers; see `_renames` for the window.
    """
    from .regression import neutral_kind

    neutral = neutral_kind(kind)
    if not neutral.startswith("point_"):
        return kind
    word = own_key() or "point"
    return word + neutral[len("point"):]


def registered() -> bool:
    """Whether anything has registered.

    The REGISTRY, deliberately, not `_supplied()`. A caller asking this is
    deciding what to say about the process, and a vocabulary passed to one call
    is not a registration -- answering `True` inside a `using` block would tell
    them something that stops being true when the block ends.
    """
    return _REGISTERED is not None


def in_force() -> bool:
    """Whether anything would answer right now, registered or supplied."""
    return _supplied() is not None


def reset() -> None:
    """Drop the registration. For tests that need an empty registry."""
    global _REGISTERED
    _REGISTERED = None
