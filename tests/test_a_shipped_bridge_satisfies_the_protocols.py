"""A really shipped bridge satisfies the protocols -- not only a fixture.

The sibling file adapts a foreign shape written here out of dictionaries. That
proves the protocol survives a shape its author did not derive it from, and it
proves it against something its author still wrote. This file adapts the types of
an INDEPENDENTLY PUBLISHED bridge, which is the claim no fixture can make.

WHY IT SKIPS. That bridge depends on this package, not the other way round, so
this distribution declares nothing about it and a clean clone will not have it.
The import used to sit at module scope in the sibling file and took the whole
file down with it -- including checks that need no bridge at all. Here the skip
costs exactly this file and nothing else.

A SKIP IS NOT A PASS. CI installs the bridge and then asserts the suite reported
no skips, so this file running is a fact about the run rather than a hope. If you
see it skipped locally, it did not check anything.

The member lists are DERIVED from the protocol classes rather than typed, so a
protocol that grows a member is driven here on the next run without an edit. The
sibling file keeps the hand-written lists and asserts they equal the same
surface -- between them, a new member is both exercised and noticed.
"""

from __future__ import annotations

import pytest

from presence_audit import protocols as P

pytest.importorskip(
    "bmc_sensor_audit",
    reason="this file adapts a published bridge's own types; install "
           "bmc-sensor-audit to run it. CI does, and asserts it did not skip")

from bmc_sensor_audit.inventory.entity_manager import Declaration, DeclaredSensor  # noqa: E402
from bmc_sensor_audit.inventory.redfish import LiveSensor, Walk                    # noqa: E402


def _members(protocol) -> tuple:
    """Every member the protocol declares, read off the class."""
    return tuple(sorted(n for n in vars(protocol) if not n.startswith("_")))


CAPTURE_MEMBERS = _members(P.Capture)
POINT_MEMBERS = _members(P.CapturedPoint)
DECLARATION_MEMBERS = _members(P.DeclarationSource)
DECLARED_MEMBERS = _members(P.DeclaredPoint)


def _drive(subject, members) -> dict:
    """Read every declared member. A member that raises fails here, by name."""
    seen = {}
    for member in members:
        try:
            seen[member] = getattr(subject, member)
        except Exception as error:               # noqa: BLE001
            raise AssertionError(
                f"{type(subject).__name__}.{member} raised: "
                f"{type(error).__name__}: {error}") from error
    return seen


# --------------------------------------------------------------------------
# The shipped bridge's shapes, adapted onto the neutral protocols.
# They were THIS package's shapes once. They stopped being so at the split,
# and the sentence calling them that outlived the move by a release.
# --------------------------------------------------------------------------

class _BmcPoint:
    def __init__(self, sensor: LiveSensor):
        self._s = sensor

    name = property(lambda self: self._s.name)
    path = property(lambda self: self._s.path)
    reading = property(lambda self: self._s.reading)
    is_reading = property(lambda self: self._s.is_reading)
    state = property(lambda self: self._s.state)
    thresholds = property(lambda self: self._s.thresholds)
    units = property(lambda self: self._s.units)
    is_enabled = property(lambda self: self._s.is_enabled)


class _BmcCapture:
    def __init__(self, walk: Walk):
        self._w = walk

    points = property(lambda self: [_BmcPoint(s) for s in self._w.sensors])
    captured_at = property(lambda self: self._w.captured_at)
    complete = property(lambda self: self._w.complete)
    errors = property(lambda self: self._w.errors)


class _BmcDeclared:
    def __init__(self, sensor: DeclaredSensor):
        self._d = sensor

    name = property(lambda self: self._d.name)
    type = property(lambda self: self._d.type)
    display_name = property(lambda self: self._d.display_name)
    source = property(lambda self: self._d.source)
    expects_reading = property(lambda self: self._d.expects_reading)
    disabled = property(lambda self: self._d.disabled_in_config)
    thresholds = property(lambda self: self._d.thresholds)
    is_templated = property(lambda self: self._d.is_templated)


class _BmcDeclaration:
    def __init__(self, declaration: Declaration):
        self._d = declaration

    points = property(lambda self: [_BmcDeclared(s) for s in self._d.sensors])
    sources = property(lambda self: self._d.sources)
    anomalies = property(lambda self: self._d.anomalies)
    unreadable = property(lambda self: self._d.unreadable)


class TestAShippedBridgeSatisfiesTheProtocols:
    def test_its_capture_drives_every_member(self):
        walk = Walk(sensors=[
            LiveSensor(name="Inlet", path="/redfish/v1/a", reading=21.0, state="Enabled"),
            LiveSensor(name="Dead", path="/redfish/v1/b", reading=None, state="Enabled"),
        ])
        capture = _BmcCapture(walk)
        _drive(capture, CAPTURE_MEMBERS)
        points = list(capture.points)
        assert len(points) == 2, "the adapter yielded nothing; the drive was vacuous"
        for point in points:
            _drive(point, POINT_MEMBERS)

    def test_its_declaration_drives_every_member(self):
        decl = Declaration(sensors=[
            DeclaredSensor(name="Inlet", type="Temperature", label=None,
                           record=None, source="entity-manager"),
        ])
        source = _BmcDeclaration(decl)
        _drive(source, DECLARATION_MEMBERS)
        points = list(source.points)
        assert len(points) == 1, "the adapter yielded nothing; the drive was vacuous"
        for point in points:
            _drive(point, DECLARED_MEMBERS)



    def test_the_drive_was_not_vacuous(self):
        """Non-vacuity for the two above: they iterate the member lists, and a
        list that came back empty would drive nothing and pass."""
        for members in (CAPTURE_MEMBERS, POINT_MEMBERS,
                        DECLARATION_MEMBERS, DECLARED_MEMBERS):
            assert len(members) >= 4, members
