Stage 5 can declare `host_runtime.pod_credential_ssm` with three nonsecret fields:
`name` (the SecureString parameter name), `region`, and `trigger_directory`.
The host role needs `ssm:GetParameter` for that name and `kms:Decrypt` if a customer
KMS key protects it. The Python process retrieves and validates the key once,
after its first readiness trigger, caches it privately across cycles, and releases
the reference on close. It never writes it or passes it to subprocesses.

After the retained Granite observer publishes actual readiness for an admitted
request, write its public trigger immutably at
`<trigger_directory>/<request_id>/FRANKIE_ACTUAL_EXECUTE_V1.json`:

```json
{"schema":"FRANKIE_ACTUAL_EXECUTE_V1","readiness_directory":"<host readiness directory>","service_pins_sha256":"<sha256 of service-pins.json>"}
```

Same-job recovery uses `FRANKIE_ACTUAL_RESUME_JOB_V1.json` in that request directory,
with `schema`, `request_id`, and `service_pins_sha256`. No trigger contains a key.
The existing request, startup, host instance and service witness checks still run.
Without this optional configuration the original bounded stdin protocol applies.
An absent trigger waits; it never authorizes a new job or Pod start. This bridge
does not create readiness evidence or replace the independent observer.

API reference: https://docs.aws.amazon.com/boto3/latest/reference/services/ssm/client/get_parameter.html
