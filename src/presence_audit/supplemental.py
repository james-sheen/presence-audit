"""Declarations the system does not make about itself, written down by an operator.

Two axioms need a fact the declaration format has no way to state, and neither can
be derived from the declaration however carefully it is read:

**Redundancy.** CONSISTENCY can check that two readings which should agree do.
Nothing in a declaration says two points measure the same thing. The tempting
derivation is the multi-channel part -- a TMP421 declares `Name` and `Name1`, so pair
them -- and it is wrong on the physics: those two channels are the chip's own die and
an external diode, which differ by tens of degrees on a working board. The other
tempting derivation is identical declared thresholds, and the pinned corpus refutes it
outright: `SLED1_THERM_LOCAL` through `SLED6_THERM_LOCAL` carry the same four numbers
and sit on six different parts.

So redundancy is a claim about the hardware, and this project's rule for the shape of
that claim already exists in the engine's own modelling guide: **a floor is a
specification, not a guess.** A pairing is the same kind of sentence. Auto-pairing
would have produced a tool that reports disagreement between two things that were
never the same measurement, which is worse than not checking -- it is a false positive
that looks like the feature working.

**Counters.** MONOTONICITY judges values that only ever climb. Power-on hours and
error counters mostly live outside `entity-manager` altogether, so which readings are
cumulative is also operator knowledge.

**Couplings.** The engine can step a model forward through declared dynamics -- what
drives what, how long the change takes to arrive, how fast it settles -- and nothing in
a declaration says that one reading moves another. Two points that drive one another
are two independent entries to every format that lists them; which of them moves which
is a fact about the installation, not about the file. So a coupling is the same kind of
operator sentence as a pairing, and gets the same treatment.

**Its gain is a specification too, and usually nobody has one.** A coupling may state
`gain` as a number with a `gain_basis` -- a datasheet coefficient, a commissioning
measurement -- or as the string `estimate`, which declares the coupling and withholds
the number. The engine then fits it from history and reports it with its `n`, its
`r_squared` and an interval, and **projects nothing until a human writes a number
down**. Withholding is the honest default; inventing a coefficient to make a
simulation run would put a guess where this format's whole purpose is to refuse one.

**`sampling_interval_s` is required once a coupling is declared, and this was
MEASURED rather than reasoned.** The fit aligns the two series on a shared grid, so a
`propagation_delay_s` that is not a multiple of the collection cadence can align no
pair of readings at all: the engine declines `delay_off_grid` and the coupling
contributes nothing, from a file that looks correct. Refusing it here turns a silent
later decline into a load-time error naming the arithmetic.

**Flows.** CONSERVATION checks that what goes into a device comes out of it, minus a
tolerated loss. `entity-manager` does declare the readings -- the pinned Ampere
Mt.Jade configuration exposes `PSU0_PINPUT` and `PSU0_POUTPUT` -- but nothing in the
file says the second is the first minus conversion loss, and nothing says what loss is
acceptable. **The loss margin is an efficiency figure off a datasheet**, which is the
same kind of number as a threshold floor and gets the same treatment: declared, with
its basis, or absent.

Those two readings also carry **no thresholds at all**, so the generator's ordinary
rule excludes them -- a point with nothing to bound against is a question nobody
asked. Naming one in a flow is what asks the question, so a flow participant is
modelled whether or not it has bounds.

## The file

    {
      "format": "presence-audit/supplemental/1",
      "provenance": "who established this and how",
      "redundant_groups": [
        {"sensors": ["A", "B"], "tolerance": 0.05,
         "basis": "why these are the same measurement"}
      ],
      "counters": [
        {"sensor": "PWR_ON_HOURS", "direction": "increasing", "allow_reset": true,
         "basis": "why this only climbs"}
      ],
      "sampling_interval_s": 300,
      "couplings": [
        {"from": "DRIVER_POINT", "to": "DRIVEN_POINT",
         "propagation_delay_s": 300, "time_constant_s": 600,
         "gain": "estimate",
         "basis": "why the first drives the second"}
      ]
    }

**`basis` is required and is not decoration.** It is the difference between a
specification and a guess, and it is the field a reviewer reads first. A group without
one is refused rather than accepted with a warning, because a warning on a path that
still works is a warning nobody reads.

Points are named as the declaration names them -- `display_name`, whatever shape
that takes. A name this file mentions and the declaration does not is refused too:
the likeliest cause is a typo, and a typo silently drops the pairing it was written to
create, leaving a file that looks like the check is running.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from . import vocabulary as _vocabulary

__all__ = ["ACCEPTED_FORMATS",
           "Supplemental", "RedundantGroup", "Counter", "Coupling",
           "load_supplemental", "SupplementalError", "FORMAT",
           "RESPONSE_MODELS", "ESTIMATE"]

FORMAT = "presence-audit/supplemental/1"

#: Accepted on read, newest first. Same argument as the attestation format: the
#: shape is unchanged, so a file written before the move is still this document.
ACCEPTED_FORMATS = (FORMAT, "bmc-sensor-audit/supplemental/1")

# The engine's own default is 0.05 relative. Restated rather than imported because
# Stage 1 must not import the engine, and a default that silently tracked an upstream
# constant would move a live tolerance under an operator on an engine bump.
DEFAULT_TOLERANCE = 0.05

_DIRECTIONS = ("increasing", "decreasing")

#: The time courses the engine knows. Restated rather than imported for the reason
#: `DEFAULT_TOLERANCE` is: Stage 1 must not import the engine.
#:
#: **A RESTATED CLOSED ENUM IS NOT A RESTATED DEFAULT, and this one is guarded.** A
#: default that drifts moves a number; a member list that drifts refuses a value the
#: engine accepts, or accepts one it does not. The first draft of this line was
#: written from memory and got it wrong in two directions at once -- it invented
#: `immediate`, which the engine has never had, and omitted `step` and `logarithmic`,
#: which it has. `test_the_response_models_are_the_engine's` re-derives this tuple
#: from the engine wherever the engine is installed, and skips with a reason where it
#: is not.
RESPONSE_MODELS = ("exponential", "linear", "step", "logarithmic")

#: A gain declared as withheld. The coupling is stated; the number is not.
ESTIMATE = "estimate"


class SupplementalError(ValueError):
    """The file could not be used. Never a warning: see the module docstring."""


@dataclass(frozen=True)
class RedundantGroup:
    sensors: tuple[str, ...]
    basis: str
    tolerance: float | None = None
    tolerance_absolute: float | None = None

    @property
    def primary(self) -> str:
        """The member that carries the `consistency` block.

        One side declares it, not both. The engine's agreement test is symmetric --
        it divides by `max(abs(a), abs(b))` precisely so that `a agrees with b` means
        the same as `b agrees with a` -- so declaring it twice would produce two
        findings for one disagreement and double-count a single drifting point.
        """
        return self.sensors[0]

    @property
    def peers(self) -> tuple[str, ...]:
        return self.sensors[1:]


@dataclass(frozen=True)
class Counter:
    sensor: str
    basis: str
    direction: str = "increasing"
    allow_reset: bool = True


@dataclass(frozen=True)
class Flow:
    """One conservation claim: this input, these outputs, this tolerated loss."""

    input: str
    outputs: tuple[str, ...]
    basis: str
    loss_margin: float | None = None

    @property
    def members(self) -> tuple[str, ...]:
        return (self.input,) + self.outputs


@dataclass(frozen=True)
class Coupling:
    """One reading drives another, and how long it takes to arrive.

    `gain` is either a float or `ESTIMATE`. The two are not interchangeable: a
    number projects, and a withheld one declares the coupling and leaves the
    engine reporting a fit nobody has adopted. Which of those a file states is
    the operator's claim about whether anybody has measured it.
    """

    source: str
    target: str
    basis: str
    propagation_delay_s: float
    time_constant_s: float
    response_model: str = "exponential"
    gain: float | str = ESTIMATE
    gain_basis: str | None = None

    @property
    def gain_is_withheld(self) -> bool:
        return isinstance(self.gain, str)

    @property
    def members(self) -> tuple[str, ...]:
        return (self.source, self.target)


@dataclass
class Supplemental:
    """Operator declarations, and the file they came from."""

    provenance: str = ""
    source: str | None = None
    redundant_groups: list[RedundantGroup] = field(default_factory=list)
    counters: list[Counter] = field(default_factory=list)
    flows: list[Flow] = field(default_factory=list)
    couplings: list[Coupling] = field(default_factory=list)
    #: The cadence the collector reads at. Required once a coupling is
    #: declared, because a delay that does not divide it can align no
    #: pair of readings -- see the module docstring.
    sampling_interval_s: float | None = None

    def __bool__(self) -> bool:
        return bool(self.redundant_groups or self.counters or self.flows
                    or self.couplings)

    def flow_for(self, display_name: str) -> Flow | None:
        """The flow this point is the INPUT of, if any. The outputs are carried as
        properties on the input's entity, the same way redundant peers are."""
        for flow in self.flows:
            if flow.input == display_name:
                return flow
        return None

    def modelled_regardless(self) -> set[str]:
        """Points that must be modelled even with nothing to bound against.

        A flow's readings routinely carry no thresholds -- the pinned Mt.Jade PSU
        entries declare `pin` and `pout1` with bounds on neither -- and the ordinary
        exclusion rule would drop them, leaving a declared conservation check that
        silently never runs.
        """
        names = {name for flow in self.flows for name in flow.members}
        # A COUPLED POINT IS THE SAME CASE. A fan tachometer routinely carries no
        # thresholds -- no speed is a fault on its own -- so the ordinary exclusion
        # rule drops it, and a coupling naming it would then reference an entity
        # type the model does not contain. Naming a point in a coupling is what
        # asks the question, exactly as naming one in a flow is.
        return names | {name for c in self.couplings for name in c.members}

    def group_for(self, display_name: str) -> RedundantGroup | None:
        """The group this point leads, if it leads one."""
        for group in self.redundant_groups:
            if group.primary == display_name:
                return group
        return None

    def peer_of_any_group(self, display_name: str) -> bool:
        return any(display_name in g.peers for g in self.redundant_groups)

    def counter_for(self, display_name: str) -> Counter | None:
        for counter in self.counters:
            if counter.sensor == display_name:
                return counter
        return None

    def names(self) -> set[str]:
        """Every point name this file mentions, for the cross-check against the
        declaration."""
        named = {s for group in self.redundant_groups for s in group.sensors}
        named |= {name for flow in self.flows for name in flow.members}
        named |= {name for c in self.couplings for name in c.members}
        return named | {c.sensor for c in self.counters}


def _own(plural: bool = False) -> str | None:
    """The domain's own spelling of an input key, or None when it is ours."""
    return _vocabulary.record_key(plural=plural)


def _either(block: dict, key: str):
    """A block's value under the published key OR the domain's own word for it.

    The published spellings are REQUIRED INPUT keys here, so a vertical whose
    domain is a different one had to write another domain's noun into its own
    supplemental file to be read at all -- the one surface it could not route
    around by writing its own report. Both spellings are accepted now; neither
    is required to be the one the published format was named after.
    """
    own = _own(plural=key.endswith("s"))
    if own is not None and own in block:
        return block[own]
    return block.get(key)


def _require_named(block: dict, key: str, where: str):
    """`_require`, over either spelling of a domain-named key."""
    own = _own(plural=key.endswith("s"))
    if own is not None and own in block:
        return block[own]
    return _require(block, key, where)


def _require(block: dict, key: str, where: str):
    value = block.get(key)
    if value is None or (isinstance(value, str) and not value.strip()):
        raise SupplementalError(
            f"{where} has no {key!r}. This file states things the machine does not "
            f"state about itself, so every entry has to say what establishes it")
    return value


def load_supplemental(path: str | Path) -> Supplemental:
    """Read and validate a supplemental declarations file.

    Every refusal here is a hard error. A malformed entry that loaded anyway would
    produce a run that reports no disagreements because it never checked for any --
    indistinguishable, from the outside, from a board where everything agrees.
    """
    path = Path(path)
    try:
        raw = json.loads(path.read_text())
    except OSError as error:
        raise SupplementalError(f"{path}: cannot be read: {error}") from error
    except json.JSONDecodeError as error:
        raise SupplementalError(f"{path}: not parseable as JSON: {error}") from error

    if not isinstance(raw, dict):
        raise SupplementalError(f"{path}: top level is not an object")
    declared_format = raw.get("format")
    if declared_format not in ACCEPTED_FORMATS:
        raise SupplementalError(
            f"{path}: format is {declared_format!r}, this build reads "
            f"{' or '.join(repr(f) for f in ACCEPTED_FORMATS)}")

    result = Supplemental(provenance=str(raw.get("provenance") or ""),
                          source=str(path))

    for index, block in enumerate(raw.get("redundant_groups") or []):
        where = f"{path}: redundant_groups[{index}]"
        if not isinstance(block, dict):
            raise SupplementalError(f"{where} is not an object")
        sensors = _either(block, "sensors")
        if not isinstance(sensors, list) or len(sensors) < 2:
            raise SupplementalError(
                f"{where} names {sensors!r}; a redundant group needs at least two "
                f"{_vocabulary.noun()[1]}, because the claim is that they agree "
                f"with each other")
        if len(set(sensors)) != len(sensors):
            raise SupplementalError(
                f"{where} names the same {_vocabulary.noun()[0]} twice; a reading "
                f"always agrees with itself, so the check would pass while "
                f"measuring nothing")
        tolerance = block.get("tolerance")
        absolute = block.get("tolerance_absolute")
        if tolerance is not None and absolute is not None:
            raise SupplementalError(
                f"{where} sets both `tolerance` and `tolerance_absolute`. The engine "
                f"reads the absolute one and ignores the relative one, so the number "
                f"written here would not be the number applied")
        result.redundant_groups.append(RedundantGroup(
            sensors=tuple(str(s) for s in sensors),
            basis=str(_require(block, "basis", where)),
            tolerance=None if tolerance is None else float(tolerance),
            tolerance_absolute=None if absolute is None else float(absolute)))

    for index, block in enumerate(raw.get("flows") or []):
        where = f"{path}: flows[{index}]"
        if not isinstance(block, dict):
            raise SupplementalError(f"{where} is not an object")
        outputs = block.get("outputs")
        if not isinstance(outputs, list) or not outputs:
            raise SupplementalError(
                f"{where} names outputs {outputs!r}; a flow needs at least one, "
                f"because the claim is that the input arrives at them")
        input_name = str(_require(block, "input", where))
        if input_name in outputs:
            raise SupplementalError(
                f"{where} names {input_name!r} as both input and output; the "
                f"balance would then compare a reading against itself and always "
                f"hold, whatever the device is doing")
        margin = block.get("loss_margin")
        if margin is not None and not 0 <= float(margin) < 1:
            raise SupplementalError(
                f"{where} sets loss_margin {margin!r}; it is a FRACTION of the "
                f"input, so 0.15 means fifteen percent. A value of 1 or more "
                f"tolerates losing everything and can never report a violation")
        result.flows.append(Flow(
            input=input_name,
            outputs=tuple(str(o) for o in outputs),
            basis=str(_require(block, "basis", where)),
            loss_margin=None if margin is None else float(margin)))

    interval = raw.get("sampling_interval_s")
    if interval is not None:
        interval = float(interval)
        if interval <= 0:
            raise SupplementalError(
                f"{path}: sampling_interval_s is {interval!r}; it is the cadence "
                f"the collector walks at, so it has to be a positive number of "
                f"seconds")
        result.sampling_interval_s = interval

    for index, block in enumerate(raw.get("couplings") or []):
        where = f"{path}: couplings[{index}]"
        if not isinstance(block, dict):
            raise SupplementalError(f"{where} is not an object")
        driver = str(_require(block, "from", where))
        driven = str(_require(block, "to", where))
        if driver == driven:
            raise SupplementalError(
                f"{where} names {driver!r} as both ends; a reading cannot be "
                f"evidence about how it drives itself, and the fit would be a "
                f"series regressed on a lagged copy of itself")
        delay = float(_require(block, "propagation_delay_s", where))
        constant = float(_require(block, "time_constant_s", where))
        if delay < 0 or constant <= 0:
            raise SupplementalError(
                f"{where} declares propagation_delay_s={delay!r} and "
                f"time_constant_s={constant!r}; the delay may be zero and the "
                f"time constant may not, because a settling time of nought is a "
                f"step and is spelled response_model: step")

        # THE GRID CHECK, and it exists because the alternative is silence. The
        # engine aligns the two series on their shared sampling grid; a delay that
        # is not a whole number of steps can align no pair of readings, so the
        # coupling declines `delay_off_grid` and contributes nothing -- from a
        # file that reads as correct. Measured before this was written.
        if interval is None:
            raise SupplementalError(
                f"{where} declares a coupling and this file states no "
                f"sampling_interval_s. The delay has to be a whole number of "
                f"collection steps or no pair of readings can be aligned, and "
                f"that cannot be checked without the cadence")
        steps = delay / interval
        if abs(steps - round(steps)) > 1e-9:
            raise SupplementalError(
                f"{where} declares propagation_delay_s={delay:g} against a "
                f"sampling_interval_s of {interval:g}, which is {steps:.4g} "
                f"collection steps. A delay that does not land on the grid aligns "
                f"no pair of readings: the engine would decline and this file "
                f"would look correct. Use a multiple of {interval:g}")

        model = str(block.get("response_model") or "exponential")
        if model not in RESPONSE_MODELS:
            raise SupplementalError(
                f"{where} declares response_model {model!r}; this build knows "
                f"{list(RESPONSE_MODELS)}")

        gain = block.get("gain", ESTIMATE)
        gain_basis = block.get("gain_basis")
        if isinstance(gain, str):
            if gain != ESTIMATE:
                raise SupplementalError(
                    f"{where} declares gain {gain!r}; a gain is a number, or the "
                    f"word {ESTIMATE!r} to declare the coupling and withhold it")
            if gain_basis:
                raise SupplementalError(
                    f"{where} withholds the gain and also states a gain_basis. "
                    f"One of those is wrong: a basis is what establishes a "
                    f"number, and there is no number here")
        else:
            gain = float(gain)
            if gain == 0:
                raise SupplementalError(
                    f"{where} declares gain 0; that is the claim that the first "
                    f"reading does not drive the second, which is what NOT "
                    f"declaring the coupling already says")
            if not str(gain_basis or "").strip():
                raise SupplementalError(
                    f"{where} states a gain and no gain_basis. A coefficient "
                    f"with nothing establishing it is the guess this file exists "
                    f"to refuse; withhold it with gain: {ESTIMATE!r} instead")

        result.couplings.append(Coupling(
            source=driver, target=driven,
            basis=str(_require(block, "basis", where)),
            propagation_delay_s=delay, time_constant_s=constant,
            response_model=model, gain=gain,
            gain_basis=None if gain_basis is None else str(gain_basis)))

    for index, block in enumerate(raw.get("counters") or []):
        where = f"{path}: counters[{index}]"
        if not isinstance(block, dict):
            raise SupplementalError(f"{where} is not an object")
        direction = str(block.get("direction") or "increasing")
        if direction not in _DIRECTIONS:
            raise SupplementalError(
                f"{where} declares direction {direction!r}; this build knows "
                f"{list(_DIRECTIONS)}")
        result.counters.append(Counter(
            sensor=str(_require_named(block, "sensor", where)),
            basis=str(_require(block, "basis", where)),
            direction=direction,
            allow_reset=bool(block.get("allow_reset", True))))

    return result


def unmatched_names(supplemental: Supplemental, declared: set[str]) -> list[str]:
    """Names the file mentions that the declaration does not carry.

    Returned rather than raised, so the caller can report every one of them at once
    instead of stopping at the first. A typo here is silent by nature: the pairing it
    was meant to create simply never exists, and the run reports no disagreement
    because it asked no question.
    """
    return sorted(supplemental.names() - declared)
