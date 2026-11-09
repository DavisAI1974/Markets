# Pending artifact publication

Research outputs are preserved locally under `E:\Markets-native-dipole-agent-pass\agent-pass`. Ccode owns the three-tier repository layout; its output destination paths and immutable-version conventions have not been supplied to this pass. The supplied markets-data repository is used only for verified inputs. No AWS/S3 or alternate output repository was used.

- Generated local artifacts: 551 files, 232,390,109 bytes.
- Local inventory: `agent-pass/cache/pending-publication-manifest.json`.
- Inventory SHA256: `d896e1535383542ed4980fec139b2319e665688d005957265b0b124039d32738`.
- Pinned source blobs in the inventory: 21; locally present: 21.
- Sizes are measured only from present files. Missing local sources are explicit nulls, never zero; the inventory does not fetch Git objects.

The inventory records SHA256 and byte size for each CSV, compressed observation table, chart, workbook and receipt, plus each pinned source revision/path/hash and its local cache coordinate. It is an inventory pending routing, not an assertion that a destination manifest has been created.

Already-published pre-policy artifacts are listed by commit and path family in PROGRESS.md. No published history was rewritten. Since the policy change only code, Markdown and references have been staged. Original tracked generated artifacts now have intentional unstaged local updates; preserve them for the data-repository handoff.

After Ccode supplies the configured layout, publish from these local files using its conventions, verify read-back hashes, and replace local-only references with actual immutable destination versions. Do not create a duplicate tier layout or copy the artifacts into another Markets commit.
