$ErrorActionPreference = 'Continue'
$aws = 'C:\Program Files\Amazon\AWSCLIV2\aws.exe'
Write-Output "IDENTITY=$(& $aws sts get-caller-identity --query Arn --output text 2>&1)"
Write-Output "--- s3 ls WITHOUT region:"
& $aws s3 ls s3://bento-568968024170-us-east-2-an/frankie/sunday_20260915_restore/ 2>&1 | Select-Object -First 4
Write-Output "--- s3 ls WITH --region us-east-2:"
& $aws s3 ls s3://bento-568968024170-us-east-2-an/frankie/sunday_20260915_restore/ --region us-east-2 2>&1 | Select-Object -First 4
Write-Output "--- head manifest WITH region:"
& $aws s3api head-object --bucket bento-568968024170-us-east-2-an --key frankie/sunday_20260915_restore/UPLOAD_MANIFEST.json --region us-east-2 --query ContentLength --output text 2>&1
Write-Output "--- configured region: [$env:AWS_DEFAULT_REGION] [$env:AWS_REGION]"
