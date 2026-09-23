"""Build an explicit WAIT-bound native readiness delivery script, without credentials."""
import argparse
import base64
import json
import importlib.util
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location('workflow_delivery_builder',
    ROOT/'research/kalshi/frankie_boss/operations/workflow_delivery.py')
delivery = importlib.util.module_from_spec(spec)
spec.loader.exec_module(delivery)
DELIVERED, validate_context = delivery.DELIVERED, delivery.validate_context


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--readiness', required=True)
    parser.add_argument('--context-json', required=True)
    parser.add_argument('--out', required=True)
    args = parser.parse_args()
    context = validate_context(json.loads(args.context_json))
    encoded = base64.b64encode(args.context_json.encode()).decode()
    lines = ["$ErrorActionPreference = 'Stop'",
             "$contextEncoded = '" + encoded + "'",
             "$context = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($contextEncoded)) | ConvertFrom-Json",
             "$tool = Join-Path $context.tools_root 'research/kalshi/frankie_boss/operations/workflow_delivery.py'",
             "$env:PYTHONPATH = $context.tools_root",
             "$env:PYTHONDONTWRITEBYTECODE = '1'",
             "$verifiedLines = & $context.python $tool --context-base64 $contextEncoded --kind validate",
             "if ($LASTEXITCODE -ne 0) { throw 'delivery context refused before payload placement' }",
             "$verified = ($verifiedLines | Select-Object -Last 1) | ConvertFrom-Json",
             "if ($verified.status -ne 'delivery_context_verified') { throw 'exact delivery validation result required' }",
             "$payload = Join-Path $verified.run_directory ('workflow-deliveries/incoming-readiness-' + [guid]::NewGuid().ToString('N'))",
             "New-Item -ItemType Directory -Path $payload | Out-Null"]
    for name in DELIVERED:
        raw = (Path(args.readiness)/name).read_bytes()
        lines.append("[IO.File]::WriteAllBytes((Join-Path $payload '" + name + "'), [Convert]::FromBase64String('" + base64.b64encode(raw).decode() + "'))")
    lines += ["& $context.python $tool --context-base64 $contextEncoded --kind readiness --payload $payload",
              "if ($LASTEXITCODE -ne 0) { throw 'readiness delivery refused; payload retained' }"]
    Path(args.out).write_text('\n'.join(lines)+'\n', encoding='ascii')


if __name__ == '__main__':
    main()
