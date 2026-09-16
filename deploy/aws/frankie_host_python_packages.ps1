$ErrorActionPreference = 'Stop'
# The restored venv (actual-host-python) has include-system-site-packages=true and carries neither torch
# nor numpy: on the workstation both live in the USER site (AppData\Roaming\Python\Python313), which the
# venv archive never contained (found 2026-09-16 when VENV= came back empty after a verified restore).
# Install the exact numeric-identity pins into C:\Python313's site-packages, visible to the venv under
# any user the SSM agent runs as. Wheels: the PyTorch CPU index for torch, PyPI for the rest.
$py = 'C:\Python313\python.exe'
& $py -m pip install --disable-pip-version-check --no-warn-script-location --quiet `
    --index-url https://download.pytorch.org/whl/cpu --extra-index-url https://pypi.org/simple `
    'torch==2.9.1+cpu' 'numpy==2.3.5'
if ($LASTEXITCODE -ne 0) { throw "pip install failed with exit $LASTEXITCODE" }
Write-Output ("SYSTEM=" + (& $py -c "import sys,torch,numpy;print(sys.version.split()[0],torch.__version__,numpy.__version__)"))
Write-Output ("VENV=" + (& E:\Codex\Frankie-BOSS-20260915\actual-host-python\Scripts\python.exe -c "import sys,torch,numpy;print(sys.version.split()[0],torch.__version__,numpy.__version__,torch.get_num_threads(),torch.__file__)"))
