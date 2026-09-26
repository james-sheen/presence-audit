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
means. Sixteen members; most domains answer several of them with *nothing*.

```
class MyVocabulary:
    kinds       = ("tag", "label")      # every class a declared point falls into
    count_keys  = {"label": "not_a_tag"}  # the ones worth reporting, under YOUR name
    def classify(self, declared_type): ...        # must return a member of `kinds`
    def is_auditable(self, kind): ...             # which kinds the audit is about
    def is_expected_live(self, declared_type): ...
    # ... and nine more, including the three that let a domain say
    #     something about its own capture that the pairing cannot see

def register():
    from presence_audit import vocabulary
    vocabulary.register(MyVocabulary())
```

Name `register` on the `presence_audit.plugins` entry point and a plain
`pip install` finds it. Then `diff.compare(declaration, capture)` answers in
three states, counting your kinds under your own keys.

A vertical may also declare which revision of that contract it was written
against:

```
from presence_audit import PROTOCOL_VERSION

class MyVocabulary:
    protocol_version = PROTOCOL_VERSION
```

Saying nothing is admitted — verticals were published before the number
existed, and refusing them would make the guarantee itself a breaking change.
Saying the wrong thing is refused at registration, naming both numbers. The
value moves only when a vertical that conforms today would stop working, which
has not happened yet: `noun`, `count_labels` and `report_sections` all arrived
after two verticals shipped, and all three are optional so that none of them
had to move it.

Two installed verticals are refused, not ranked, as above. Choose one with the
environment variable or your own command line.

## The exit contract

`0` clean, `1` something got worse, `2` could not complete. Two audits of
different domains are comparable only if they mean the same thing by those
numbers, so the rule for combining them lives here:

```
from presence_audit.exit_contract import compose
compose(stage_one, stage_two, strict_floor)
```

The worst leg wins, `2` outranks `1`, a value outside the three reads as `2`
with the raw value kept beside it, and **composing nothing is `2`** — a battery
whose legs all failed to be collected has not come out clean. That last case is
why this is a function and not `max()`.

**The floors are not here and will not be.** Which finding class or decline
reason floors at which code depends on what the axiom means where you are and
how often it fires on a healthy population. A package that cannot see a domain
cannot make that call, and a shared default would be decided once by whoever
wrote the first vertical and inherited by everyone after. Verticals keep their
own floor tables and share this.

## Two domains in one process

The vocabulary used to be resolved from process-global state, so *which domain
is this* was a property of the interpreter rather than of the call. Every public
entry point now takes one for the call instead:

```
compare(declaration, capture, vocabulary=mine)
```

Omit it and the registered vocabulary is used, exactly as before — nothing that
worked has stopped. Pass one and **nothing is registered**, which is what lets a
harness run two verticals in one process, including in two threads at once: the
lookup is context-local, not module-level.

The report carries the vocabulary it was built with, because a report is read
after the call that made it returns, and its counts ask the domain what its
kinds are called.

**Finished migrating?** Set `PRESENCE_AUDIT_REQUIRE_EXPLICIT_VOCABULARY=1` and
the registry stops being a fallback, so your suite goes red on whatever still
depends on it. That is the only way to find those calls. It is off by default
and stays off: published verticals register and pass nothing, and a default that
broke them would make this a removal rather than an addition.

## Checking a vertical

The kit that proves this core serves a domain it was not written for ships with
it, so you can point it at yours:

```
python -m presence_audit.conformance your_package.vertical:register
```

The spec is the same one `PRESENCE_AUDIT_PLUGINS` and `--plugin` take. It drives
the core with stand-ins that implement the protocol and nothing else — no
convenience a concrete type happens to have — and then hands your vocabulary the
same objects.

**It proves nothing reached past the contract. It cannot prove the contract is
enough for you.** A stand-in is written *from* the protocol, so it can only find
that something reached past the document, never that the document is missing
something your domain needs. The second is the interesting failure and only a
real domain finds it.

## Known verticals

Each of these registers on `presence_audit.plugins`. Where a link goes says
where the thing is:

| distribution | the domain it supplies | where it is |
|---|---|---|
| [`bmc-sensor-audit`](https://pypi.org/project/bmc-sensor-audit/) | server BMC sensors, read over Redfish | on the index: `pip install bmc-sensor-audit` |
| [`factory-line-audit`](https://pypi.org/project/factory-line-audit/) | a discrete-manufacturing line, read over OPC UA | on the index: `pip install 'factory-line-audit[vertical]'` |
| [`engagement-deliverable-audit`](https://pypi.org/project/engagement-deliverable-audit/) | an engagement's deliverables, read from a tracker export | on the index: `pip install engagement-deliverable-audit` |
| [`operating-health-audit`](https://github.com/james-sheen/operating-health-audit) | an organisation's operating units, read against its operating model | source only, not on the index: install the repository |

The extra on `factory-line-audit` is not a detail: that package runs a whole
stage without this one, and only its vertical leg needs a core to register with.

**Until 0.1.12 this table was wrong twice.** It called `factory-line-audit` *source
only, not on the index* -- true for sixteen hours on 2026-09-09, and false on all
four pages this package published after, 0.1.8 through 0.1.11 -- and it named two of
the four verticals that register here. The check that asks the index about each row
asked only about rows claiming to be on it; it now asks about both.

Install exactly one of them beside this package. None of them is a dependency of
this one and none ever will be — the arrow points the other way, which is what
lets the next vertical arrive without any of these knowing.

## The engine contract

`feed()` takes a session and reads an envelope back. What this package is
coupled to is that envelope's **wire shape**, not the engine's package version,
and the shape carries a number:

```
from presence_audit import ENVELOPE_SCHEMA_VERSION
```

`feeder.schema_mismatch()` answers in three states, and the third is the one
worth knowing about. A version this build parses is accepted; a version it does
not is refused, naming both; an **absent** version is accepted, because engines
before the field existed shipped this same shape without stamping it, and
reading a missing key as *unsupported* rather than *empty* is the same mistake
as reading *absent* for *not reading*. A vertical whose own pin excludes those
engines is free to be stricter, and one is.

**Two engine constants are RESTATED here, and they are not the same risk.**
`DEFAULT_TOLERANCE` is a default: if it drifts, a number moves. `RESPONSE_MODELS`
is a closed enum, and a drifted copy refuses a value the engine accepts or accepts
one it does not — so it is guarded. The restatement is re-derived from the engine's
own enum wherever the engine happens to be installed, and skips with a reason where
it is not. The first draft of that tuple was written from memory and was wrong in
both directions at once, which is why it is checked rather than trusted.

**There is no `arbiter-engine` dependency here, and there will not be one.**
Nothing in this package imports the engine: `feed(session, ...)` takes whatever
the caller built, and the envelope comes back as a plain dict. Declaring the
engine would declare a dependency this package does not have, on the one
distribution in the family whose empty dependency list is asserted by
`tests/test_it_names_no_domain.py` rather than promised in prose. The pin lives
with the verticals because they are what construct a session, and they are
therefore the only ones who can say which engine releases they need.

## The published names do not move

Two kinds of name in this package's output are deliberately not free to change,
and both look like wording.

**The three states.** *Reading*, *present but not reading* and *absent* are keys
in a published format that two distributions already read, and the set of format
ids this package accepts is pinned by SIZE so a name cannot appear without
somebody saying why. Renaming a state reads like a lexical improvement and is a
wire-contract break.

**Nothing in a supplemental document goes unread.** A key no format carries is
refused, and a key a LATER format carries is refused under an earlier id with the
id to use named. That is the general form of the defect below: a reader ignores
what it does not recognise, so a block added to an already-published id is
invisible to every build already out there — the file loads, the block vanishes,
the run reports nothing. A reader cannot be taught a key it has never heard of;
it can be taught to refuse one it does not know. **The mechanism is forward-only
and the limit is stated rather than papered over**: builds already released
cannot learn it, and the format id is what protects those. Two mechanisms, two
populations, neither replacing the other. The declared key sets are checked
against what the loader actually reads, in both directions, by a test that
derives them from its source.

**The supplemental set went to three, and this is the saying-why.**
`presence-audit/supplemental/2` was cut because a new block in `/1` is invisible
to a build that predates it — measured: such a build loads the file without
error, drops the block, and reports the file as empty, so an operator who
declared a coupling would get a clean run in which nothing they wrote was read.
A reader cannot be taught to notice a key it has never heard of, so the notice
goes in the one field every reader already checks. Both earlier ids are still
read, because their shape is a subset; a file combining one of them with a
coupling is refused by name.

**And then the block was read by a build that did nothing with it.** That last
sentence describes an OLD reader dropping a new block. 0.1.10 fixes the mirror
image, which nothing was watching for: this build parsed the coupling, refused
four different malformations in it, emitted it into the generated model, recorded
the pair in the manifest — and never added the relationship the model needs, so
the engine reported `couplings_seen: 0` and a run with a coupling declared was
byte-identical to one without. The format id protects a reader that has never
heard of the block. Nothing protected the reader that had. Alongside it, the
feeder stamped observations sixty seconds apart whatever `sampling_interval_s`
said, so a delay this format validates against the collection grid was applied on
a different one: measured on a series generated from its driver at exactly one
interval, the fit came back **-0.0023 against a truth of +0.0040**. The window is
now generated as a number of collection samples rather than a fixed fifteen
minutes, which is what it always meant — at a sixty-second cadence it is still
`15m`, so a caller that declares no cadence sees no change.

**Then to four, in 0.1.11, because the next field sat inside a block.** A coupling can now
say how sure its gain is: `gain_sigma`, a standard deviation in the gain's own
units — a datasheet's plus-or-minus, or a fit's standard error — with a
`gain_sigma_basis` of its own. The engine adds it to the band around every value
the coupling drives; without it that band treats the gain as exact, and until
`/3` a datasheet tolerance had nowhere to be written. Every build reading `/2`
already refuses a coupling key it does not know, so nothing was ever dropped; but
it refuses saying the format has no field for a spread, which is false of a file
written for this build. Under `/3` it names the real cause, a file newer than
itself. A spread on a withheld gain, a zero, and one with no basis are refused:
the first is a spread on no number, and the engine reads the others as no spread
at all. The spread reaches the generated model under the engine's own key; its
basis stays in the file, since the engine has no field for one.

**Then to five, in 0.1.13, for two new blocks and two renamed keys.**
`presence-audit/supplemental/4` carries `fault_channels` -- which way a failure
travels, often the opposite way to a coupling, each with a `basis` and a `weight`
only where something gives one -- and `actions`, what an operator can set on a
point and with which `effect`. Every earlier id refuses both by name. It also
lists a redundant group's members under `points` and names a counter's under
`point`, where the earlier ids used the first vertical's words; those ids are read
exactly as before, old keys included.

**The names that carried another domain's word, and the window they are moving
in.** A record's subject field, five change kinds, the manifest's list, the class
behind it and those two input keys were all named after the domain this package
was extracted from, so every other vertical wrote that domain's noun to reach the
core. From 0.1.13 each has a neutral name -- `point`, `points`, `GeneratedPoint`,
`point_removed` and its four siblings -- and **every old name still reads through
the 0.1 line**: the old keyword is accepted, the old attribute answers, both with
a `DeprecationWarning` naming the replacement. Reports and attestations are
written as before unless a caller asks for format 2 (`spelled=True`), which keys
each record on `point` and the vertical's own word and spells each change kind in
that word -- so the vertical whose word the old keys were gets back exactly the
kinds it always emitted. **0.2.0 removes the old names**, and every consumer's
`<0.2` ceiling keeps it out until that consumer has moved.

## Adopting a fitted gain

The engine fits a declared coupling's gain from history and proposes it; it never
writes the number down. `presence_audit.adopt` is the writer a vertical's own
command calls to do that: it names the proposal in the file's words, refuses a
declared number outright, refuses a proposal the replay did not justify unless
forced -- stamping `adopted_without_replay_gain` or `adopted_untested`, because
those are two different facts -- writes `gain`, `gain_basis` and the fit's spread,
and keeps the file only if it loads back carrying them. The calling distribution
names itself in the basis (`by=`); the command, and the history it fitted from,
stay in the vertical.

## Status

Extracted from `bmc-sensor-audit`, which keeps its Redfish capture layer, its
sensor vocabulary and its command line and now depends on this. The extraction
was by import graph: every module here reaches nothing domain-specific, and that
is asserted by a test rather than by this sentence.

Apache-2.0.
