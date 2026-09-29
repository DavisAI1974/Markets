# Install DuckDB into the box venv for the experiment's search (Greg, 2026-09-29: "I added duck db"). A BOX CHANGE:
# dispatch only on Greg's go. Pinned: duckdb 1.5.5 with its extension packages from PyPI (json, parquet, sqlite_scanner,
# httpfs; the extension server extensions.duckdb.org may be unreachable, so each extension is installed from the file its
# PyPI package carries), plus pyarrow. ACTION=check (read-only: what is installed) or ACTION=install.
set -eu
PY=/opt/frankie-box/venv/bin/python
case "${ACTION:-check}" in
  check) ;;
  install)
    "$PY" -m pip install --no-cache-dir duckdb==1.5.5 duckdb-extension-json==1.5.5 duckdb-extension-parquet==1.5.5 \
      duckdb-extension-sqlite-scanner==1.5.5 duckdb-extension-httpfs==1.5.5 pyarrow
    "$PY" - <<'PY'
import duckdb, glob, os, site
con = duckdb.connect()
paths = [p for d in site.getsitepackages() for p in glob.glob(os.path.join(d, 'duckdb_extension_*', '**', '*.duckdb_extension'), recursive=True)]
for p in sorted(paths):
    con.execute("INSTALL '%s'" % p)
    print('installed', os.path.basename(p))
PY
    ;;
  *) echo "ACTION must be check or install" >&2; exit 2;;
esac
"$PY" - <<'PY'
import importlib
for name in ('duckdb', 'pyarrow', 'numpy', 'scipy'):
    try:
        m = importlib.import_module(name)
        print(name, getattr(m, '__version__', '?'))
    except ImportError:
        print(name, 'NOT INSTALLED')
try:
    import duckdb
    con = duckdb.connect()
    for ext in ('json', 'parquet', 'sqlite', 'httpfs'):
        try:
            con.execute('LOAD ' + ext); print('extension', ext, 'loads')
        except Exception as error:
            print('extension', ext, 'does not load:', str(error)[:120])
except ImportError:
    pass
PY
