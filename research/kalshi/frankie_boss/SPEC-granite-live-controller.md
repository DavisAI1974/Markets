# Synthetic live Granite controller fixture

`granite_live_controller.py` prepares and runs a small software integration probe
through the existing native controller and SageMaker service. It is not a Frankie
agent launcher or a fitted forecast, calibration, throughput or trading test.

`prepare_fixture(new_directory)` freezes one complete synthetic PROBE_ONLY source
row, the actual random native/decoder state, three toy target sessions, request,
causal context and complete compact prompt. Preparation makes no model forward or
provider call. Source and request identities are computed from the retained bytes.

`measure_fixture(fixture, verified_tokenizer_directory, output_tokens=1200)` requires
the selected image's transformers 5.8.0/tokenizers 0.22.2 and exactly eight pinned
tokenizer/config/template files. It applies the actual single-user template with
thinking disabled, retains complete token IDs and admits input plus output against
the positional limit without truncation. This has unit coverage with a test
tokenizer; real tokenizer measurement remains an operational prerequisite.

`identity_from_runtime(startup, admission)` binds the measured tokenizer and current
compact parser to a startup receipt. Its caller MUST first validate that complete
receipt against the pinned image, mounted artifact manifest, bootstrap sources,
runtime versions and actual resource descriptions. Collection from CloudWatch alone
does not perform all those comparisons. Generate source-dependent pins on the same
Linux checkout used for bootstrap staging, not from Windows working-copy hashes.

`run_fixture(...)` refuses changed request/source/context/file/prompt identities and
requires measured admission for the real client. It uses the existing SageMaker
service and FrankieForecastController, counts exactly three native forwards and
one provider invocation, then reopens trusted journals and proves an identical
retry makes no further calls. It preserves actual complete/incomplete outcomes,
wire requests and controller/native receipts. Provider input token usage must
equal the independent measurement for a complete live integration result.

The resource lifecycle is separate in `granite_deployment.py`. A coordinator/CI
workflow still needs to join staging verification, preparation, real measurement,
bounded deployment, full runtime admission, this helper and confirmed cleanup.
Use Python finally and an independent CI always cleanup step. No such hosted run
has completed as of this commit, and no unit-test identity is a runtime identity.

Validation: 12 focused tests passed before documentation. Independent review also
exercised HTML, non-object JSON and malformed usage responses: retained evidence,
incomplete integration, three native/one provider call and zero-work retry. These
are synthetic SDK tests, not real Granite calls.
