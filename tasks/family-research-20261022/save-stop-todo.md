# Unattended completion and save-before-stop

User authorizes preserving all data, stopping idle research boxes after completion,
and restarting them if needed for issues. This supersedes the earlier prohibition
on lifecycle changes and permits one scoped follow-up for this unattended request.
No AI subagents/chats/messages/orders; Search disks/code stay unchanged.

1. [x] Test exact completion/key coverage, prediction-row validation, archive hash
   verification and refusal to stop on missing/corrupt data. Reuse current helpers.
2. [x] Implement one completion callback per coordinator using Linux pidfd exit
   notification; no polling or numerical coordinator edits/restarts. B/C/D verify
   their existing uploaded archives. A saves final outputs, own retained model
   states/attempts/preprocessing/provenance and references all three remote archives.
3. [x] Verify on Linux with mocked shutdown, then arm callbacks for exact current
   PID/start token/run/assignment/instance. Poweroff only after verified S3 backup
   and local sync. EC2 shutdown behavior already verified as stop on all four.
   Existing Ssm role cannot stop EC2 by API; no IAM change is required.
4. [x] Create one task heartbeat for completion/failure recovery and state checks,
   scoped to these four boxes. Resume only missing work; preserve all evidence.
   Stop/deactivate follow-up after backups and all possible stops are confirmed.
5. [x] Save receipts/handoff, commit and push. Numerical research remains running;
   final semantic coverage stays NOT_PASSED even after numerical completion.

Original EBS volumes, frozen snapshot and S3 artifacts remain retained. No volumes,
snapshots or instances are deleted/terminated to save storage charges.
