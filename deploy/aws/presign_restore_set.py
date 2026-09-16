"""Presign GET links for every object of the uploaded Sunday restore set, for a host with no S3 role rights.

Runs on the workstation with the deployment key. Produces a JSON of {key: url} valid for a few
hours and a PowerShell runner that writes that JSON on the host and invokes the restore script
with --presigned. The links are bearer tokens scoped to GET on these objects until they expire;
they will appear in the SSM command history, which is why the expiry is short. The durable fix
is the read-only bucket policy for the Ssm role in deploy/aws/frankie-native-host/.

    python deploy/aws/presign_restore_set.py --bucket <b> --prefix frankie/sunday_20260915_restore --hours 4 --out-ps1 deploy/aws/_frankie_host_restore_presigned.ps1
"""
import argparse
import json
import os
import re
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bucket', required=True)
    parser.add_argument('--prefix', required=True)
    parser.add_argument('--hours', type=float, default=4.0)
    parser.add_argument('--env-file', default='scratchpad/aws.env')
    parser.add_argument('--out-ps1', required=True)
    args = parser.parse_args()
    for line in open(args.env_file, encoding='utf-8', errors='replace'):
        m = re.match(r'\s*(?:export\s+)?([A-Z_]+)\s*=\s*"?([^"\n]+)"?', line)
        if m and m.group(1).startswith('AWS_'):
            os.environ[m.group(1)] = m.group(2).strip()
    import boto3
    from botocore.config import Config
    # Sign against the bucket's REGIONAL endpoint. A URL signed for the global endpoint gets a 307 to the
    # regional one, where the signed host no longer matches and S3 answers 403 (measured 2026-09-16).
    s3 = boto3.client('s3', region_name='us-east-2', endpoint_url='https://s3.us-east-2.amazonaws.com',
                      config=Config(signature_version='s3v4', s3={'addressing_style': 'virtual'}))
    manifest_key = f'{args.prefix}/UPLOAD_MANIFEST.json'
    manifest_bytes = s3.get_object(Bucket=args.bucket, Key=manifest_key)['Body'].read()
    manifest = json.loads(manifest_bytes)
    keys = [manifest_key] + [e['key'] for e in manifest['entries']]
    expires = int(args.hours * 3600)
    urls = {key: s3.generate_presigned_url('get_object', Params={'Bucket': args.bucket, 'Key': key}, ExpiresIn=expires) for key in keys}
    # Prove one link works unauthenticated, without following redirects, before a host spends time on it.
    import urllib.request
    class _NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *a, **k):
            return None
    with urllib.request.build_opener(_NoRedirect).open(urls[manifest_key], timeout=60) as response:
        if response.status != 200 or response.read() != manifest_bytes:
            raise SystemExit('presigned manifest link did not return the manifest bytes; not writing the runner')
    payload = json.dumps(dict(schema='FRANKIE_SUNDAY_RESTORE_PRESIGNED_V1', bucket=args.bucket, prefix=args.prefix,
                              expires_seconds=expires, urls=urls), separators=(',', ':'))
    ps1 = (
        "$ErrorActionPreference = 'Stop'\n"
        "$git = 'C:\\Program Files\\Git\\cmd\\git.exe'\n"
        "& $git -C C:\\tools\\Markets fetch -q --depth 1 origin ccode/frankie-lawful-recovery-review-20260915\n"
        "& $git -C C:\\tools\\Markets checkout -q --detach FETCH_HEAD\n"
        "Write-Output (\"TOOLS_HEAD=\" + (& $git -C C:\\tools\\Markets rev-parse HEAD))\n"
        "New-Item -ItemType Directory -Force E:\\Codex, C:\\Users\\A\\Documents\\Codex, C:\\restore-stage | Out-Null\n"
        "$json = @'\n" + payload + "\n'@\n"
        "[IO.File]::WriteAllText('C:\\restore-stage\\PRESIGNED.json', $json)\n"
        "$env:PYTHONDONTWRITEBYTECODE = '1'\n"
        "& C:\\Python313\\python.exe C:\\tools\\Markets\\research\\kalshi\\frankie_boss\\operations\\restore_sunday_set_on_host.py "
        f"--bucket {args.bucket} --prefix {args.prefix} --tools C:\\tools\\Markets --receipt E:\\Codex\\RESTORE_RECEIPT_20260916.json "
        "--stage C:\\restore-stage --presigned C:\\restore-stage\\PRESIGNED.json\n"
        "if ($LASTEXITCODE -ne 0) { throw \"restore failed with exit $LASTEXITCODE\" }\n"
        "Remove-Item C:\\restore-stage\\PRESIGNED.json\n"
        "Write-Output (\"VENV=\" + (& E:\\Codex\\Frankie-BOSS-20260915\\actual-host-python\\Scripts\\python.exe -c \"import sys,torch,numpy;print(sys.version.split()[0],torch.__version__,numpy.__version__,torch.get_num_threads())\"))\n"
        "Write-Output (\"SUNDAY_TREE_HEAD=\" + (& $git -C E:\\Codex\\Frankie-BOSS-20260915\\sunday-launch-20260915\\Markets rev-parse HEAD))\n"
        "Write-Output (\"SUNDAY_TREE_CLEAN=\" + ((& $git -C E:\\Codex\\Frankie-BOSS-20260915\\sunday-launch-20260915\\Markets status --porcelain --untracked-files=no | Measure-Object).Count -eq 0))\n"
        "Write-Output (\"RECEIVER_HEAD=\" + (& $git -C 'C:\\Users\\A\\Documents\\Codex\\2026-09-14\\continue-the-frankie-build-in-parallel\\work\\Markets-source' rev-parse HEAD))\n"
        "Write-Output (\"E_FREE_GB=\" + [math]::Round((Get-Volume -DriveLetter E).SizeRemaining / 1GB, 1))\n"
    )
    Path(args.out_ps1).write_text(ps1, encoding='utf-8')
    print(f'presigned {len(urls)} objects for {args.hours} h; runner written to {args.out_ps1} ({len(ps1)} chars; SSM limit is 48k)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
