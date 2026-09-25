"""Given a declaration and a capture, say what is present.

A declaration is what should exist. A capture is what was observed. This
package pairs them and puts every declared point in one of three states --
reading, present but not reading, absent -- diffs two captures for regression,
turns either into a report, feeds a judge, and attests to what it did.

**It knows nothing about any domain, and it cannot.** What a declared point IS,
which kinds are worth auditing, when two of them are redundant readings of one
thing, what changed about one between two captures: those are domain questions,
and they arrive through `vocabulary.Vocabulary` from a vertical that registers
itself. This package ships no vertical. That is the property it exists to have,
and `tests/` asserts it rather than this docstring promising it.

The protocol in `protocols.py` is the WHOLE contract a vertical is written
against. If something here needs a member the protocol does not declare, the
protocol is wrong -- not the vertical.
"""

# The one contract this package holds with an engine, re-exported so a reader
# can see it without knowing which module it lives in. Imported rather than
# restated: a second literal here would be a second record of one fact, and the
# whole point of the constant is that there is one.
from .feeder import ENVELOPE_SCHEMA_VERSION
from .protocols import PROTOCOL_VERSION

# `exit_contract.compose` is deliberately NOT re-exported here. The two names
# above are constants a reader has to be able to find without knowing which
# module holds them; a function with a module named after the contract it
# implements is already findable, and re-exporting it under a second name --
# `compose` means nothing at the package root, so it would have needed one --
# creates exactly the two-records-of-one-fact problem the constants avoid.
__all__ = ["ENVELOPE_SCHEMA_VERSION", "PROTOCOL_VERSION"]

__version__ = "0.1.10"
