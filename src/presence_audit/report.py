"""Render a diff two ways: for a machine, and for the person who owns the thing.

Acceptance criterion 4 of Stage 1 is that a before/after run produces a diff its
owner can read without explanation. That rules out a wall of JSON, and it rules
out a summary that hides which point is affected.

THE WORDS ARE THE DOMAIN'S, NOT THIS MODULE'S. Every noun a reader sees comes
from `vocabulary.noun()`, because a module that cannot name the domain cannot
name the things in it either. This file used to spell one domain's words into
every sentence it printed, so a factory line was told about its coverage, and
about its equipment, in nouns belonging to a different industry. A neutral core
that picks a vertical's vocabulary is not neutral -- it just has a favourite.

The human view leads with the counts, because the first question is always how
much of it is fine, and then lists findings grouped by kind with the most
actionable first. The machine view is stable, sorted, and carries the
attribution -- which config declared it, which URI reported it -- because a
finding without a source is a finding nobody can act on.
"""

from __future__ import annotations

import json
import textwrap
from typing import Any, Sequence

from .diff import DiffReport
from .regression import RegressionReport
from . import vocabulary as _vocabulary
from .protocols import Capture

__all__ = ["as_json", "as_text", "KIND_ORDER", "regression_as_text",
           "headlines", "change_headlines",
           "regression_as_json", "supplemental_as_text", "unattested_notice",
           "declaration_sources_as_text", "CHANGE_ORDER"]

# Most actionable first. `declared_absent` leads because it is the case that no
# other tool in the stack can produce at all.
KIND_ORDER = (
    "declared_absent",
    "declared_disabled",
    "declared_unreadable",
    "threshold_missing",
    "threshold_drift",
    "threshold_direction_conflict",
    "interface_divergence",
    "unknown_threshold_direction",
    "unclassified_threshold_level",
    "unreadable_threshold_value",
    "malformed_exposes",
    "duplicate_address",
    "config_unreadable",
    "walk_incomplete",
    "disabled_in_config_but_live",
    "undeclared_present",
    "matched_inexactly",
)

def headlines(singular: str | None = None) -> dict:
    """The kind headlines, in the domain's own noun.

    PUBLIC. It was `_HEADLINE`, a module constant, and a consumer imported the
    private name to assert that every kind it ships is ranked and titled. That
    is a real invariant and it was being checked from the wrong repository --
    the core owns both lists, so the core owns the question. `TestEveryKindHasA
    Headline` in this distribution now asks it, and the name is public so a
    consumer can ask it too without reaching past an underscore.

    A function rather than a module constant because the noun is not known at
    import time -- a vertical registers after this module is loaded, and a dict
    built at import would freeze whichever domain happened to be first.
    """
    if singular is None:
        singular = _vocabulary.noun()[0]
    return {
        "declared_absent": "Declared and not reported at all",
        "declared_disabled": "Present but switched off",
        "declared_unreadable": "Present and enabled, but not reading",
        "threshold_missing": f"Declared threshold absent on the live {singular}",
        "threshold_drift": "Threshold moved between declaration and machine",
        "threshold_direction_conflict":
            "The declaration contradicts itself about which side it guards",
        # Was `Present on one Redfish interface`. The kind is about two
        # interfaces disagreeing, which is a shape, not a protocol -- naming one
        # protocol here made every other domain's copy of this sentence false.
        "interface_divergence": "Present on one interface, absent from the other",
        "unknown_threshold_direction": "Threshold direction not recognised",
        "unclassified_threshold_level": "Threshold severity level not recognised",
        "unreadable_threshold_value": "Threshold value is not a number",
        "duplicate_address": f"More than one {singular} at one address",
        "malformed_exposes": "Malformed declaration record",
        "config_unreadable": "Declaration file could not be read",
        "walk_incomplete": "The capture did not finish",
        "disabled_in_config_but_live":
            "The declaration says disabled; the machine is reporting it",
        "undeclared_present": "Reported by the machine and declared nowhere",
        "matched_inexactly": "Paired by something other than an exact name",
    }


def as_json(report: DiffReport, *, target: str | None = None,
            walk: Capture | None = None, vocabulary=None) -> str:
    """The JSON report.
    `vocabulary` supplies the domain for this call only; omit it and the registered
    one is used. See `vocabulary.using`.
    """
    with _vocabulary.using(vocabulary):
        return _as_json(report, target=target, walk=walk)


def _as_json(report: DiffReport, *, target: str | None = None,
             walk: Capture | None = None) -> str:
    payload: dict[str, Any] = {
        "target": target,
        "walk_complete": report.walk_complete,
        "absence_findings_withheld": report.absence_withheld,
        "counts": report.counts(),
        "exit_code": report.exit_code,
        "findings": [
            {"kind": f.kind, "sensor": f.sensor, **_own_key(f.sensor),
             "detail": f.detail,
             "regression": f.is_regression,
             "declared_in": f.declared_in, "live_path": f.live_path}
            for f in _ordered(report)
        ],
    }
    if report.declaration_sources:
        # Emitted only when one was used, so a run against the manufacturer's files
        # alone carries no key claiming it had help. Both the prose line and the
        # fields it was built from: a machine consumer should not have to parse a
        # sentence, and a person reading raw JSON should not have to reassemble one.
        payload["declaration_sources"] = [
            _source_as_json(source) for source in report.declaration_sources]
    if walk is not None:
        # Sections the VERTICAL adds, under the names it gives them. Naming
        # `strict_fields` here is what made this builder know about Redfish.
        for key, build in _vocabulary.member("report_sections")().items():
            payload[key] = build(walk)
    return json.dumps(payload, indent=2, sort_keys=False)


def _own_key(value: Any) -> dict:
    """The domain's own key for a record, beside the published one, or nothing.

    A line audit's certificate came out reading "sensor": ST-01.die_temp_c,
    because every finding, decline and evidence record in this core is keyed on
    one domain's word. That word cannot simply move -- "cert-generator" reads it
    out of a finding and "bmc-sensor-audit" reads several more -- so the domain's
    key is ADDED and the published one stays. For the vertical the key was named
    after, the two are the same word and nothing is added at all.
    """
    key = _vocabulary.record_key()
    return {key: value} if key else {}


def _own_counts(before: int, after: int) -> dict:
    key = _vocabulary.record_key(plural=True)
    return {f"{key}_before": before, f"{key}_after": after} if key else {}


def _source_as_json(source: Any) -> dict:
    """One provenance entry, from whatever the protocol actually promises.

    `DeclarationSource.sources` promises `Sequence[object]` -- the files or
    authorities read -- and this function used to read ELEVEN members off each
    element, unguarded. `declaration_sources_as_text` next door had already been
    through exactly this: its docstring records the crash, for the first domain
    that answered with what the protocol allows. The lesson was applied in one
    function and not in its neighbour, and the two then disagreed about the type
    of one field.

    The direction of the disagreement is what made it worth fixing rather than
    documenting. The PERMISSIVE writer is the one a person reads; the strict one
    is the machine-readable half. So a run whose sources were plain strings
    printed a clean report and raised `AttributeError` on `--json` -- and an
    uncaught one exits 1, which in this package means findings. A run that could
    not complete reported a judgment nobody made.
    """
    described = getattr(source, "provenance_line", None)
    supplied = getattr(source, "supplied", None)
    return {"format": getattr(source, "kind", None),
            # A source that is just a path IS its path, which is what the text
            # report prints for one. Neither half invents a `kind` for it.
            "path": getattr(source, "path", None) if hasattr(source, "path") else str(source),
            "platform": getattr(source, "platform", None),
            "firmware": getattr(source, "firmware", None),
            "captured_at": getattr(source, "captured_at", None),
            "derived_from": getattr(source, "derived_from", None),
            "reviewed_by": getattr(source, "reviewed_by", None),
            "reviewed_on": getattr(source, "reviewed_on", None),
            "downgrade": getattr(source, "is_downgrade", None),
            "sensors_supplied": list(supplied) if supplied is not None else None,
            "provenance": described() if callable(described) else str(source)}


def declaration_sources_as_text(sources: Sequence[Any]) -> list[str]:
    """The provenance block, as report lines. Empty when nothing but the
    manufacturer's own files was read.

    Printed above the counts rather than below the findings. A reader decides how
    much to believe a number before they read it, not after.
    """
    if not sources:
        return []
    # `protocols.DeclarationSource.sources` promises `Sequence[object]` -- the
    # files or authorities read. It does NOT promise `provenance_line()`, and
    # calling it unconditionally made this function crash for the first domain
    # that answered with what the protocol allows: plain strings. A requirement
    # the protocol does not declare is one nobody outside can discover, and
    # nothing on either side could fail while one domain happened to satisfy it.
    lines = ["  Declared partly from additional sources:"]
    for source in sources:
        described = getattr(source, "provenance_line", None)
        lines.append(f"    {described() if callable(described) else source}")
    return lines + [""]


def _ordered(report: DiffReport) -> list:
    rank = {kind: i for i, kind in enumerate(KIND_ORDER)}
    return sorted(report.findings,
                  key=lambda f: (rank.get(f.kind, len(KIND_ORDER)), f.sensor))


#: The counts this module owns: the label it prints, the key, the field width.
#: ONE record, because the loop below prints from it AND `_CORE_COUNT_KEYS` is
#: derived from it. Written twice, the two would disagree and the disagreement
#: would show up as a vertical's count printed under a core label.
_CORE_COUNTS = (
    ("  declared          ", "declared", 5),
    ("  matched           ", "matched", 5),
    ("    reading         ", "reading", 5),
    ("    not reading     ", "present_not_reading", 5),
    ("  declared, absent  ", "declared_absent", 5),
    ("  present, undeclared ", "undeclared_present", 3),
)

#: Everything else in `counts` came from the vertical. `findings` and
#: `regressions` are the core's too; they are printed in the verdict line rather
#: than the summary block, which is why they are added here by hand.
_CORE_COUNT_KEYS = tuple(key for _, key, _ in _CORE_COUNTS) + ("findings", "regressions")


def as_text(report: DiffReport, *, target: str | None = None,
            vocabulary=None) -> str:
    """The human report.
    `vocabulary` supplies the domain for this call only; omit it and the registered
    one is used. See `vocabulary.using`.
    """
    with _vocabulary.using(vocabulary):
        return _as_text(report, target=target)


def _as_text(report: DiffReport, *, target: str | None = None) -> str:
    singular, _plural = _vocabulary.noun()
    kind_headlines = headlines(singular)
    counts = report.counts()
    lines: list[str] = []
    # SINGULAR, used attributively: the domain's own singular noun followed by
    # `coverage`, never its plural. Built from the plural at first, which read as
    # a typo and changed a line this distribution's own consumer has published
    # since its first release.
    title = f"{singular[:1].upper()}{singular[1:]} coverage"
    header = f"{title}: {target}" if target else title
    lines.append(header)
    lines.append("=" * len(header))
    lines.append("")
    lines.extend(declaration_sources_as_text(report.declaration_sources))
    for label, key, width in _CORE_COUNTS:
        lines.append(f"{label}{counts[key]:>{width}}")

    # Declarations set aside before expectation. Printed when NON-zero, because an
    # exclusion the reader cannot see is indistinguishable from a checker that
    # forgot to look.
    #
    # ITERATED, NOT NAMED. These keys belong to the vertical -- `count_keys` is a
    # vocabulary member and `diff.counts()` already builds them from it. This block
    # used to name two of them, `not_a_sensor` and `unrecognised_type`, which are
    # this distribution's predecessor's. A vertical whose keys were called anything
    # else had these counts present in the JSON and silently missing from the text,
    # which is the worse half: the reader sees a shorter list and no sign that one
    # exists. The labels are the domain's too, because the core cannot say what a
    # key it did not choose means.
    labels = _vocabulary.count_labels()
    kind_of = {key: kind for kind, key in _vocabulary.count_keys().items()}
    for key, value in counts.items():
        if key in _CORE_COUNT_KEYS or not value:
            continue
        label, note = labels.get(key, (key, ""))
        lines.append(f"  {label:<18}{value:>5}" + (f"   ({note})" if note else ""))
        for entry in report.not_sensor_kinds.get(kind_of.get(key, ""), [])[:10]:
            lines.append(f"      {entry.display_name}  [{entry.type}]")
    lines.append("")

    if not report.walk_complete:
        lines.append("  ** THE CAPTURE DID NOT FINISH. Absence findings are withheld,")
        lines.append(f"     because an unread subtree and a missing {singular} look the")
        lines.append("     same from here. Fix the transport and re-run. **")
        lines.append("")

    if not report.findings:
        lines.append(f"  No findings. Every declared {singular} is present and reading,")
        lines.append("  and nothing is reporting that the declaration does not declare.")
        return "\n".join(lines)

    grouped: dict[str, list] = {}
    for finding in _ordered(report):
        grouped.setdefault(finding.kind, []).append(finding)

    for kind, findings in grouped.items():
        title = kind_headlines.get(kind, kind)
        flag = " (regression)" if findings[0].is_regression else ""
        lines.append(f"{title} -- {len(findings)}{flag}")
        lines.append("-" * len(f"{title} -- {len(findings)}{flag}"))
        for finding in findings:
            lines.append(f"  {finding.sensor}")
            lines.append(f"      {finding.detail}")
            if finding.declared_in:
                lines.append(f"      declared in {finding.declared_in}")
        lines.append("")

    verdict = ("REGRESSIONS PRESENT" if report.regressions
               else "no regressions; findings above are informational")
    lines.append(f"{counts['regressions']} regression(s) of {counts['findings']} "
                 f"finding(s) -- {verdict}")
    return "\n".join(lines)


# Most actionable first, same principle as KIND_ORDER. A removal leads because it
# is the change a firmware release is most often shipped without noticing.
CHANGE_ORDER = (
    # First, because it EXPLAINS the removals below it. A reader who meets forty
    # removals and then the note has already started writing the incident.
    "aggregation_prefix_shift",
    "sensor_removed",
    "sensor_renamed",
    "reading_lost",
    "sensor_disabled",
    "threshold_removed",
    "threshold_moved",
    "units_changed",
    "tree_shape_gone",
    "field_drift",
    "walk_incomplete",
    "threshold_added",
    "sensor_enabled",
    "sensor_added",
    "aggregation_prefix_paired",
)

def change_headlines(singular: str | None = None) -> dict:
    """Change headlines, in the domain's own noun. Public for the same reason
    `headlines` is, and a function for the same reason: the noun is not known at
    import time.

    THE NOUN WAS COMPUTED AND DISCARDED. Every sentence below elided its subject
    -- *Reported before, not reported now* -- so the one value this function goes
    and fetches was never used, and the docstring's claim was true of `headlines`
    next door and of nothing here.

    The KEYS are a different question and are deliberately unchanged. Five of
    them carry one domain's noun, and they are format: "bmc-sensor-audit" and
    "cert-generator" read change kinds out of a published report. A kind renamed
    is a reader broken, so what moves is the prose a person reads.
    """
    if singular is None:
        singular = _vocabulary.noun()[0]
    return {
    "sensor_removed": f"A {singular} reported before and not now",
    "sensor_renamed": f"Same address, a different {singular} name",
    "reading_lost": "Still enabled, no longer reading",
    "sensor_disabled": f"A {singular} switched off since the earlier capture",
    # Was `the earlier firmware`. What carried the threshold is the earlier
    # CAPTURE -- true of a BMC, a PLC and anything else that gets captured twice.
    "threshold_removed": "Threshold the earlier capture carried is gone",
    "threshold_moved": "Threshold value changed",
    "units_changed": "Reading units changed",
    "tree_shape_gone": "An interface stopped being served",
    "field_drift": "New properties the published schema does not declare",
    "walk_incomplete": "A walk did not finish",
    "threshold_added": "A threshold appeared",
    "sensor_enabled": f"A {singular} switched on since the earlier walk",
    "sensor_added": f"A {singular} reported now and absent from the earlier capture",
    "aggregation_prefix_shift": "A subtree may have moved behind a new prefix",
    "aggregation_prefix_paired": "Paired across a declared aggregation prefix",
}


def _ordered_changes(report: RegressionReport) -> list:
    rank = {kind: i for i, kind in enumerate(CHANGE_ORDER)}
    return sorted(report.changes,
                  key=lambda c: (rank.get(c.kind, len(CHANGE_ORDER)), c.sensor))


def regression_as_json(report: RegressionReport, *, before: str, after: str,
                       vocabulary=None) -> str:
    """The JSON regression report.
    `vocabulary` supplies the domain for this call only; omit it and the registered
    one is used. See `vocabulary.using`.
    """
    with _vocabulary.using(vocabulary):
        return _regression_as_json(report, before=before, after=after)


def _regression_as_json(report: RegressionReport, *, before: str, after: str) -> str:
    payload: dict[str, Any] = {
        "before": before, "after": after,
        "walks_complete": report.complete,
        "absence_changes_withheld": report.absence_withheld,
        "fields_comparable": report.fields_comparable,
        "sensors_before": report.before_count,
        "sensors_after": report.after_count,
        **_own_counts(report.before_count, report.after_count),
        "paired": report.paired,
        "paired_through_declared_prefix": report.prefix_paired,
        "counts": report.counts(),
        "regressions": len(report.regressions),
        "changes": [
            {"kind": c.kind, "sensor": c.sensor, **_own_key(c.sensor),
             "detail": c.detail,
             "regression": c.is_regression,
             "before_path": c.before_path, "after_path": c.after_path}
            for c in _ordered_changes(report)
        ],
    }
    return json.dumps(payload, indent=2, sort_keys=False)


def regression_as_text(report: RegressionReport, *, before: str, after: str,
                       vocabulary=None) -> str:
    """The human regression report.
    `vocabulary` supplies the domain for this call only; omit it and the registered
    one is used. See `vocabulary.using`.
    """
    with _vocabulary.using(vocabulary):
        return _regression_as_text(report, before=before, after=after)


def _regression_as_text(report: RegressionReport, *, before: str, after: str) -> str:
    lines: list[str] = []
    singular, plural = _vocabulary.noun()
    titles = change_headlines(singular)
    header = "Capture regression"
    lines.append(header)
    lines.append("=" * len(header))
    lines.append("")
    lines.append(f"  before  {before}")
    lines.append(f"  after   {after}")
    lines.append("")
    lines.append(f"  {plural + ' before':<18}{report.before_count:>5}")
    lines.append(f"  {plural + ' after':<18}{report.after_count:>5}")
    lines.append(f"  paired            {report.paired:>5}")
    if report.prefix_paired:
        # Broken out rather than folded into `paired`, because these rest on a claim
        # the operator made and this tool did not check. A summary that hid them
        # would report a firmware as clean on the strength of a flag.
        lines.append(f"    of those, through a declared prefix map "
                     f"{report.prefix_paired:>3}")

    if not report.complete:
        lines.append("")
        lines.append(f"  ** A CAPTURE DID NOT FINISH. {plural.capitalize()} appearing and")
        lines.append("     disappearing are not reported, because an unread subtree and")
        lines.append(f"     a removed {singular} look the same from here. **")

    if not report.fields_comparable:
        # Said out loud rather than left as an empty section. One of these captures
        # carries no record of which properties each object had, so field drift was
        # not computed -- which is a different sentence from "nothing drifted".
        lines.append("")
        lines.append("  Field drift not computed: one of these captures was written")
        lines.append("  before walks recorded object properties. Re-capture both to")
        lines.append("  compare them.")
    lines.append("")

    if not report.changes:
        lines.append(f"  No changes. Every {singular} reported before is reported now,")
        lines.append("  under the same name, units, state and thresholds.")
        return "\n".join(lines)

    grouped: dict[str, list] = {}
    for change in _ordered_changes(report):
        grouped.setdefault(change.kind, []).append(change)

    for kind, changes in grouped.items():
        title = titles.get(kind, kind)
        flag = " (regression)" if changes[0].is_regression else ""
        lines.append(f"{title} -- {len(changes)}{flag}")
        lines.append("-" * len(f"{title} -- {len(changes)}{flag}"))
        for change in changes:
            lines.append(f"  {change.sensor}")
            lines.append(f"      {change.detail}")
        lines.append("")

    if report.absence_withheld and any(c.kind == "sensor_renamed" for c in report.changes):
        lines.append("  A rename is reported only where the address stayed the same.")
        lines.append(f"  A {singular} whose name AND address both changed appears above as")
        lines.append("  one removal and one addition -- but absence is withheld on this")
        lines.append("  run, so neither is shown.")
        lines.append("")
    elif any(c.kind in ("sensor_removed", "sensor_added") for c in report.changes):
        lines.append("  A rename is reported only where the address stayed the same.")
        lines.append(f"  A {singular} whose name AND address both changed appears above as")
        lines.append("  one removal and one addition; nothing in two captures says which")
        lines.append("  addition replaced which removal, so this does not guess.")
        lines.append("")

    verdict = ("REGRESSIONS PRESENT" if report.regressions
               else "no regressions; changes above are informational")
    lines.append(f"{len(report.regressions)} regression(s) of {len(report.changes)} "
                 f"change(s) -- {verdict}")
    return "\n".join(lines)


def unattested_notice(artifact: dict, path: str) -> str:
    """What to tell an operator who asked for evidence and got some of it, or none.

    Empty when there is nothing to say, so the caller prints nothing rather than a
    heading with no rows under it.

    The artifact already accounts for this honestly -- `unattested` is a required
    field and the shipped validator reads it -- but somebody who ran the command
    and watched the terminal would find out only by opening the file. A quiet gap
    is not a false claim, and it is still a gap nobody sees.
    """
    entries = artifact.get("unattested") or []
    if not entries:
        return ""
    lines = [f"{len(entries)} problem type(s) could not be attested, so {path} "
             f"carries findings without the measurements behind them:"]
    lines += [f"    {entry}" for entry in entries]
    return "\n".join(lines)


def supplemental_as_text(supplemental) -> str:
    """What the operator declared, and which numbers they left to the engine.

    **A margin nobody chose is the failure this file exists to prevent, one level
    down.** `basis` is required so a pairing cannot be a guess -- but a group with
    no `tolerance` and a flow with no `loss_margin` are still judged, against the
    engine's own defaults. From the report those are indistinguishable from numbers
    the operator picked, which is exactly the shape of claim the required `basis`
    was added to rule out.

    The default is not quoted here. It belongs to the engine, this build restating
    it is how two copies of one number come to disagree across an engine bump, and
    the sentence that matters -- *this file did not choose it* -- is true whatever
    the number is.
    """
    if supplemental is None or not supplemental:
        return ""
    lines = ["", "Operator declarations", "---------------------"]
    if supplemental.source:
        lines.append(f"  from {supplemental.source}")
    lines.append(f"  redundant groups {len(supplemental.redundant_groups):>4}")
    lines.append(f"  counters         {len(supplemental.counters):>4}")
    lines.append(f"  flows            {len(supplemental.flows):>4}")

    unstated_tolerance = [g for g in supplemental.redundant_groups
                          if g.tolerance is None and g.tolerance_absolute is None]
    unstated_margin = [f for f in supplemental.flows if f.loss_margin is None]
    if unstated_tolerance or unstated_margin:
        lines.append("")
        lines.append("  Judged against a number this file did not choose:")
        for group in unstated_tolerance:
            lines.append(f"      {group.primary} + {', '.join(group.peers)} "
                         f"-- no tolerance declared")
        for flow in unstated_margin:
            lines.append(f"      {flow.input} -> {', '.join(flow.outputs)} "
                         f"-- no loss_margin declared")
        lines.append("  The engine applies its own default for each. That is a")
        lines.append("  working check, not a specified one: declare the number with")
        lines.append("  its basis, or know that the threshold is the engine's.")
    return "\n".join(lines)


def detect_as_text(outcome, feed_result) -> str:
    """Render the Stage 2 verdict.

    Written so the three decline classes stay visibly different. Collapsing them into
    one list would hide the distinction the exit code is built on: a point whose value
    never arrived is a defect, a point without enough history yet is a fact, and a
    reason this build does not recognise is neither and must not be filed as either.
    """
    singular, _plural = _vocabulary.noun()
    lines = ["", "Liveness (Stage 2)", "------------------"]
    if outcome.schema_mismatch:
        # First, and not folded into the finding list. Everything below it was read
        # through a contract this build no longer recognises, so it is reported as
        # unreliable rather than presented as a verdict.
        lines.append("  ** ENVELOPE SCHEMA MISMATCH **")
        lines.append(f"     {outcome.schema_mismatch}")
        lines.append("")
    lines.append(f"  fed to the engine    {feed_result.fed:>5}")
    if feed_result.skipped_not_reading:
        lines.append(f"  not reading, skipped {feed_result.skipped_not_reading:>5}"
                     "   (Stage 1 owns absence; the engine is not asked)")
    if feed_result.skipped_not_modelled:
        lines.append(f"  not modelled         {feed_result.skipped_not_modelled:>5}"
                     "   (templated, not auditable, or no thresholds to bound against)")
    if outcome.checked:
        lines.append(f"  invariants checked   {outcome.checked.get('invariants', 0):>5}"
                     f"   over {outcome.checked.get('entities', 0)} entities")

    if getattr(feed_result, "peers_not_reading", None):
        # A declared pairing that was not judged, said out loud. Silence here would
        # be the worst available outcome: the operator declared a redundancy check,
        # the report shows no disagreement, and the reason is that nothing was
        # compared rather than that the readings matched.
        lines.append("")
        lines.append(f"  Redundancy not judged -- {len(feed_result.peers_not_reading)} "
                     "declared pair(s) whose peer is not reading:")
        for pair in feed_result.peers_not_reading[:5]:
            lines.append(f"      {pair}")
        if len(feed_result.peers_not_reading) > 5:
            lines.append(f"      ... and {len(feed_result.peers_not_reading) - 5} more")

    if getattr(feed_result, "couplings_not_fed", None):
        # Same rule as the pairing above, for the same reason: a declared coupling
        # that produced no edge contributes no fit and no refusal, and a report
        # that said nothing would read as a coupling the data agreed with.
        lines.append("")
        lines.append(f"  Couplings not fitted -- {len(feed_result.couplings_not_fed)} "
                     "declared coupling(s) whose endpoint did not reach the model:")
        for entry in feed_result.couplings_not_fed[:5]:
            lines.append(f"      {entry['from']} -> {entry['to']}: "
                         f"{', '.join(entry['missing'])}")
        if len(feed_result.couplings_not_fed) > 5:
            lines.append(f"      ... and {len(feed_result.couplings_not_fed) - 5} more")

    if getattr(feed_result, "coupled", None):
        # The grid travels with the count. A fitted gain is a statement about the
        # spacing it was fitted at, and a reader comparing one against a datasheet
        # has no way to check that without knowing which grid was used.
        lines.append("")
        lines.append(f"  Couplings fitted     {len(feed_result.coupled):>5}"
                     f"   on a {feed_result.interval_seconds:g} s grid")

    warming = feed_result.warming_up
    if warming:
        shown = sorted(warming.items())[:5]
        lines.append("")
        lines.append(f"  Liveness warming up -- {len(warming)} {singular}(s) below "
                     "the sample floor; stuck-at cannot be judged yet:")
        for name, count in shown:
            lines.append(f"      {name}: {count} sample(s)")
        if len(warming) > len(shown):
            lines.append(f"      ... and {len(warming) - len(shown)} more")

    if outcome.findings:
        lines.append("")
        lines.append(f"Findings -- {len(outcome.findings)}")
        for finding in outcome.findings:
            lines.append(f"  {finding}")

    if outcome.core_case_declines:
        lines.append("")
        lines.append(f"Could not evaluate, and should have been able to -- "
                     f"{len(outcome.core_case_declines)}")
        lines.append("  Stage 1 reported these as reading. Their values did not reach")
        lines.append("  the model, which means the name mapping is wrong.")
        for decline in outcome.core_case_declines:
            lines.append(f"    {decline}")

    if outcome.unmapped:
        lines.append("")
        lines.append(f"Readings the model never read -- {len(outcome.unmapped)}")
        for entry in outcome.unmapped:
            lines.append(f"    {entry}")

    if outcome.data_declines:
        lines.append("")
        lines.append(f"Not enough data yet -- {len(outcome.data_declines)} "
                     "(reported, not a failure)")
        for decline in outcome.data_declines[:5]:
            lines.append(f"    {decline}")
        if len(outcome.data_declines) > 5:
            lines.append(f"    ... and {len(outcome.data_declines) - 5} more")

    if outcome.inapplicable_declines:
        lines.append("")
        lines.append(f"Did not apply to this data -- "
                     f"{len(outcome.inapplicable_declines)} "
                     "(reported, not a failure)")
        # Its own heading rather than folded in with data sufficiency, because
        # *not enough data yet* would be the wrong sentence: there is plenty, and
        # the question is the thing that does not fit it. A declared power flow on
        # a supply reading zero watts in is the case this reaches.
        lines.append("  The check ran and the question was meaningless against the")
        lines.append("  values that arrived. Worth reading; not worth a red gate.")
        for decline in outcome.inapplicable_declines[:5]:
            lines.append(f"    {decline}")
        if len(outcome.inapplicable_declines) > 5:
            lines.append(f"    ... and {len(outcome.inapplicable_declines) - 5} more")

    if outcome.unclassified_declines:
        lines.append("")
        lines.append(f"Declines this build does not recognise -- "
                     f"{len(outcome.unclassified_declines)}")
        lines.append("  Reported rather than filed under the nearest known reason.")
        for decline in outcome.unclassified_declines[:5]:
            lines.append(f"    {decline}")

    if not (outcome.findings or outcome.core_case_declines or outcome.unmapped):
        lines.append("")
        if feed_result.fed:
            lines.append("  No liveness findings.")
        else:
            # Not the same sentence, and the difference is the whole point of the
            # section: nothing reached the engine, so this is an absence of evidence
            # and not evidence of health. Reported from outside as reading like a
            # verdict, which it did.
            lines.append("  Liveness not evaluated -- nothing was fed to the engine.")
    return "\n".join(lines)
