"""A per-run record of what was checked, what was declined, and on what evidence.

The engine answers `check()` with findings and declines. That is enough for an exit
code and not enough for an audit, because it drops the numbers: a finding says
*reading exceeds critical threshold* and never says the reading was 51.2 against a
declared 50.0. `attest()` returns those, and this assembles them into an artifact a
run can be judged from afterwards.

**Three things it records, and the second and third are the point.**

*What was checked* is the easy half. *What was declined* is the half a compliance
reader actually needs: an axiom that could not be evaluated is not an axiom that
passed, and an artifact listing only findings reads as a clean bill of health for
every question nobody managed to ask. *What this record does not establish* is the
third, and it is carried verbatim from the engine rather than written here.

## The engine's own boundary, quoted rather than paraphrased

Every evidence entry `attest()` returns carries a `boundary` string. On 0.1.7 it
reads *engine-side evidence only; production attestation records are v0.2*. That is
the engine declining to be called an attestation service, and it belongs in the
artifact for the same reason a decline does. Paraphrasing it would make this file
the author of a disclaimer the engine wrote.

## Sequencing, which is a real contract and not an implementation detail

`attest()` requires `check()` to have run on the same session. Called first it
returns an envelope with `source: unavailable` and the reason *nothing checked yet:
call check first* -- an honest refusal, and one that would be easy to mistake for
*this run found nothing to attest*. So this module never calls `attest` speculatively:
it takes the problem types out of an envelope `check()` already produced.
"""

from __future__ import annotations

from typing import Any

from . import exit_contract
from . import vocabulary as _vocabulary

__all__ = ["build_attestation", "validate_attestation", "ATTESTATION_FORMAT",
           "ATTESTATION_FORMAT_1", "ATTESTATION_FORMAT_2",
           "ACCEPTED_ATTESTATION_FORMATS"]

#: What `build_attestation` writes: each record keyed on `point` and on the
#: vertical's own word. `ATTESTATION_FORMAT` names the format this build
#: WRITES, so a reader comparing an artifact against it keeps comparing against
#: the right one; the explicit id is kept for code written while two were.
ATTESTATION_FORMAT_2 = "presence-audit/attestation/2"
ATTESTATION_FORMAT = ATTESTATION_FORMAT_2

#: Written until 0.2.0 and still READ: an artifact already on disk is exactly
#: the document it was when it was written.
ATTESTATION_FORMAT_1 = "presence-audit/attestation/1"

#: Formats this build ACCEPTS on read, newest first.
#:
#: The SHAPE did not change when this module moved distributions -- only the
#: name in front of it did. An artifact already written carries the old name and
#: is still exactly this document, so refusing it would be inventing an
#: incompatibility to match a package rename. Reading both and emitting one is
#: what makes the move invisible to anything holding an older file.
#:
#: The old name is not deprecated here and carries no removal date. It stops
#: being accepted when somebody can show nothing writes it any more, which is a
#: measurement rather than a schedule.
ACCEPTED_ATTESTATION_FORMATS = (
    ATTESTATION_FORMAT_2,
    ATTESTATION_FORMAT_1,
    "bmc-sensor-audit/attestation/1",
)


def validate_attestation(artifact: Any) -> list[str]:
    """Everything wrong with this artifact, or an empty list.

    **This lived inline in a CI workflow, and that was the defect rather than an
    inconvenience.** Checking logic that exists only inside a `run:` block cannot be
    called by the person who receives the artifact, cannot be tested, and cannot be
    versioned alongside the thing it checks. A compliance reader was expected to
    trust a shape they had no way to verify.

    So the rule it enforces ships, the canary calls it, and a recipient can run the
    same check over an artifact somebody sent them. One validator, two callers.

    Returns problems rather than raising, so a caller reports all of them at once
    instead of fixing them one run at a time.

    **Deliberately does not import the engine.** An artifact is JSON, and validating
    one is a Stage 1 operation: a recipient auditing a file should not have to
    install a detection engine to read it.
    """
    problems: list[str] = []
    if not isinstance(artifact, dict):
        return [f"the artifact is {type(artifact).__name__}, not an object"]

    declared = artifact.get("format")
    if declared not in ACCEPTED_ATTESTATION_FORMATS:
        problems.append(f"format is {declared!r}, this build reads "
                        f"{' or '.join(repr(f) for f in ACCEPTED_ATTESTATION_FORMATS)}")

    shape: list[str] = []
    for key in ("findings", "not_checked", "evidence"):
        if not isinstance(artifact.get(key), list):
            shape.append(f"{key!r} is missing or is not a list")
    if shape:
        # Everything below indexes into these lists, so reporting a type error and
        # then every consequence of it names one fault four times.
        #
        # Tracked separately from `problems` on purpose: returning early whenever
        # ANY problem existed meant a wrong `format` -- the first check -- masked
        # every other one, so a file could be fixed and re-run repeatedly, learning
        # one fault at a time.
        return problems + shape

    # The verdict block, when there is one. ABSENCE IS NOT A PROBLEM: every
    # artifact written before the slot existed has none, and refusing those
    # would make recording a conclusion a breaking change. What is checked is
    # that a block which IS present is expressible and self-consistent.
    if "verdict" in artifact:
        problems.extend(_verdict_problems(artifact["verdict"]))

    if len(artifact["evidence"]) != len(artifact["findings"]):
        problems.append(
            f"{len(artifact['findings'])} finding(s) but "
            f"{len(artifact['evidence'])} evidence entr(ies); a finding without its "
            f"measurement is the thing this artifact exists to carry")

    for index, entry in enumerate(artifact["evidence"]):
        if not isinstance(entry, dict) or not isinstance(
                entry.get("measurement"), dict) or not entry["measurement"]:
            problems.append(f"evidence[{index}] carries no measurement")

    engine = artifact.get("engine")
    if not isinstance(engine, dict):
        problems.append("the 'engine' block is missing")
    else:
        # **Required only when there IS evidence to bound.** The boundary is the
        # engine's statement about what its evidence establishes, and it is read off
        # the evidence entries themselves -- so a clean board, which produces no
        # findings and therefore no evidence, has no boundary to carry and is not
        # defective for lacking one.
        #
        # Requiring it unconditionally made this validator reject a healthy machine,
        # which is the exact inversion the rest of this file is written to prevent.
        # Found by the clean-board test rather than by reading.
        if artifact["evidence"] and not engine.get("boundary"):
            problems.append(
                "the engine's own boundary statement is absent while evidence is "
                "present; the artifact must not claim more than the engine says it "
                "can support")
        if engine.get("schema_version") is None:
            problems.append(
                "engine.schema_version is absent; without it the artifact does not "
                "record which envelope contract the judgment was made under")

    for key in ("unattested", "unread_feeds"):
        if not isinstance(artifact.get(key), list):
            problems.append(
                f"{key!r} is missing or is not a list; it is how this artifact "
                f"accounts for what was NOT part of the judgment, and an absent "
                f"list reads as 'nothing was left out'")

    return problems


def _verdict_problems(block: Any) -> list[str]:
    """Whether a verdict block is expressible in the core's vocabulary."""
    if not isinstance(block, dict):
        return [f"'verdict' is {type(block).__name__}, not an object"]
    found: list[str] = []
    code = block.get("exit_code")
    if code not in exit_contract.MEANING:
        found.append(f"verdict.exit_code is {code!r}; the contract has "
                     f"{sorted(exit_contract.MEANING)}")
    elif "meaning" in block and block["meaning"] != exit_contract.MEANING[code]:
        found.append(f"verdict.meaning is {block['meaning']!r} beside exit_code "
                     f"{code}, which means "
                     f"{exit_contract.MEANING[code]!r}")
    if not block.get("scored_by"):
        found.append("verdict names no 'scored_by'; the code is the producer's "
                     "claim and not this core's, and an unattributed one reads "
                     "as though the artifact had been scored by its format")
    return found


def build_attestation(session: Any, envelope: dict, describe: dict,
                      manifest: Any, *, target: str,
                      attest_fn: Any, verdict: Any = None,
                      spelled: bool = True) -> dict:
    """Assemble the artifact from an envelope `check()` has already produced.

    `attest_fn` is passed in rather than imported, because this module must not
    import `arbiter_engine` at module scope -- Stage 1 runs on a bench with nothing
    provisioned, and an import here would make the whole CLI need the extra.

    `verdict` is the producer's own conclusion, and it is OPTIONAL because this
    core cannot compute one. `exit_contract` holds the compose rule and nothing
    else; floors belong to each vertical, which is exactly why the artifact could
    not say what the run concluded -- it recorded everything the run SAW and
    nothing it decided, and a recipient had to re-derive the conclusion from two
    lists without knowing whether a floor table had been applied.

    What the core owns is the VOCABULARY a conclusion is expressed in, so what it
    supplies is a slot with an agreed spelling. Pass `verdict_block(code,
    scored_by=...)`. A vertical that needed this before invented a key name, and
    the next one would have invented a different one: two artifacts both carrying
    a verdict that no single reader could read.

    It writes format 2 (`ATTESTATION_FORMAT`), keyed as a format-2 report is;
    `spelled=False` keys records on `point` alone.
    """
    problem_types = []
    for finding in envelope.get("findings") or []:
        problem_type = finding.get("problem_type")
        if problem_type and problem_type not in problem_types:
            problem_types.append(problem_type)

    evidence: list[dict] = []
    unattested: list[str] = []
    for problem_type in problem_types:
        attested = attest_fn(session, problem_type).to_dict()
        meta = attested.get("meta") or {}
        if meta.get("source") == "unavailable":
            # Recorded, not dropped. A problem type the engine declined to attest is
            # a gap in the artifact, and an artifact that quietly omits it claims
            # completeness it does not have.
            unattested.append(f"{problem_type}: {meta.get('reason', 'unavailable')}")
            continue
        for entry in attested.get("evidence") or []:
            evidence.append(_render(entry, manifest, spelled))

    artifact = {
        "format": ATTESTATION_FORMAT,
        "target": target,
        "engine": {
            "schema_version": (envelope.get("meta") or {}).get("schema_version"),
            # Verbatim from the engine. See the module docstring: this is the engine
            # declining to be called an attestation service, and it is not ours to
            # soften.
            "boundary": _boundary(evidence),
        },
        "checked": envelope.get("checked") or {},
        "findings": [_finding(f, manifest, spelled)
                     for f in envelope.get("findings") or []],
        # The half a compliance reader needs. An axiom that could not be evaluated is
        # not an axiom that passed.
        "not_checked": [_decline(d, manifest, spelled)
                        for d in (envelope.get("not_checked")
                                  or envelope.get("declines") or [])],
        "evidence": evidence,
        "unattested": unattested,
        "unread_feeds": [
            f"{u.get('entity_id', '?')}.{u.get('property', '?')}"
            for u in (describe.get("unconsumed_observations")
                      or (describe.get("model") or {}).get(
                          "unconsumed_observations") or [])],
    }
    if verdict is not None:
        artifact["verdict"] = dict(verdict)
    return artifact


def verdict_block(exit_code: int, *, scored_by: str) -> dict:
    """The producer's conclusion, in the core's vocabulary.

    `scored_by` names who reached it and is required rather than defaulted: this
    is a CLAIM by the producer, not a fact the core checked. The core asserts
    only that the number is one of the three and that the word beside it is the
    one that number means -- never that the number is right, which it has no
    floor table to decide.
    """
    code, raw = exit_contract.normalise(exit_code)
    block = {"exit_code": code, "meaning": exit_contract.MEANING[code],
             "scored_by": str(scored_by)}
    if raw != code:
        # `normalise` hands back the raw value beside the mapped one precisely so
        # a composer cannot clamp and forget. A leg that exited 137 is the most
        # informative thing that run produced, and dropping it here would undo
        # that in the one artifact a recipient keeps.
        block["raw_exit_code"] = raw
    return block


def _subject_keys(value: Any, spelled: bool) -> dict:
    """The keys a record names its point under -- as a format-2 report does."""
    keys: dict = {"point": value}
    own = _vocabulary.own_key() if spelled else None
    if own and own != "point":
        keys[own] = value
    return keys


def _boundary(evidence: list[dict]) -> str | None:
    for entry in evidence:
        if entry.get("boundary"):
            return entry["boundary"]
    return None


def _declared_name(entity_id: str, manifest: Any) -> str:
    """The name the declaration gave, not the sanitised entity type.

    An artifact naming `MB_U73_THERM_LOCAL_2` is one nobody can act on six months
    later, which is the whole failure mode a per-run record exists to avoid.
    """
    for point in getattr(manifest, "points", ()):
        if point.entity_type == entity_id:
            return point.declared_name
    return entity_id


def _statement(record: dict, manifest: Any) -> str | None:
    """The domain's sentence for this record, or the engine's own word for it.

    `manifest.translate_finding` used to be read as a bare attribute, so it was
    REQUIRED -- by a writer whose `manifest` parameter is untyped, for a member
    the Vocabulary protocol does not declare and no markdown file in this
    repository mentions. A vertical passed the conformance kit green and then
    raised `AttributeError` from the middle of an artifact it was halfway
    through writing.

    Degrading to the problem type is better than raising for the reason the
    reporter gave: an attestation that cannot be written is worse than one whose
    statements read like the engine, and a vertical writing its first `attest`
    has no way to find out which member it owes.
    """
    translate = getattr(manifest, "translate_finding", None)
    if callable(translate):
        return translate(record)
    return record.get("problem_type")


def _finding(finding: dict, manifest: Any, spelled: bool = True) -> dict:
    name = _declared_name(finding.get("entity_id", "?"), manifest)
    return {**_subject_keys(name, spelled),
            # THE ENGINE'S SENSE OF THE WORD, which is the envelope this record
            # is built from. It held `entity_id` -- the manifest's sense, where
            # `entity_type` is the sanitised identifier -- so the artifact
            # carried an identifier under a name that says it is a class, one key
            # away from the field `_declared_name` exists to keep out of the artifact.
            # Empty on findings from an engine that does not classify them, which
            # is honest; the published name key carries it either way.
            "entity_type": finding.get("entity_type"),
            "axiom": finding.get("axiom"),
            "severity": finding.get("severity"),
            "problem_type": finding.get("problem_type"),
            "statement": _statement(finding, manifest)}


#: Decline keys the projection names itself. Everything else is measurement.
_DECLINE_NAMED = ("entity_id", "entity_type", "indicator", "axiom", "reason", "detail")


def _decline(decline: dict, manifest: Any, spelled: bool = True) -> dict:
    """One declined evaluation, with the fields that make two of them two.

    This kept FOUR keys of the thirteen a decline carries, and `indicator` was
    among the nine it dropped -- so two indicators on one entity, both declining
    for the same reason, became two identical rows, and a validated artifact
    could not say which two things declined or that they were two rather than
    one counted twice.

    The rest go under `measurement` rather than into the top level, so the row
    stays readable and a key the engine adds later arrives without a change
    here. They are not incidental: `insufficient_samples` means the series will
    fill OR that the collector's cadence can never reach the floor however long
    it runs, and the engine says which in a field this used to drop -- a floor
    of nothing against a floor of one, indistinguishable in the artifact.
    """
    measurement = {key: value for key, value in decline.items()
                   if key not in _DECLINE_NAMED}
    name = _declared_name(decline.get("entity_id", "?"), manifest)
    row = {**_subject_keys(name, spelled),
           "entity_type": decline.get("entity_type"),
           "indicator": decline.get("indicator"),
           "axiom": decline.get("axiom"),
           "reason": decline.get("reason"),
           "detail": decline.get("detail")}
    if measurement:
        row["measurement"] = measurement
    return row


def _render(entry: dict, manifest: Any, spelled: bool = True) -> dict:
    inner = entry.get("evidence") or {}
    name = _declared_name(entry.get("entity_id", "?"), manifest)
    return {**_subject_keys(name, spelled),
            "axiom": entry.get("axiom"),
            "problem_type": entry.get("problem_type"),
            "confidence": entry.get("confidence"),
            "boundary": entry.get("boundary"),
            # The numbers, which is the reason this artifact exists at all. Copied
            # rather than reshaped: `bound`, `threshold_type` and `value` are the
            # engine's vocabulary, and renaming them here would create a second
            # vocabulary for one set of facts.
            "measurement": dict(inner)}
