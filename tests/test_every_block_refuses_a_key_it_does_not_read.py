"""Every supplemental block refuses a key it does not read -- the three older ones too.

A misspelled `tolerance`, `loss_margin` or `allow_reset` loaded without error
and was the default: a number nobody chose, which the required `basis` exists
to prevent one level up. `couplings` and `fault_channels` refused an unknown
key; `redundant_groups`, `counters` and `flows` did not, because the first two
take a vertical's own noun beside the format's word, and nobody had said how
an alias joins a closed set.

It joins exactly as it is read. The check asks `_own` what `_member` asks, so a
vertical's own word is accepted where the reader reads it and nowhere else --
and a block naming its members under both spellings, which the reader resolved
by dropping one list without a word, is refused. `flows` names its ends
`input` and `outputs`, nobody's domain word, and has one answer.
"""

from __future__ import annotations

import json

import pytest

from presence_audit import conformance, vocabulary
from presence_audit.supplemental import (ACCEPTED_FORMATS, FORMAT,
                                         MEMBER_KEYS_BY_FORMAT,
                                         SupplementalError, load_supplemental)

GROUP = {"points": ["a", "b"], "basis": "a bench"}
FLOW = {"input": "a", "outputs": ["b"], "basis": "a bench"}
COUNTER = {"point": "c", "basis": "a bench"}


class _Tagged(conformance.ReferenceVocabulary):
    """A vertical whose own word for what it audits is `tag`."""
    noun = ("tag", "tags")


def _load(tmp_path, fmt=FORMAT, **blocks):
    path = tmp_path / "declarations.json"
    path.write_text(json.dumps({"format": fmt, "provenance": "a bench",
                                **blocks}))
    return load_supplemental(path)


class TestAMisspelledKeyIsRefused:

    @pytest.mark.parametrize("block, entry, typo", [
        ("redundant_groups", GROUP, "tolerence"),
        ("flows", FLOW, "loss_margn"),
        ("counters", COUNTER, "alow_reset"),
    ])
    def test_it_is_refused_naming_what_the_block_reads(self, tmp_path, block,
                                                       entry, typo):
        with pytest.raises(SupplementalError, match=typo) as raised:
            _load(tmp_path, **{block: [dict(entry, **{typo: 0.2})]})
        assert "this block does not read" in str(raised.value)


class TestEveryKeyABlockReadsStillLoads:

    def test_a_fully_declared_file_loads_with_every_number_applied(self, tmp_path):
        loaded = _load(
            tmp_path,
            redundant_groups=[dict(GROUP, tolerance=0.1)],
            flows=[dict(FLOW, loss_margin=0.2)],
            counters=[dict(COUNTER, direction="increasing", allow_reset=False)])
        assert (loaded.redundant_groups[0].tolerance, loaded.flows[0].loss_margin,
                loaded.counters[0].allow_reset) == (0.1, 0.2, False)

    @pytest.mark.parametrize("fmt", ACCEPTED_FORMATS)
    def test_every_format_reads_its_own_member_word(self, tmp_path, fmt):
        plural, singular = MEMBER_KEYS_BY_FORMAT[fmt]
        loaded = _load(tmp_path, fmt,
                       redundant_groups=[{plural: ["a", "b"], "basis": "x"}],
                       counters=[{singular: "c", "basis": "x"}])
        assert loaded.redundant_groups[0].points == ("a", "b")
        assert loaded.counters[0].point == "c"


class TestAnAliasJoinsTheSetExactlyAsItIsRead:

    def test_a_verticals_own_word_is_read(self, tmp_path):
        with vocabulary.using(_Tagged()):
            loaded = _load(tmp_path,
                           redundant_groups=[{"tags": ["a", "b"], "basis": "x"}],
                           counters=[{"tag": "c", "basis": "x"}])
        assert loaded.redundant_groups[0].points == ("a", "b")
        assert loaded.counters[0].point == "c"

    def test_another_verticals_word_is_refused(self, tmp_path):
        with vocabulary.using(_Tagged()), pytest.raises(
                SupplementalError, match="accounts"):
            _load(tmp_path, redundant_groups=[
                {"accounts": ["a", "b"], "basis": "x"}])

    def test_both_spellings_at_once_is_refused(self, tmp_path):
        """The reader took the vertical's word and dropped the other list --
        the one the published documentation told the author to write."""
        with vocabulary.using(_Tagged()), pytest.raises(
                SupplementalError, match="both"):
            _load(tmp_path, redundant_groups=[
                {"tags": ["a", "b"], "points": ["c", "d"], "basis": "x"}])


class TestTheSetsAreWhatEachBlockLoopReads:
    """Derived from the loader's source, in both directions: a key a block's
    loop reads and its set lacks is refused on every file, and a key in the
    set that the loop never reads is the silent drop this check removes. The
    member keys are read through `_member` and join by `_member_keys`."""

    @pytest.mark.parametrize("name, declared", [
        ("redundant_groups", "REDUNDANT_GROUP_KEYS"),
        ("counters", "COUNTER_KEYS"),
        ("flows", "FLOW_KEYS"),
    ])
    def test_each_set_is_its_loop(self, name, declared):
        import ast
        import inspect

        from presence_audit import supplemental as module

        tree = ast.parse(inspect.getsource(module.load_supplemental))
        loops = [node for node in ast.walk(tree) if isinstance(node, ast.For)
                 and name in ast.unparse(node.iter)]
        assert len(loops) == 1, f"found {len(loops)} loops over {name}"
        read = set()
        for node in ast.walk(loops[0]):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if (isinstance(func, ast.Attribute) and func.attr == "get"
                    and isinstance(func.value, ast.Name)
                    and func.value.id == "block"):
                read.add(node.args[0].value)
            if (isinstance(func, ast.Name)
                    and func.id in ("_require", "_require_named")
                    and len(node.args) > 1
                    and isinstance(node.args[1], ast.Constant)):
                read.add(node.args[1].value)
        assert read == set(getattr(module, declared))
