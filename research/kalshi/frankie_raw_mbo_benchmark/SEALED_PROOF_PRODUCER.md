# Receiver sealed-absence proof producer

Run from the pinned receiver checkout after staging the actual principal input files:

```powershell
python -m research.kalshi.frankie_raw_mbo_benchmark.native_sealed_absence `
  --prompt <actual-prompt.md> `
  --knowledge-receipt <KNOWLEDGE_RECEIPT.json> `
  --knowledge-bundle <KNOWLEDGE_BUNDLE.md> `
  --delivery-receipt <actual-delivery-receipt.json> `
  --output <runtime-directory-outside-checkout>/sealed-proof.json
```

The producer validates the delivered knowledge against the receiver's frozen corpus,
derives the sealed token set from its registry and source inventory, and scans the
prompt, bundle, knowledge path list, and delivered path list. It records each scanned
surface's SHA-256. It refuses contamination, missing delivered paths, altered knowledge,
or an existing output file. It makes no model call and changes no input.

The proof covers those protocol surfaces. It does not establish absence in the bodies
of every retrieval document referenced by the bundle. Preserve the scanned input files
and deliver their exact bytes; rendering a different prompt requires another scan.

The historical Sunday knowledge bundle cannot currently pass validation against the
new receiver corpus. A passing unit test is not a production admission proof. Stage
the actual compatible knowledge and prompt before invoking this producer for launch.
