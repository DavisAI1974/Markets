set -eu
d=$HOME/ng-root-bounded-13eb0f6ab
mkdir -p "$d"
python3 -m venv --without-pip "$d/venv"
curl -fsSL --max-time 30 https://bootstrap.pypa.io/get-pip.py -o "$d/get-pip.py"
"$d/venv/bin/python" "$d/get-pip.py" --no-warn-script-location
"$d/venv/bin/python" -m pip install --disable-pip-version-check 'zstandard==0.25.0' 'databento-dbn==0.62.0' 'numpy<3' 'pytest<10'