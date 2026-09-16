$ErrorActionPreference = 'Stop'
$git = 'C:\Program Files\Git\cmd\git.exe'
# Refresh the tools checkout to the branch tip so the restore script is the committed one.
& $git -C C:\tools\Markets fetch -q --depth 1 origin ccode/frankie-lawful-recovery-review-20260915
& $git -C C:\tools\Markets checkout -q --detach FETCH_HEAD
Write-Output ("TOOLS_HEAD=" + (& $git -C C:\tools\Markets rev-parse HEAD))
New-Item -ItemType Directory -Force E:\Codex, C:\Users\A\Documents\Codex, C:\restore-stage | Out-Null
$env:PYTHONDONTWRITEBYTECODE = '1'
& C:\Python313\python.exe C:\tools\Markets\research\kalshi\frankie_boss\operations\restore_sunday_set_on_host.py `
    --bucket bento-568968024170-us-east-2-an --prefix frankie/sunday_20260915_restore `
    --tools C:\tools\Markets --receipt E:\Codex\RESTORE_RECEIPT_20260916.json --stage C:\restore-stage
if ($LASTEXITCODE -ne 0) { throw "restore failed with exit $LASTEXITCODE" }
# Independent checks after the restore: the venv answers with the bound toolchain; the receiver is at its commit and clean.
Write-Output ("VENV=" + (& E:\Codex\Frankie-BOSS-20260915\actual-host-python\Scripts\python.exe -c "import sys,torch,numpy;print(sys.version.split()[0],torch.__version__,numpy.__version__,torch.get_num_threads())"))
Write-Output ("RECEIVER_HEAD=" + (& $git -C 'C:\Users\A\Documents\Codex\2026-09-14\continue-the-frankie-build-in-parallel\work\Markets-source' rev-parse HEAD))
Write-Output ("RECEIVER_CLEAN=" + ((& $git -C 'C:\Users\A\Documents\Codex\2026-09-14\continue-the-frankie-build-in-parallel\work\Markets-source' status --porcelain --untracked-files=no | Measure-Object).Count -eq 0))
Write-Output ("SUNDAY_TREE_HEAD=" + (& $git -C E:\Codex\Frankie-BOSS-20260915\sunday-launch-20260915\Markets rev-parse HEAD))
Write-Output ("SUNDAY_TREE_CLEAN=" + ((& $git -C E:\Codex\Frankie-BOSS-20260915\sunday-launch-20260915\Markets status --porcelain --untracked-files=no | Measure-Object).Count -eq 0))
Write-Output ("E_FREE_GB=" + [math]::Round((Get-Volume -DriveLetter E).SizeRemaining / 1GB, 1))
