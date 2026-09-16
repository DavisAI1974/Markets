$ErrorActionPreference = 'Stop'
$git = 'C:\Program Files\Git\cmd\git.exe'
$branch = 'ccode/frankie-lawful-recovery-review-20260915'
New-Item -ItemType Directory -Force C:\tools | Out-Null
if (-not (Test-Path C:\tools\Markets\.git)) {
    & $git clone -q --depth 1 --branch $branch https://github.com/DavisAI1974/Markets.git C:\tools\Markets
}
& $git -C C:\tools\Markets fetch -q --depth 1 origin $branch
& $git -C C:\tools\Markets checkout -q --detach FETCH_HEAD
$head = & $git -C C:\tools\Markets rev-parse HEAD
$count = (Get-ChildItem -Recurse -File C:\tools\Markets\research\kalshi\frankie_boss\sunday_20260915_package | Measure-Object).Count
$script = Test-Path C:\tools\Markets\research\kalshi\frankie_boss\operations\restore_sunday_set_on_host.py
Write-Output "TOOLS_HEAD=$head"
Write-Output "PACKAGE_FILES=$count"
Write-Output "RESTORE_SCRIPT=$script"
