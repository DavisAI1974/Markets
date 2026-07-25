from pathlib import Path as _Path
import tarfile as _tarfile
_archive = _Path(__file__).parent / "_v28_execution_patch.txz"
with _tarfile.open(_archive, "r:xz") as _bundle:
    _source = _bundle.extractfile("research/kalshi/ng_historical_refinement_preflight_v24.py").read()
exec(compile(_source, __file__, "exec"), globals(), globals())
