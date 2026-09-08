# presence-audit

Given a **declaration** of what should exist and a **capture** of what was
observed, say which declared points are **reading**, **present but not reading**,
or **absent**.

Those three states are the whole product. *We did not look* and *it is not there*
are different findings, and a presence audit exists to keep them apart.

## What it does not know

Anything about your domain. What a declared point IS, which kinds are worth
auditing, when two of them are redundant readings of one thing, what changed
about one between two captures — all of that arrives through a **vocabulary**
supplied by a vertical you register. This package ships none.

The protocol in `protocols.py` is the whole contract a vertical is written
against. If something here needs a member the protocol does not declare, the
protocol is wrong — not your vertical.

## Registering a vertical

Three ways in, resolved before anything is read:

- an entry point in the group `presence_audit.plugins`
- `PRESENCE_AUDIT_PLUGINS`, an `os.pathsep`-separated list of specs
- whatever your own command line passes to `plugins.load_spec`

Two installed verticals are **refused rather than ranked**: both would register,
the later would silently win, and every verdict would come from a domain you were
not auditing.

## Status

Extracted from `bmc-sensor-audit`, which keeps its Redfish capture layer, its
sensor vocabulary and its command line and now depends on this. The extraction
was by import graph: every module here reaches nothing domain-specific, and that
is asserted by a test rather than by this sentence.

Apache-2.0.
