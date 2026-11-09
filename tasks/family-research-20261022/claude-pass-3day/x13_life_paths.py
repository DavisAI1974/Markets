"""Full-lifecycle per-candidate paths: the same per-second construction as x03 (birth axis, same variables and orientation), extended to boundary k = -60 .. +1260 s from the birth-second boundary,
so that every candidate's whole life (birth, recognition, loss of one-sidedness, flip, empty window) lies inside the matrix.  Nothing is averaged; each row is one candidate.
Usage: OD_SESS=<session> python3 -I x13_life_paths.py     Writes WORK/<SESS>/x13_life_paths.npz  (and a copy for the repo: tables/dipole/<SESS>/instances/x13_life_paths.npz)"""
import os, sys
src = open('x03_birth_paths.py').read().split('\n')
os.environ.setdefault('X03_DRAWS', '1')
exec('\n'.join(src[:94]))
KS = np.arange(-60, 1261)
parts = []
for d, T in tapes.items():
    s = Fs[Fs.tape == d]; parts.append(T.paths(s.pre_ns.to_numpy(np.int64), s.pol.to_numpy(), KS))
P = {v: np.vstack([q[v] for q in parts]) for v in parts[0]}
os.makedirs(f'{TABD}/instances', exist_ok=True)
np.savez_compressed(f'{CW}/x13_life_paths.npz', ks=KS, row=Fs.row.to_numpy(), pol=Fs.pol.to_numpy(), **P)
np.savez_compressed(f'{TABD}/instances/x13_life_paths.npz', ks=KS, row=Fs.row.to_numpy(), pol=Fs.pol.to_numpy(), **P)
print('done', SESS, {k: v.shape for k, v in list(P.items())[:3]})
