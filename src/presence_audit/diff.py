"""Compare what is declared against what is reported. This is the product.

Every other module exists to feed this one. The comparison answers a question no
tool watching live values asks, because none of them read the declaration:
**which declared points should be here and are not?**

Three design commitments, each of which costs code and each of which exists
because the cheap version produces a confidently wrong report:

**Matching is layered and always attributed.** A declared name matches a live one
exactly, or after normalisation, or -- for the roughly one name in eight that
carries a runtime template like `$bus` -- through a pattern derived from that
template. Every match records *how* it was made, so a fuzzy match is visible in
the output rather than indistinguishable from an exact one. A tool that silently
fuzzy-matches will eventually pair two unrelated points and report a clean
capture.

**An incomplete capture is not an empty one.** If any fetch failed, absence
findings are withheld entirely rather than reported against a partial picture.
A transport failure that renders as a page of missing points is worse than no
report, because someone will act on it.

**Presence is three-valued, not two.** Present and reading, present but disabled
or unreadable, and entirely absent are three different conditions with three
different responses. Collapsing the middle one into either neighbour loses the
case this tool was built for -- the disabled point that nothing displays.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterable

from .protocols import DeclarationSource, DeclaredPoint
from . import vocabulary as _vocabulary
from .protocols import Capture, CapturedPoint

__all__ = ["Finding", "Match", "DiffReport", "compare", "normalise_name",
           "expects_reading"]

# Findings that mean something got worse. The CLI exits non-zero on these so a
# firmware-upgrade gate can fail a release candidate in CI.
REGRESSION_KINDS = frozenset({
    "declared_absent", "declared_unreadable", "declared_disabled",
    "threshold_missing", "threshold_drift", "threshold_direction_conflict",
    "interface_divergence",
})

_SEPARATORS = re.compile(r"[\s_\-]+")

# The template vocabulary lives in one place -- see entity_manager.TEMPLATE_VARS.
# Defining it twice is how the two copies come to disagree, and the direction
# they disagree in here is the dangerous one: a matcher that recognises fewer
# variables than the reader silently wildcards the difference.


@dataclass(frozen=True)
class Finding:
    kind: str
    sensor: str
    detail: str
    declared_in: str | None = None
    live_path: str | None = None

    @property
    def is_regression(self) -> bool:
        return self.kind in REGRESSION_KINDS

    def __str__(self) -> str:
        return f"[{self.kind}] {self.sensor} -- {self.detail}"


@dataclass(frozen=True)
class Match:
    declared: DeclaredPoint
    live: CapturedPoint
    how: str          # "exact" | "normalised" | "template"


@dataclass
class DiffReport:
    findings: list[Finding] = field(default_factory=list)
    matches: list[Match] = field(default_factory=list)
    unmatched_declared: list[DeclaredPoint] = field(default_factory=list)
    unmatched_live: list[CapturedPoint] = field(default_factory=list)
    walk_complete: bool = True
    absence_withheld: bool = False
    # Declarations excluded from expectation because their Type does not produce a
    # reading, keyed by kind. Reported, never silently dropped -- an exclusion
    # nobody can see is indistinguishable from a checker that forgot to look.
    not_sensor_kinds: dict[str, list] = field(default_factory=dict)
    #: The vocabulary this report was BUILT with, when the caller supplied one.
    #:
    #: A report is read after the call that made it returns, and `counts()`
    #: asks the vocabulary what its kinds are called. Without this the argument
    #: to `compare()` would build a report nobody could read: the comparison
    #: would use the domain you passed and the counts would come from whatever
    #: happened to be registered, or raise if nothing was. Found by writing the
    #: two-domain test, not by reasoning about it.
    #:
    #: `None` means the caller supplied nothing, and `using(None)` is a no-op,
    #: so a report built the old way still reads the registry exactly as before.
    vocabulary: Any = None
    # DeclarationSource sources other than entity-manager that this report was judged
    # against. Carried ON THE REPORT rather than passed to each renderer, so a new
    # output format cannot be added without the provenance coming with it. A reader
    # who cannot tell a manufacturer's declaration from a snapshot of one machine is
    # being handed the second while reading it as the first.
    declaration_sources: list = field(default_factory=list)

    @property
    def regressions(self) -> list[Finding]:
        return [f for f in self.findings if f.is_regression]

    @property
    def exit_code(self) -> int:
        """Non-zero when something got worse, so CI can gate on it."""
        return 1 if self.regressions else 0

    def counts(self) -> dict[str, int]:
        with _vocabulary.using(self.vocabulary):
            return self._counts()

    def _counts(self) -> dict[str, int]:
        reading = sum(1 for m in self.matches if m.live.is_reading)
        return {
            "declared": len(self.matches) + len(self.unmatched_declared),
            "matched": len(self.matches),
            "reading": reading,
            "present_not_reading": len(self.matches) - reading,
            "declared_absent": len(self.unmatched_declared),
            "undeclared_present": len(self.unmatched_live),
            # The kinds a vertical reports separately, under the names IT gives
            # them. Naming them here is what made this module know about BMCs.
            **{key: len(self.not_sensor_kinds.get(kind, []))
               for kind, key in _vocabulary.current().count_keys.items()},
            "findings": len(self.findings),
            "regressions": len(self.regressions),
        }


def normalise_name(name: str) -> str:
    """The matcher's notion of one name being the same name as another.

    Public because precedence between declaration sources has to use exactly this
    function. Two sources declaring one name with a separator the other spells
    differently are declaring one point, and a merge that kept both would expect it
    twice and report one of them permanently absent -- a false regression created
    by the merge itself.
    """
    return _SEPARATORS.sub("_", name.strip().lower())


def _index_live(walk: Capture) -> tuple[dict[str, CapturedPoint], dict[str, CapturedPoint]]:
    exact: dict[str, CapturedPoint] = {}
    normalised: dict[str, CapturedPoint] = {}
    for sensor in walk.points:
        exact.setdefault(sensor.name, sensor)
        normalised.setdefault(normalise_name(sensor.name), sensor)
    return exact, normalised


def _pair(declaration: Iterable[DeclaredPoint], walk: Capture) -> tuple[list[Match], list[DeclaredPoint]]:
    exact, normalised = _index_live(walk)
    claimed: set[str] = set()
    matches: list[Match] = []
    unmatched: list[DeclaredPoint] = []

    # Exact, then normalised, then template -- most confident first, so a
    # template pattern can never steal a point an exact name would have claimed.
    pending: list[DeclaredPoint] = []
    for declared in declaration:
        live = exact.get(declared.name)
        if live is not None and live.path not in claimed:
            claimed.add(live.path)
            matches.append(Match(declared, live, "exact"))
        else:
            pending.append(declared)

    still_pending: list[DeclaredPoint] = []
    for declared in pending:
        live = normalised.get(normalise_name(declared.name))
        if live is not None and live.path not in claimed:
            claimed.add(live.path)
            matches.append(Match(declared, live, "normalised"))
        else:
            still_pending.append(declared)

    for declared in still_pending:
        pattern = _vocabulary.current().template_pattern(declared.name)
        hit = None
        if pattern is not None:
            for sensor in walk.points:
                if sensor.path not in claimed and pattern.match(sensor.name):
                    hit = sensor
                    break
        if hit is not None:
            claimed.add(hit.path)
            matches.append(Match(declared, hit, "template"))
        else:
            unmatched.append(declared)

    return matches, unmatched


def _compare_thresholds(match: Match, findings: list[Finding]) -> None:
    """Does the live point carry the thresholds the declaration asked for?

    Drift here is its own finding: an update that keeps a point and quietly widens
    its limits is invisible to presence checking and to ordinary alerting, because
    nothing ever breaches a threshold that moved.
    """
    declared, live = match.declared, match.live
    for threshold in declared.thresholds:
        if threshold.bound is None or threshold.level is None:
            continue
        slot = (threshold.bound, threshold.level)
        actual = live.thresholds.get(slot)
        if actual is None:
            findings.append(Finding(
                "threshold_missing", declared.display_name,
                f"config declares a {threshold.bound} {threshold.level} threshold "
                f"at {threshold.value:g}; the captured point carries none",
                declared.source, live.path))
        elif not _close(actual, threshold.value):
            findings.append(Finding(
                "threshold_drift", declared.display_name,
                f"{threshold.bound} {threshold.level} declared {threshold.value:g}, "
                f"live {actual:g}",
                declared.source, live.path))


def _close(a: float, b: float, *, rel: float = 1e-6) -> bool:
    return abs(a - b) <= rel * max(1.0, abs(a), abs(b))


def expects_reading(sensor: DeclaredPoint) -> bool:
    """Whether absence of this declaration should count as a regression.

    **The type filter is a fact about ONE declaration format, not about
    declarations in general.** Some formats declare things that never produce a
    reading -- controls, fittings, identifiers -- in exactly the same shape as the
    points that do, so a type this build cannot place is reported and never
    asserted about. The vertical is what knows which is which.

    A declaration source that only ever records things that were READING carries no
    such population, and applying the filter to one is not caution -- it is a silent
    hole. Every entry would classify `UNRECOGNISED` for want of a type the format
    does not carry, so a point that stopped reporting would be counted, printed, and
    never once fail a gate. That is the exact vacuous pass this tool exists to
    catch.

    So the source says. `expects_reading is None` means decide from `type`, which is
    the case for a format that carries one, and the default.
    """
    if sensor.expects_reading is not None:
        return sensor.expects_reading
    return _vocabulary.current().is_expected_live(sensor.type)


def _classify_excluded(declared: list) -> dict:
    """Group the declarations that will not be expected live, by why.

    Returned rather than discarded so the report can say how many entries were set
    aside and on what grounds. A filter whose output nobody can inspect is a filter
    nobody can challenge.
    """
    excluded: dict = {}
    for sensor in declared:
        if expects_reading(sensor):
            continue
        kind = _vocabulary.current().classify(sensor.type)
        excluded.setdefault(kind, []).append(sensor)
    return excluded


def compare(declaration: DeclarationSource, walk: Capture, *,
            include_disabled_in_config: bool = False,
            vocabulary=None) -> DiffReport:
    """Diff a declaration against a walk.

    `include_disabled_in_config` controls whether points the declaration itself
    marks disabled are expected to be present. They are excluded by default:
    reporting a deliberately disabled point as missing on a healthy capture is
    precisely the every-run-red noise that teaches people to stop reading the
    report. How many carry that marker is a fact about one corpus, and it lives
    with the vertical that measured it.

    `vocabulary` supplies the domain for THIS CALL only. Omit it and the
    registered one is used, exactly as before. Pass one and nothing is
    registered, which is what lets two domains run in one process -- and in
    two threads at once, because the lookup is context-local rather than
    module-level.
    """
    with _vocabulary.using(vocabulary):
        return _compare(declaration, walk,
                        include_disabled_in_config=include_disabled_in_config)


def _compare(declaration: DeclarationSource, walk: Capture, *,
             include_disabled_in_config: bool = False) -> DiffReport:
    report = DiffReport(walk_complete=walk.complete,
                        declaration_sources=list(declaration.sources),
                        vocabulary=_vocabulary._ACTIVE.get())
    findings: list[Finding] = []

    # EVERY declared point is paired, including the ones the declaration marks
    # disabled. Excluding them from pairing was the first cut and it was wrong in
    # a way only a run against real data showed: a declaration that disables
    # several points the capture nonetheless reports produced an
    # `undeclared_present` row for each, on a completely healthy capture. Noise on
    # every run is how a report teaches its reader to stop opening it.
    #
    # So they are matched, and only their EXPECTATIONS differ: a disabled point
    # that is absent is not a finding, and one that is live is a finding of its
    # own -- the declaration and the capture disagree about whether that thing is
    # switched on.
    # `.points` on both, never iteration of the object itself. The protocol is
    # the whole contract a second bridge gets: anything this module needs that
    # the protocol does not declare is a requirement nobody outside can discover.
    all_matches, unmatched_declared = _pair(list(declaration.points), walk)
    matched_paths = {m.live.path for m in all_matches}
    report.matches = all_matches
    report.unmatched_live = [s for s in walk.points if s.path not in matched_paths]

    if not include_disabled_in_config:
        unmatched_declared = [s for s in unmatched_declared if not s.disabled]

    # The same move again, for a bigger population and a worse symptom. A
    # declaration entry is not necessarily a point that reads: a format may declare
    # controls, fittings and identifiers the same way, and none of them can ever
    # appear in a capture of live values. Expecting them made a sixth of one real
    # corpus permanently absent, which is a red gate on a healthy capture -- and on
    # most of them. The corpus and its numbers belong to the vertical that has
    # them; what belongs here is that the source is ASKED rather than assumed.
    #
    # Three-valued, because a closed split would force a Type this build has never
    # seen into whichever bucket the default happens to be. An unrecognised type is
    # counted and REPORTED, never asserted about: claiming a regression for
    # something we cannot classify is the exact false positive being removed here.
    report.not_sensor_kinds = _classify_excluded(unmatched_declared)
    unmatched_declared = [s for s in unmatched_declared if expects_reading(s)]

    # Anything wrong with the declaration itself travels into the report. A
    # defect in the expectation source is a finding no reading-watcher can see.
    for anomaly in declaration.anomalies:
        findings.append(Finding(
            anomaly.kind, anomaly.sensor or "(config)", anomaly.detail, anomaly.source))
    # Findings only this domain can produce from its own capture. The diff does
    # not know what they are; it knows they belong beside its own.
    findings.extend(_vocabulary.current().capture_findings(walk))
    for source, reason in declaration.unreadable:
        findings.append(Finding(
            "config_unreadable", "(config)",
            f"{reason} -- every point this file declares is unverifiable, not absent",
            source))

    for match in all_matches:
        live = match.live
        name = match.declared.display_name
        if match.declared.disabled:
            # The config says this hardware is switched off. If the machine is
            # reporting it anyway, the two disagree, and the config is the thing
            # every downstream generator trusts.
            if live.is_reading:
                findings.append(Finding(
                    "disabled_in_config_but_live", name,
                    f"the configuration marks this Status: disabled, and the "
                    f"machine is reporting {live.reading:g}"
                    f"{' ' + live.units if live.units else ''}",
                    match.declared.source, live.path))
            continue
        if not live.is_enabled:
            findings.append(Finding(
                "declared_disabled", name,
                f"declared and present, but the capture reports "
                f"State={live.state!r}. A disabled {_vocabulary.noun()[0]} is "
                f"typically invisible wherever this domain normally shows them",
                match.declared.source, live.path))
        elif live.reading is None:
            findings.append(Finding(
                "declared_unreadable", name,
                "declared and present and enabled, but carries no reading",
                match.declared.source, live.path))
        else:
            _compare_thresholds(match, findings)
        if match.how != "exact":
            findings.append(Finding(
                "matched_inexactly", name,
                f"matched to captured point {live.name!r} by {match.how}, not by an "
                f"exact name; confirm the pairing before trusting its findings",
                match.declared.source, live.path))

    if walk.complete:
        report.unmatched_declared = unmatched_declared
        for declared in unmatched_declared:
            findings.append(Finding(
                "declared_absent", declared.display_name,
                f"declared by {declared.type or 'an entry'} in the declaration "
                f"and not present in the capture at all",
                declared.source))
        for live in report.unmatched_live:
            findings.append(Finding(
                "undeclared_present", live.name,
                f"present in the capture at {live.path} and declared nowhere "
                f"in the declaration",
                None, live.path))
    else:
        # Withheld on purpose. See the module docstring.
        report.absence_withheld = True
        report.unmatched_declared = []
        findings.append(Finding(
            "walk_incomplete", "(walk)",
            f"{len(walk.errors)} fetch(es) failed, so absence cannot be "
            f"distinguished from an unread subtree. Absence findings are "
            f"withheld: first error was {walk.errors[0][0]} ({walk.errors[0][1]})"))

    report.findings = findings
    return report
