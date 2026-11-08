import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { scanProject } from './scan.js';

const publicDir = fileURLToPath(new URL('../public/', import.meta.url));
const ASSETS = { '/': ['index.html', 'text/html'], '/app.js': ['app.js', 'text/javascript'], '/guide-tasks.js': ['guide-tasks.js', 'text/javascript'], '/styles.css': ['styles.css', 'text/css'] };
const LOOPBACK_HOSTS = new Set(['localhost', '127.0.0.1', '[::1]', '::1']);
const SIGNAL_IGNORE = new Set(['.git', 'node_modules', 'dist', 'build', 'coverage', '.next', '.cache', '.venv', 'venv', '__pycache__', 'target', 'vendor']);
const DEFAULT_TTL_MS = 5000;

// Result cache TTL. BUILDMAP_SCAN_TTL_MS overrides the 5000 ms default; 0
// disables caching (every request scans).
export function scanTtlMs(env = process.env) {
  const value = env.BUILDMAP_SCAN_TTL_MS;
  return value !== undefined && /^[0-9]{1,9}$/.test(String(value).trim()) ? Number(value) : DEFAULT_TTL_MS;
}

// The Host header must name this machine's loopback interface (any port) unless
// the operator bound an explicit host. Everything else is misdirected (421),
// which blocks DNS-rebinding style requests from a browser tab on another origin.
export function hostAllowed(header) {
  if (typeof header !== 'string' || !header) return false;
  const name = header.startsWith('[') ? header.slice(0, header.indexOf(']') + 1) : header.split(':')[0];
  return LOOPBACK_HOSTS.has(name.toLowerCase());
}

export function startServer({ root, source = null, host = '127.0.0.1', port = 4173, scan = scanProject, ttlMs = scanTtlMs(), hostCheck = true }) {
  const rootHash = crypto.createHash('sha256').update(root).digest('hex').slice(0, 12);
  const cache = { map: null, signal: null, at: 0, inFlight: null, mode: null };
  // One scan at a time: concurrent requests share the in-flight promise, and a
  // result is reused while the cheap change signal (git HEAD + status with file
  // stats, or a tracked-file mtime walk) is unchanged and the TTL has not passed.
  function currentMap() {
    if (cache.inFlight) return cache.inFlight;
    const signal = ttlMs > 0 ? changeSignal(root) : null;
    cache.mode = signal?.mode || cache.mode;
    if (cache.map && signal && signal.value === cache.signal && Date.now() - cache.at < ttlMs) return Promise.resolve(cache.map);
    cache.inFlight = Promise.resolve().then(() => scan(root, { source })).then(map => {
      if (signal) { cache.map = map; cache.signal = signal.value; cache.at = Date.now(); }
      return map;
    }).finally(() => { cache.inFlight = null; });
    return cache.inFlight;
  }
  const server = http.createServer(async (req, res) => {
    try {
      if (!['GET', 'HEAD'].includes(req.method)) {
        res.setHeader('allow', 'GET, HEAD');
        return json(res, { error: 'Method not allowed' }, 405);
      }
      if (hostCheck && !hostAllowed(req.headers.host)) return json(res, { error: 'Misdirected request: this BuildMap server answers only loopback Host names (localhost, 127.0.0.1, [::1]). Start it with an explicit --host to serve another name.' }, 421);
      const url = new URL(req.url || '/', 'http://localhost');
      if (url.pathname === '/api/health') return json(res, { ok: true, project: path.basename(root), rootHash, cache: { ttlMs, changeSignal: cache.mode || changeSignal(root)?.mode || null } });
      if (url.pathname === '/api/map') return json(res, await currentMap());
      if (url.pathname === '/api/gaps') {
        const map = await currentMap();
        return json(res, { project: map.project, gaps: map.gaps, diagnostics: map.diagnostics, fingerprint: map.fingerprint, generatedAt: map.generatedAt });
      }
      const asset = ASSETS[url.pathname];
      if (!asset) return json(res, { error: 'Not found' }, 404);
      const content = fs.readFileSync(path.join(publicDir, asset[0]));
      res.writeHead(200, { 'content-type': `${asset[1]}; charset=utf-8`, 'cache-control': 'no-store', 'x-content-type-options': 'nosniff' });
      res.end(content);
    } catch (err) {
      console.error('BuildMap request failed:', err.message);
      json(res, { error: 'Could not read the current project. Retry after checking its path and permissions.' }, 500);
    }
  });
  server.listen(port, host, () => {
    console.log(`BuildMap watching: ${root}`);
    console.log(`Open: http://${host.includes(':') ? `[${host}]` : host}:${server.address().port}`);
  });
  return server;
}

// A cheap signal that changes whenever the mapped tree changes. Git mode hashes
// HEAD plus every status entry with that file's size and mtime (so a second
// edit of an already-modified file still registers); otherwise every regular
// file under the root (minus the standard ignored directories) is stat'ed.
// Returns null when no signal can be computed, which disables caching.
export function changeSignal(root) {
  const h = crypto.createHash('sha256');
  const git = args => spawnSync('git', ['-c', 'core.fsmonitor=false', '-C', root, ...args], { encoding: 'utf8', timeout: 5000, maxBuffer: 16 * 1024 * 1024, env: { ...process.env, LC_ALL: 'C' } });
  const top = git(['rev-parse', '--show-toplevel']);
  if (top.status === 0) {
    const toplevel = top.stdout.trim();
    const head = git(['rev-parse', '--verify', '--quiet', 'HEAD']);
    const status = git(['status', '--porcelain', '-z', '--untracked-files=all', '--', '.']);
    if (status.status === 0) {
      h.update(`git:${head.status === 0 ? head.stdout.trim() : 'unborn'}\0`);
      for (const entry of status.stdout.split('\0').filter(Boolean)) {
        h.update(entry); h.update('\0');
        try { const st = fs.statSync(path.join(toplevel, entry.slice(3)), { bigint: true }); h.update(`${st.size}:${st.mtimeNs}\0`); } catch { h.update('absent\0'); }
      }
      // .buildmap/* may be gitignored but still drives the map: stat it directly.
      walkSignal(path.join(root, '.buildmap'), h, 2000);
      return { mode: 'git', value: h.digest('hex') };
    }
  }
  try { walkSignal(root, h, 200000); return { mode: 'mtime', value: h.digest('hex') }; } catch { return null; }
}

function walkSignal(dir, h, budget) {
  const stack = [dir];
  let seen = 0;
  while (stack.length) {
    const current = stack.pop();
    let entries;
    try { entries = fs.readdirSync(current, { withFileTypes: true }); } catch { continue; }
    for (const entry of entries.sort((a, b) => a.name.localeCompare(b.name))) {
      if (++seen > budget) throw new Error('signal budget exceeded');
      const full = path.join(current, entry.name);
      if (entry.isDirectory()) { if (!SIGNAL_IGNORE.has(entry.name)) stack.push(full); continue; }
      try {
        const lst = fs.lstatSync(full, { bigint: true });
        h.update(`${path.relative(dir, full)}:${lst.size}:${lst.mtimeNs}\0`);
        if (lst.isSymbolicLink()) { const st = fs.statSync(full, { bigint: true }); h.update(`link:${st.size}:${st.mtimeNs}\0`); if (st.isDirectory()) stack.push(full); }
      } catch { h.update(`${path.relative(dir, full)}:absent\0`); }
    }
  }
}

function json(res, value, status = 200) {
  res.writeHead(status, { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'no-store' });
  res.end(JSON.stringify(value));
}
