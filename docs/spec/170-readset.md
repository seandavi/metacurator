# SPEC 170 — readset: readset identifiers

- Status: drafted
- Determinism: deterministic
- Implements: `src/metacurator/readset.py`
- Related: SPEC 190; nextflow_telemetry `docs/adr/0007-readset-identity.md`

## Purpose

Compute the **readset id** — the identifier the processing pipeline uses for a set of
sequencing runs — from the run list alone, offline, exactly as the control plane computes
it (nextflow_telemetry ADR 0007). Discovery emits readsets keyed by this id.

## Contracts

```python
RUN_ACCESSION = re.compile(r"^[SED]RR\d+$")
UNIT = re.compile(r"^insdc\.sra:[SED]RR\d+$")

def sha512t24u(data: bytes) -> str     # base64url(sha512(data)[:24]); 32 characters
def canonical_json(obj: Any) -> bytes  # RFC 8785 for the JSON this module produces
def insdc_unit(run_accession: str) -> str   # "SRR1" -> "insdc.sra:SRR1"
def readset_id(units: Iterable[str]) -> str # "RS." + 32-char digest
```

## Behavior

The algorithm is [refget Sequence Collections v1.0.0](https://ga4gh.github.io/refget/seqcols/)
encoding steps 1–5 over a schema whose only inherent attribute is `units`:

```python
u = sorted(set(units))                       # a set: dedupe, sort by code point
level1 = {"units": sha512t24u(canonical_json(u))}
readset_id = "RS." + sha512t24u(canonical_json(level1))
```

- `canonical_json` is `json.dumps(obj, separators=(",", ":"), ensure_ascii=False,
  allow_nan=False, sort_keys=True)` encoded as UTF-8. This equals the RFC 8785 JSON
  Canonicalization Scheme for the inputs used here (strings, lists of strings, dicts of
  strings; no numbers), which is all seqcol needs.
- `sha512t24u` is seqcol footnote F3: SHA-512, first 24 bytes, base64url with padding (none
  occurs at 24 bytes).
- `insdc_unit` strips whitespace, requires `RUN_ACCESSION`, prefixes `insdc.sra:`.
- Units are CURIEs; only INSDC run accessions are valid today. Other sources are reserved
  by ADR 0007 and rejected here.
- The id is case-sensitive and may contain `-` and `_`.

## Errors

- `readset_id([])` → `ValueError("readset has no units")`.
- A unit not matching `UNIT` → `ValueError("invalid readset unit: '<x>'")`.
- `insdc_unit` of a non-run accession (e.g. `SRS123`) →
  `ValueError("not an INSDC run accession: '<x>'")`.

## Test cases (golden vectors from ADR 0007)

| input | output |
|---|---|
| `sha512t24u(canonical_json(["chr1","chr2","chr3"]))` | `g04lKdxiYtG3dOGeUC5AdKEifw65G0Wp` (seqcol spec example) |
| `sha512t24u(canonical_json({"names":"g04lKdxiYtG3dOGeUC5AdKEifw65G0Wp","sequences":"rD29ZKmEqwwHRXjiQ36p6UMZQ5hemmsb"}))` | `sjNNwm4zov3Dl0FRWbRTcZwzqrTQKIqL` (seqcol spec example) |
| `readset_id(["insdc.sra:SRR000001"])` | `RS.29BkNp8wxCWwuhVe3luQxYtv97BwdwjF` |
| `insdc.sra:` + ERR478958, ERR478959, ERR478960, ERR478961, ERR480454, ERR480455, ERR480456, ERR480457 | `RS.l29A5uBFtCKLgc-EPvUhj0hD6Q02Z7qj` |
| same eight shuffled, ERR478958 twice | `RS.l29A5uBFtCKLgc-EPvUhj0hD6Q02Z7qj` |
| `insdc.sra:SRR1`, `insdc.sra:ERR2`, `insdc.sra:DRR3` | `RS.uFRI93utvCk3llTO2fQPqARuz-e6Lj_-` |

Plus the three error cases above.

## Open questions

- Unit identifiers for non-INSDC reads (reserved by ADR 0007; to be defined with the storage
  access decision).
