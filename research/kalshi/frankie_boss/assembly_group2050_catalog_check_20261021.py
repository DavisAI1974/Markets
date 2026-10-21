"""Disposable focused check for Catalog._verify_restamped (group 2050 class, 2026-10-21).

Usage: /opt/frankie-box/venv/bin/python assembly_group2050_catalog_check_20261021.py <deploy/aws/box dir>
Builds one tiny catalog with the native Writer/seal in a temp dir, exercises the restamp path, removes the dir.
No production path, no scientific model, no box state is touched.
"""
import json, os, pathlib, shutil, sys, tempfile

sys.path.insert(0, sys.argv[1])
import frankie_box_search_catalog as C  # noqa: E402

t = pathlib.Path(tempfile.mkdtemp(prefix='catalog-restamp-check.'))
try:
    path = t / 'g.sqlite'
    ident = dict(schema='CHECK', selection=1, lags=1)
    w = C.Writer(path, ident, [], 'selected_inputs')
    w.db.execute('CREATE TABLE inputs (key TEXT PRIMARY KEY, moves INTEGER, size INTEGER, body BLOB, pin BLOB) WITHOUT ROWID')
    w.db.execute("INSERT INTO inputs VALUES ('k',1,1,x'00',x'00')"); w.db.commit()
    w.seal(dict(n=1))
    receipt = t / 'g.sqlite.json'
    r0 = json.loads(receipt.read_text()); print('sealed stat', r0['stat'])
    # 1 untouched: opens, receipt untouched
    C.Catalog(path, ident); assert json.loads(receipt.read_text()) == r0; print('check1 untouched open: ok')
    # 2 restamped mtime only (what nfsd did to 2050): opens, re-minted, old stat retained
    st = path.stat(); os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns + 65_000_000_000))
    c = C.Catalog(path, ident); r1 = json.loads(receipt.read_text())
    assert r1['stat'] == [st.st_size, st.st_mtime_ns + 65_000_000_000], r1['stat']
    assert r1['stat_superseded'][0]['stat'] == r0['stat'] and r1['sha256'] == r0['sha256'] and c.receipt == r1
    print('check2 restamp re-minted: ok;', r1['stat_superseded'][0]['why'])
    # 3 second open: stat matches, nothing rewritten
    C.Catalog(path, ident); assert json.loads(receipt.read_text()) == r1; print('check3 stable: ok')
    # 4 one byte flipped at equal size: refused, receipt untouched
    b = bytearray(path.read_bytes()); b[-1] ^= 0xFF; path.write_bytes(bytes(b))
    try:
        C.Catalog(path, ident); raise SystemExit('check4 FAILED: corrupt catalog accepted')
    except ValueError as e:
        assert str(e) == 'immutable search catalog changed; retained'; print('check4 corrupt refused: ok')
    assert json.loads(receipt.read_text()) == r1
    # 5 size changed: refused without a digest
    b.append(0); path.write_bytes(bytes(b))
    try:
        C.Catalog(path, ident); raise SystemExit('check5 FAILED: size change accepted')
    except ValueError as e:
        assert str(e) == 'immutable search catalog changed; retained'; print('check5 size change refused: ok')
    print('ALL CHECKS PASSED')
finally:
    shutil.rmtree(t, ignore_errors=True); print('fixture removed', t)
