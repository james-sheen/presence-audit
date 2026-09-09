"""The three exit codes, and the one rule for combining them.

`0` clean, `1` something got worse, `2` could not complete. Two audits of
different domains are comparable only if they mean the same thing by those
numbers, which is why the rule lives here rather than being written out again
in each vertical.

**What is here is the COMPOSE rule and nothing else.** Maximum over the legs,
so the worst leg wins; `2` outranks `1` because *could not read* is a different
claim from *something got worse*, and a gate that conflates them fails a healthy
system for a network timeout. A value outside the three reads as `2` with the
raw value kept beside it, because a leg that returned `137` has told you
something and clamping it silently destroys the evidence.

**What is NOT here, deliberately: the floors.** Which finding class or decline
reason floors at which code is a DOMAIN judgement -- it depends on what the
axiom means where you are, how often it fires on a healthy population, and what
a false alarm costs somebody. A package that cannot see a domain cannot make
that call, and a shared default would be made once, by whoever wrote the first
vertical, and inherited by everyone after them without anybody deciding.

The worked example is a learned baseline: an axiom firing at two sigma from a
rolling mean will fire on a healthy population about as often as the tail says
it will, so one vertical floors its warning arm at `0` and its critical arm at
`1` -- measured, over its own series. The same axiom against a DECLARED setpoint
floors at `1` in both arms, because a setpoint is a statement about the plant
rather than about the last thirty samples. Neither number is derivable from
here, and putting either here would make it look as if it were.

So: verticals keep their own floor tables, and share this.
"""

from __future__ import annotations

from typing import Any, Tuple

__all__ = ["CLEAN", "FINDINGS", "INCOMPLETE", "MEANING", "normalise", "compose"]

CLEAN = 0
FINDINGS = 1
INCOMPLETE = 2

#: What each code means, for a caller printing it. The words matter as much as
#: the numbers: *could-not-complete* is the one a reader is most likely to
#: misread as a failure of the thing being audited rather than of the audit.
MEANING = {CLEAN: "clean",
           FINDINGS: "findings",
           INCOMPLETE: "could-not-complete"}


def normalise(code: Any) -> Tuple[int, Any]:
    """Map anything to one of the three, keeping the raw value beside it.

    Both halves matter. A composer that clamps and forgets has destroyed the
    evidence that a leg exited `137`, and `137` is the most informative thing
    that run produced.

    `True` normalises to `2` and not to `1`. It is an `int` in Python and would
    otherwise sail through as *something got worse*, which is a claim nobody
    made -- a boolean where a code was expected is a caller error, and a caller
    error is a run that did not complete.
    """
    if isinstance(code, bool) or not isinstance(code, int):
        return INCOMPLETE, code
    if code in (CLEAN, FINDINGS, INCOMPLETE):
        return code, code
    return INCOMPLETE, code


def compose(*codes: Any) -> int:
    """The worst leg wins. Composing NOTHING is `2`, not `0`.

    The empty case is the whole reason this is a function rather than `max()`.
    `max()` of nothing raises, and a caller who guards that with a default will
    reach for `0` -- but composing no legs is the shape of a battery whose legs
    all failed to be collected, and reading that as clean is precisely the
    could-not-run-exits-clean failure the three-code contract exists to prevent.
    """
    normalised = [normalise(code)[0] for code in codes]
    if not normalised:
        return INCOMPLETE
    return max(normalised)
