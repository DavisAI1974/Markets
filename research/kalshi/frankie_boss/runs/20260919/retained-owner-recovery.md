# Retained Pod ownership recovery — 2026-09-17

The September 15 readiness owner was still active for request ec1bd4c34cd27a654b05e2811f892f4d2fe1aa44e6b5dc919cd972709cea92e2 and startup 0cd700390f3f37c758fba82b80a7b0d904f5d229540283abe6ce26ba8c0e0dc0. No completion marker was present in its migration journal.

Read-only inspection of the original AWS host's durable critic spool verified an actual HTTP 200 terminal model response, finish_reason stop, exact dispatch binding, job f48d89b647344eb0c95f31c0d7252d818d970bb60284d9219c6bb360278a938e, and backend response SHA256 276e0536a0189bfcaeb606fa0cb1c68df69b9c53b93c343270778b09e3e7d6c6. The saved native publication intent pins code 91e600fe58a0a55782393f1fbbd52ef7df275f8a.

The original publication workflow failed because its checkout and migrated Pod routing differed from the actual saved intent. Recovery workflow [35189910648](https://github.com/DavisAI1974/Markets/actions/runs/35189910648) used separate exact native and reviewed publisher checkouts and the explicitly selected historical journal generation. It published the matching completed-outcome and finished records successfully.

The original owner's conditional active→stopping transition preceded one Runpod stop action. That action returned Pod ycf4v6lmave6xw with status EXITED. Exact stop acknowledgement and confirmed cleanup were saved and read back in the original journal, then conditional stopping→closed released the same startup owner. Mounted data was retained. This was completion cleanup, not an elapsed timeout.

No completion or classroom success is claimed for the new two-cycle run. Its readiness witness must contain exactly request_sha256, host_instance_id and admitted_at; a prior observer supplied the whole host-ready record and was rejected before startup. The current witness uses host instance 0f7e5d5c39ec4db1a885b0b535165110. The rejected observer was cancelled after confirming that it had never persisted startup intent.

Both AWS ingest and native machines remain running. No new files were written on the operator's PC.
