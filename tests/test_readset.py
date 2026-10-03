"""readset tests (SPEC 170) — golden vectors shared with nextflow_telemetry ADR 0007."""

from __future__ import annotations

import pytest

from metacurator.readset import canonical_json, insdc_unit, readset_id, sha512t24u

ZELLER_RUNS = [
    "ERR478958", "ERR478959", "ERR478960", "ERR478961",
    "ERR480454", "ERR480455", "ERR480456", "ERR480457",
]


def test_seqcol_spec_examples():
    assert sha512t24u(canonical_json(["chr1", "chr2", "chr3"])) == (
        "g04lKdxiYtG3dOGeUC5AdKEifw65G0Wp"
    )
    level1 = {
        "names": "g04lKdxiYtG3dOGeUC5AdKEifw65G0Wp",
        "sequences": "rD29ZKmEqwwHRXjiQ36p6UMZQ5hemmsb",
    }
    assert sha512t24u(canonical_json(level1)) == "sjNNwm4zov3Dl0FRWbRTcZwzqrTQKIqL"


def test_single_run():
    assert readset_id(["insdc.sra:SRR000001"]) == "RS.29BkNp8wxCWwuhVe3luQxYtv97BwdwjF"


def test_zeller_sample_is_order_and_duplicate_insensitive():
    units = [insdc_unit(r) for r in ZELLER_RUNS]
    expected = "RS.l29A5uBFtCKLgc-EPvUhj0hD6Q02Z7qj"
    assert readset_id(units) == expected
    shuffled = [units[i] for i in (5, 0, 7, 2, 1, 6, 3, 4)] + [units[0]]
    assert readset_id(shuffled) == expected


def test_mixed_archives_sorted_by_code_point():
    units = ["insdc.sra:SRR1", "insdc.sra:ERR2", "insdc.sra:DRR3"]
    assert readset_id(units) == "RS.uFRI93utvCk3llTO2fQPqARuz-e6Lj_-"


def test_errors():
    with pytest.raises(ValueError, match="no units"):
        readset_id([])
    with pytest.raises(ValueError, match="invalid readset unit"):
        readset_id(["SRR1"])
    with pytest.raises(ValueError, match="not an INSDC run accession"):
        insdc_unit("SRS123")
    assert insdc_unit(" SRR7 ") == "insdc.sra:SRR7"
