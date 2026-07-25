from pathlib import Path as _Path
import tarfile as _tarfile
_archive = _Path(__file__).parents[1] / "_v28_execution_patch.txz"
with _tarfile.open(_archive, "r:xz") as _bundle:
    _source = _bundle.extractfile("research/kalshi/tests/test_ng_readiness_v28_execution_chain.py").read()
exec(compile(_source, __file__, "exec"), globals(), globals())
