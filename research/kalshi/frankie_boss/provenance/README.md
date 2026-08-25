# Supplied Frankie boss checkpoint provenance

`supplied_checkpoint/` is the byte-for-byte artifact set supplied on 2026-08-24/25: 28 chronological
handoff screenshots, both intermediate and authoritative source variants, and the tests that produced
the completed 101-test checkpoint. The executable package one directory above was materialized from:

| Executable file | Supplied source | Supplied SHA-256 |
|---|---|---|
| `causal_packet.py` | `causal_packet.py` | `ea7b7acf43ea2eb03e279acef19b0385dda4a9cd6b3a9e5d53bdab99945e1fc8` |
| `databento_adapter.py` | `databento_adapter.py` | `79ba86199135575aff9fcb686356df07cad242140462449ec7f4a539be7032b9` |
| `decision_contract.py` | `decision_contract(2).py` | `f2c8eb7ba494d490fb42248eeb962f6656c7cd00d5cc30422e9c79fddee2cdfe` |
| `frankie_contract.py` | `frankie_contract.py` | `236eff0c51dc9ef5ca110b2e6febc5f8b1d130360ce6ad5711949d13bdab7bc3` |
| `teacher.py` | `teacher.py` | `d78dc3a839bb09e849e8e3387a3240531f918243071bf38c84f42620dc6e0b43` |
| `trunk.py` | `trunk(2).py` | `2d769713a44ca681991ef2969b0672940dacbaa900730d40dc242a3ce9d665c8` |

The untouched supplied set reproduced `101 passed` before the two continuation slices were applied.
The raw copies remain the comparison authority; executable files are allowed to diverge only through
reviewed continuation commits.

The supplied ReFRAG archive is persisted separately at
`research/refrag/provenance/davisai_refrag_v21_manifests.zip` with SHA-256
`bc2df161ee55c3fe3e65e2071ef2ba87d005d46b1a16fe550c341630d121a26a`. Its 22 manifests parse, and
the archive passes an integrity check. Architecture DOCX/PDF sources and the Nucleus source markdown
are retained under `research/refrag/docs/`.

Checkpoint publication preserves the raw artifact files byte-for-byte. Do not normalize, rename,
delete, or hand-curate them; future executable changes belong outside `supplied_checkpoint/`.
