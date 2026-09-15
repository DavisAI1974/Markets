# Historical Granite read-only recovery

Frozen target: GitHub run 34906771361, September 14 2026, 23:00â€“23:45 UTC,
us-east-1, exact `frankie-granite42-ci-34906771361-1` endpoint/config/model.

`granite_recovery.py` collects CloudTrail management events, historical log-group
messages, current descriptions and owned endpoint inventory, quota and price.
STS must match the existing approved account hash before collection. There is no
create, delete, update, invoke, S3 staging, training, order, replay or model loading
operation. API retries are disabled. Pagination is finite, repeated tokens and
truncation stay incomplete; later API errors preserve prior event pages.

The separate workflow runs only when its own workflow path is deliberately pushed
to the integration branch. It uses pinned actions/dependencies, tests without
credentials, grants job credentials only to the collector, and uploads sanitized
results even when sections fail. Existing hosted workflow is unchanged.

CloudTrail queries use one EventSource filter and exact local resource matching.
They omit identity/access-key/IP/user-agent/container-environment fields; preserve
service event name/time/ID, full sanitized error message, response and service
details. Logs and descriptors use the existing diagnostic redaction. Evidence
remains private. No missing log group or event proves a model crash or capacity
failure. Not-found descriptors alone may become `absent`; AccessDenied stays an
error. Missing CloudTrail permission is an explicit access gap, not empty history.

The budget section repeats the original approved compute cap/rate. Current
pricing is separate. Actual billed spend and remaining budget are not established;
no future launch authorization can be inferred. No paid Cost Explorer query is
issued. This collector cannot reconstruct descriptors discarded by the old run.

Sources: [CloudTrail LookupEvents](https://docs.aws.amazon.com/awscloudtrail/latest/APIReference/API_LookupEvents.html)
(last 90 days, one attribute, 50 events/page, 2 requests/s maximum),
[SageMaker DescribeEndpoint](https://docs.aws.amazon.com/sagemaker/latest/APIReference/API_DescribeEndpoint.html).
CloudTrail collection spaces pages by one second. All local verification uses
fakes; actual recovered events/permission outcomes belong in the workflow artifact.
