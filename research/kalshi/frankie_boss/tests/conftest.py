"""Pin the bare-name module resolution these suites rely on.

The suites run with the frankie_boss directory on PYTHONPATH and several modules
fall back to bare imports (``from forecast_contract import sha256_digest``) when
loaded outside the package. pytest's prepend import mode imports
``frankie_boss/__init__.py`` as the package ``frankie_boss`` at the first test's
setup and puts ``research/kalshi`` at the front of ``sys.path`` from then on, so
a bare ``forecast_contract`` imported lazily inside a test resolves to
``research/kalshi/forecast_contract.py``, a different module without
``sha256_digest``. That is the only name shared by the two directories. Cache the
intended module at collection time, before the package import reorders the path.
"""
import pathlib
import sys

PACKAGE_DIR = pathlib.Path(__file__).resolve().parent.parent
if str(PACKAGE_DIR) not in sys.path:
    sys.path.insert(0, str(PACKAGE_DIR))
import forecast_contract  # noqa: E402,F401

assert pathlib.Path(forecast_contract.__file__).resolve().parent == PACKAGE_DIR, forecast_contract.__file__
