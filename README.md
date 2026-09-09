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

## What a vertical supplies

A **sketch, not a runnable block** — the complete member list is
`vocabulary.Vocabulary`, which documents each one and what an empty answer
means. Thirteen members; most domains answer several of them with *nothing*.

```
class MyVocabulary:
    kinds       = ("tag", "label")      # every class a declared point falls into
    count_keys  = {"label": "not_a_tag"}  # the ones worth reporting, under YOUR name
    def classify(self, declared_type): ...        # must return a member of `kinds`
    def is_auditable(self, kind): ...             # which kinds the audit is about
    def is_expected_live(self, declared_type): ...
    # ... and eight more, including the three that let a domain say
    #     something about its own capture that the pairing cannot see

def register():
    from presence_audit import vocabulary
    vocabulary.register(MyVocabulary())
```

Name `register` on the `presence_audit.plugins` entry point and a plain
`pip install` finds it. Then `diff.compare(declaration, capture)` answers in
three states, counting your kinds under your own keys.

Two installed verticals are refused, not ranked, as above. Choose one with the
environment variable or your own command line.

## Known verticals

Each of these registers on `presence_audit.plugins`. Where a link goes says
where the thing is:

| distribution | the domain it supplies | where it is |
|---|---|---|
| [`bmc-sensor-audit`](https://pypi.org/project/bmc-sensor-audit/) | server BMC sensors, read over Redfish | on the index: `pip install bmc-sensor-audit` |
| [`factory-line-audit`](https://github.com/james-sheen/factory-line-audit) | a discrete-manufacturing line, read over OPC UA | source only, not on the index: install the repository with its `vertical` extra |

The extra on `factory-line-audit` is not a detail: that package runs a whole
stage without this one, and only its vertical leg needs a core to register with.

Install exactly one of them beside this package. None of them is a dependency of
this one and none ever will be — the arrow points the other way, which is what
lets the next vertical arrive without any of these knowing.

## Status

Extracted from `bmc-sensor-audit`, which keeps its Redfish capture layer, its
sensor vocabulary and its command line and now depends on this. The extraction
was by import graph: every module here reaches nothing domain-specific, and that
is asserted by a test rather than by this sentence.

Apache-2.0.
