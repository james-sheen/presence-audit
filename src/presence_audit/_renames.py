"""The reading window: public names this package renamed, and how the old ones still read.

This package's first vertical named the thing it audits, and the name stuck in
the shared code: a record's subject field, five change kinds, a manifest key, a
generated class, the keys of two input blocks. Every other vertical then had to
spell that one domain's word for its own subject to use the core at all, and
relabel it on the way out.

The neutral word is the one this package has used about itself from the start:
a declared thing is a POINT (`CapturedPoint`, `DeclaredPoint`, `DEFAULT_NOUN`).

THE OLD NAMES STILL READ, AND SAY SO. Through the 0.1 line every old name is
accepted where it was accepted and answers where it answered, with a
`DeprecationWarning` naming its replacement. They are removed in 0.2.0, which
every consumer's `<0.2` ceiling keeps out until that consumer has moved. A
renamed public field is a break for whoever reads it, and a window is how a
break is taken without breaking anybody who has not had the chance to move.
"""

from __future__ import annotations

import warnings
from typing import Any

#: A keyword nobody passed. `None` cannot serve: it is a legitimate value.
UNSET: Any = object()

#: The release the old names stop reading in.
REMOVED_IN = "0.2.0"

#: The key a record named its point under, and the plural it counted them
#: under, as published. Written once, here, so the window's own code names them
#: in one place and 0.2.0 can remove them from one place.
PUBLISHED_SUBJECT = "sensor"
PUBLISHED_SUBJECTS = "sensors"


def warn(owner: str, old: str, new: str, *, stacklevel: int = 3) -> None:
    warnings.warn(
        f"{owner}.{old} is renamed {owner}.{new}; the old name reads until "
        f"presence-audit {REMOVED_IN}",
        DeprecationWarning, stacklevel=stacklevel)


def resolve(new_value: Any, old_value: Any, owner: str, old: str, new: str) -> Any:
    """The value a caller meant, whichever spelling they passed it under.

    Both spellings at once is refused rather than resolved: two values for one
    field is a caller bug, and picking either would hide it.
    """
    if old_value is UNSET:
        return new_value
    if new_value is not UNSET:
        raise TypeError(f"{owner}() got both {new!r} and its old name {old!r}; "
                        f"pass {new!r} only")
    warn(owner, old, new, stacklevel=4)
    return old_value
