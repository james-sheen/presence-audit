"""Write a fitted gain into a supplemental file, with what it was fitted from.

The engine fits a coupling's gain from history and reports it as a PROPOSAL: an
`n`, an r-squared, an interval, and a replay saying what adopting it would have
caught. It will not write the number down, and that refusal is load-bearing -- an
engine that replaced a declaration with its own measurement leaves nobody able to
say what the model asserts.

**Somebody still has to write it down**, or every fit is a measurement nobody can
act on. The engine's ruling says who: a vertical, in its own file, under a command
a person invoked, recording a basis. The distance from the engine is the whole of
the permission -- a separate distribution, a separate command, a named proposal,
and a basis in the file -- and taking any one of them away leaves the thing the
engine refuses.

**THIS MODULE IS THE WRITER, AND THE COMMAND STAYS IN THE VERTICAL.** It was
written inside the first vertical that needed it, and nothing in it was about that
domain: two lines named that vertical's own file layout and its distribution. It
lives beside the format it writes now, so the keys it sets and the loader that
reads them are one package and cannot drift apart. Each vertical still exposes
its own command and names itself in the basis (`by=`), because the ruling's
distance is a person invoking a vertical's command -- this package runs nothing on
its own.

**THE FILE IS THE AUTHOR'S, AND THIS ONLY EVER FILLS IN A BLANK.** `gain:
estimate` is an author saying *these two are coupled and I do not know by how
much*. Adopting answers that question. A coupling that already declares a NUMBER
is the author's claim about the system, and where the data contradict it the
engine reports a disagreement -- so this refuses to touch it.

**AND IT REFUSES A NUMBER THAT WOULD NOT HAVE HELPED.** `n` and `r_squared` say
how well a gain fits the window it was fitted on; the replay says whether adopting
it would have caught more of what actually happened. Those come apart, so the
replay is the gate. Two refusals, because they are two facts with two remedies:

  * the replay RAN and the proposal caught no more -- forcing stamps
    `adopted_without_replay_gain`;
  * there was no corpus to replay against at all -- forcing stamps
    `adopted_untested`.

**WHAT IS WRITTEN IS RE-READ BEFORE IT IS KEPT,** through `load_supplemental`,
and restored if it does not load or does not carry the number. **THE SPREAD IS
WRITTEN BESIDE THE GAIN** when the fit proposes one, with a basis of its own, and
the file is raised to the oldest format that carries it.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

__all__ = ["ADOPTED_WITHOUT_REPLAY_GAIN", "ADOPTED_UNTESTED", "SPREAD_KEY",
           "AdoptionRefused", "Proposal", "Written", "proposals", "find", "check",
           "basis_for", "spread_basis_for", "declared_format", "format_for_spread",
           "write", "now"]

#: Stamped into the basis when a forced adoption overrode a replay that RAN and
#: found the proposal caught no more than the model already did.
ADOPTED_WITHOUT_REPLAY_GAIN = "adopted_without_replay_gain"

#: Stamped when a forced adoption overrode the absence of a corpus. A different
#: fact from the one above and a different remedy -- file a surprises corpus -- so
#: it is a different stamp.
ADOPTED_UNTESTED = "adopted_untested"

#: The coupling key a spread is written under, which is also the engine's.
SPREAD_KEY = "gain_sigma"


class AdoptionRefused(Exception):
    """Why a proposal was not written. Every one of these is a refusal, never a
    warning: a run that carried on would leave the operator believing a number
    is in their file."""


@dataclass(frozen=True)
class Proposal:
    """One fitted gain, named the way the operator's own file names it.

    `id` is `<driver> -> <driven>` in DECLARED point names -- the two strings an
    author typed into their supplemental. The engine names its edge after the
    sanitised entity types it generated, which is a spelling nobody chose.
    """

    id: str
    driver: str
    driven: str
    gain: float
    n: int
    r_squared: float
    interval: tuple[float, float]
    response_model: str
    grid_seconds: float
    declared_gain: float | None
    replay: dict
    #: The engine's proposed `gain_sigma`: the standard error of the fitted gain.
    gain_sigma: float | None = None
    #: Whether the engine reports that standard error readable as stated.
    sigma_assumes_independence: bool | None = None
    residual_autocorrelation: float | None = None

    @property
    def replay_ran(self) -> bool:
        return self.replay.get("status") == "replayed"

    @property
    def delta(self) -> int | None:
        return self.replay.get("delta") if self.replay_ran else None

    @property
    def spread(self) -> float | None:
        """The standard error, where it can be written down as a spread.

        A zero is not one: the format refuses it because the engine reads zero
        as no spread at all. A merely tiny one is that fit's standard error, and
        is written as it is: a floor below which a real number counted as none
        would be this module picking a threshold nobody declared.
        """
        sigma = self.gain_sigma
        if sigma is None or not math.isfinite(sigma) or sigma <= 0:
            return None
        return sigma


def proposals(described: dict, manifest: Any, *,
              grid_seconds: float) -> list[Proposal]:
    """Every fitted gain in a `model_describe` payload, in the file's names.

    The engine's `edge` is `<source entity id>-><target entity id>`, and the
    feeder registers each entity under its generated TYPE. So the mapping back is
    the manifest's, which is the one place the two spellings are recorded
    together.
    """
    by_type = {point.entity_type: point.declared_name for point in manifest.points}
    out: list[Proposal] = []
    for row in (((described.get("model") or {}).get("proposed_transitions")
                 or {}).get("fitted") or []):
        edge = str(row.get("edge") or "")
        if "->" not in edge:
            continue
        source, target = edge.split("->", 1)
        driver = by_type.get(source)
        driven = by_type.get(target)
        if driver is None or driven is None:
            # An edge the file cannot name is skipped, not rendered under the
            # generated spelling: an id nobody can find in their own file is
            # worse than one absent from the list.
            continue
        low, high = (row.get("interval") or [float("nan"), float("nan")])[:2]
        independent = row.get("gain_sigma_assumes_independent_residuals")
        autocorrelation = row.get("residual_autocorrelation")
        out.append(Proposal(
            id=f"{driver} -> {driven}",
            driver=driver, driven=driven,
            gain=float(row["gain"]), n=int(row.get("n") or 0),
            r_squared=float(row.get("r_squared") or 0.0),
            interval=(float(low), float(high)),
            response_model=str(row.get("response_model") or ""),
            grid_seconds=float(grid_seconds),
            declared_gain=(None if row.get("declared_gain") is None
                           else float(row["declared_gain"])),
            replay=dict(row.get("replay") or {}),
            gain_sigma=(None if row.get("gain_sigma") is None
                        else float(row["gain_sigma"])),
            sigma_assumes_independence=(None if independent is None
                                        else bool(independent)),
            residual_autocorrelation=(None if autocorrelation is None
                                      else float(autocorrelation))))
    return out


def find(candidates: Sequence[Proposal], wanted: str) -> Proposal:
    """The one proposal named, or a refusal that lists the alternatives.

    Matched on the whole id after collapsing whitespace, so `A->B` and `A -> B`
    are the same request.
    """
    key = _key(wanted)
    for candidate in candidates:
        if _key(candidate.id) == key:
            return candidate
    if not candidates:
        raise AdoptionRefused(
            "this run fitted no gains, so there is no proposal to adopt. A "
            "coupling is fitted only when both its ends were reading and the run "
            "carried enough paired samples; the run that fitted them reports "
            "which.")
    available = "\n".join(f"    {c.id}" for c in candidates)
    raise AdoptionRefused(
        f"no proposal is named {wanted!r}. This run fitted:\n{available}")


def _key(value: str) -> str:
    return "".join(str(value).split()).lower()


def basis_for(proposal: Proposal, *, when: datetime, by: str,
              stamp: str | None = None, override: str = "--force") -> str:
    """The sentence written into `gain_basis`, and it is the whole provenance.

    `by` is the distribution that wrote it and its version, as a reviewer will
    need to look it up. `override` is how that distribution's command spells
    forcing, so the sentence names the flag the operator actually passed.
    """
    low, high = proposal.interval
    parts = [
        f"adopted_from_proposal {proposal.id} at {when.isoformat()} by {by}",
        f"fitted {proposal.gain:.6g} through a {proposal.response_model} "
        f"response over {proposal.n} paired changes, r_squared "
        f"{proposal.r_squared:.4g}, interval "
        f"[{low:.6g}, {high:.6g}], on a {proposal.grid_seconds:g}s "
        f"collection grid",
    ]
    if proposal.replay_ran:
        parts.append(
            f"replayed against the {proposal.replay.get('corpus')} corpus: "
            f"detected {proposal.replay.get('detected_before')} -> "
            f"{proposal.replay.get('detected_after')} of "
            f"{proposal.replay.get('confirmed')} confirmed "
            f"(delta {proposal.delta:+d})")
    else:
        parts.append(f"no replay: {proposal.replay.get('reason') or 'unavailable'}")
    if stamp:
        parts.append(
            f"{stamp}: {override} was given, so this number is in the file "
            f"without evidence that adopting it catches more")
    return ". ".join(parts) + "."


def spread_basis_for(proposal: Proposal, *, when: datetime, by: str) -> str:
    """The sentence written into `gain_sigma_basis`: how sure the number is, and
    what that sureness ASSUMES -- which the engine reports and the file cannot
    recover afterwards."""
    spread = proposal.spread
    parts = [
        f"adopted_from_proposal {proposal.id} at {when.isoformat()} by {by}",
        f"the standard error of the fitted gain, {spread:.6g}, over "
        f"{proposal.n} paired changes through a {proposal.response_model} "
        f"response on a {proposal.grid_seconds:g}s collection grid: how well "
        f"the readings pin the gain down, not how much they scatter",
    ]
    autocorrelation = ("" if proposal.residual_autocorrelation is None else
                       f" (lag-1 residual autocorrelation "
                       f"{proposal.residual_autocorrelation:.3g})")
    if proposal.sigma_assumes_independence is False:
        parts.append(
            f"the engine reports it NOT readable as stated on a "
            f"{proposal.response_model} fit{autocorrelation}: it comes out "
            f"wider than the gain's true scatter, so the band it draws errs "
            f"wide")
    elif proposal.sigma_assumes_independence is True:
        parts.append(
            f"the engine reports it readable as stated on a "
            f"{proposal.response_model} fit{autocorrelation}")
    else:
        parts.append("the engine did not say whether it is readable as stated "
                     "on this fit")
    return ". ".join(parts) + "."


def declared_format(path: str | Path) -> str | None:
    """The format id a supplemental file declares, read as written."""
    return json.loads(Path(path).read_text(encoding="utf-8")).get("format")


def format_for_spread(declared: str | None) -> str | None:
    """The id a file must declare to carry a spread; `None` if it already can.

    The OLDEST such id, not the newest: raising a header is a change to the
    author's file, and the smallest change that carries the key is the one an
    older build is likeliest to read.
    """
    from . import supplemental as _format

    by_format = _format.COUPLING_KEYS_BY_FORMAT
    if SPREAD_KEY in by_format.get(declared, ()):
        return None
    for name in reversed(_format.ACCEPTED_FORMATS):
        if SPREAD_KEY in by_format.get(name, ()):
            return name
    raise AdoptionRefused("no supplemental format carries a coupling's spread")


@dataclass(frozen=True)
class Written:
    """What `write` put into the file, for the command to say."""

    text: str
    spread: float | None
    format_raised_from: str | None = None
    format_raised_to: str | None = None


def check(proposal: Proposal, *, force: bool, override: str = "--force") -> str | None:
    """The gate. Returns the stamp to record, or raises the refusal.

    `None` means the replay ran and the proposal caught more -- nothing to stamp,
    because the number earned its place. A declared numeric gain is refused with
    no override at all.
    """
    if proposal.declared_gain is not None:
        raise AdoptionRefused(
            f"{proposal.id} already declares gain {proposal.declared_gain:g}. "
            f"That is your claim about the system, and a fit that disagrees "
            f"with it is a FINDING, reported with its interval. Nothing here "
            f"overwrites a declared number: adopting fills in `gain: estimate`, "
            f"which is the author asking for one.")
    if not proposal.replay_ran:
        if not force:
            raise AdoptionRefused(
                f"{proposal.id} has no corpus to replay against, so nothing "
                f"says whether adopting it would catch more. This is a "
                f"refusal and not a score of zero -- {proposal.replay.get('reason')}"
                f"\n\nEither file a surprises corpus for this domain, or pass "
                f"{override}, which writes `{ADOPTED_UNTESTED}` into the basis.")
        return ADOPTED_UNTESTED
    if proposal.delta is not None and proposal.delta <= 0:
        if not force:
            raise AdoptionRefused(
                f"{proposal.id} fits the data well and changes nothing: the "
                f"replay detected {proposal.replay.get('detected_before')} "
                f"before and {proposal.replay.get('detected_after')} after, a "
                f"delta of {proposal.delta:+d} over "
                f"{proposal.replay.get('confirmed')} confirmed entries.\n\n"
                f"r_squared {proposal.r_squared:.4g} says how well the number "
                f"fits the window it was fitted on, which is a different "
                f"question. Pass {override} to adopt anyway, which writes "
                f"`{ADOPTED_WITHOUT_REPLAY_GAIN}` into the basis.")
        return ADOPTED_WITHOUT_REPLAY_GAIN
    return None


def write(path: str | Path, proposal: Proposal, basis: str,
          spread_basis: str | None = None) -> Written:
    """Set `gain` and `gain_basis` on the matching coupling -- and the spread,
    when `spread_basis` is given and the fit has one -- and prove it parses and
    carries them. Restored on any refusal."""
    from .supplemental import SupplementalError, load_supplemental

    path = Path(path)
    original = path.read_text(encoding="utf-8")
    document = json.loads(original)
    spread = proposal.spread if spread_basis else None
    raised_from = raised_to = None
    if spread is not None:
        raised_to = format_for_spread(document.get("format"))
        if raised_to is not None:
            raised_from = document.get("format")

    def _number(into: dict) -> None:
        into["gain"] = proposal.gain
        into["gain_basis"] = basis
        if spread is not None:
            into[SPREAD_KEY] = spread
            into["gain_sigma_basis"] = spread_basis

    written_here = ("gain_basis", SPREAD_KEY, "gain_sigma_basis")
    couplings = document.get("couplings") or []
    for index, block in enumerate(couplings):
        if (str(block.get("from")) == proposal.driver
                and str(block.get("to")) == proposal.driven):
            # Rebuilt rather than mutated, so `gain_basis` lands beside `gain`:
            # a provenance sentence three keys from the number it is about is
            # one a reviewer reads separately.
            rebuilt: dict = {}
            for key, value in block.items():
                if key == "gain":
                    _number(rebuilt)
                elif key not in written_here:
                    rebuilt[key] = value
            if "gain" not in rebuilt:
                # `gain:` IS OPTIONAL -- absent means withheld, as `estimate`
                # does -- so walking the existing keys could write nothing and
                # report success.
                _number(rebuilt)
            couplings[index] = rebuilt
            break
    else:
        raise AdoptionRefused(
            f"{path} declares no coupling from {proposal.driver!r} to "
            f"{proposal.driven!r}; it may have been edited since this run read it")
    if raised_to is not None:
        document["format"] = raised_to

    updated = json.dumps(document, indent=2, ensure_ascii=False) + "\n"
    path.write_text(updated, encoding="utf-8")
    try:
        reloaded = load_supplemental(str(path))
    except SupplementalError as error:
        path.write_text(original, encoding="utf-8")
        raise AdoptionRefused(
            f"the adopted file did not load back: {error}\n\n"
            f"{path} is unchanged.") from error
    # PARSING IS NOT THE POST-CONDITION: a file can load perfectly and still
    # carry the number it started with.
    landed = next((c for c in reloaded.couplings
                   if c.source == proposal.driver and c.target == proposal.driven),
                  None)
    if landed is None or landed.gain_is_withheld or landed.gain != proposal.gain:
        path.write_text(original, encoding="utf-8")
        raise AdoptionRefused(
            f"the file loaded back without the adopted gain on "
            f"{proposal.id}. {path} is unchanged.")
    if spread is not None and getattr(landed, SPREAD_KEY, None) != spread:
        path.write_text(original, encoding="utf-8")
        raise AdoptionRefused(
            f"the file loaded back without the adopted spread on "
            f"{proposal.id}. {path} is unchanged.")
    return Written(text=updated, spread=spread,
                   format_raised_from=raised_from,
                   format_raised_to=raised_to)


def now() -> datetime:
    """A real clock, and deliberately not injectable: the date records when a
    person adopted this number, and a frozen one would claim a time that did not
    happen."""
    return datetime.now(timezone.utc).replace(microsecond=0)
