import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { scanProject } from './scan.js';

const publicDir = fileURLToPath(new URL('../public/', import.meta.url));
const ASSETS = { '/': ['index.html', 'text/html'], '/app.js': ['app.js', 'text/javascript'], '/guide-tasks.js': ['guide-tasks.js', 'text/javascript'], '/styles.css': ['styles.css', 'text/css'] };

export function startServer({ root, source = null, host = '127.0.0.1', port = 4173 }) {
  const server = http.createServer((req, res) => {
    try {
      if (!['GET', 'HEAD'].includes(req.method)) {
        res.setHeader('allow', 'GET, HEAD');
        return json(res, { error: 'Method not allowed' }, 405);
      }
      const url = new URL(req.url || '/', 'http://localhost');
      if (url.pathname === '/api/health') return json(res, { ok: true, root });
      if (url.pathname === '/api/map') return json(res, scanProject(root, { source }));
      if (url.pathname === '/api/gaps') {
        const map = scanProject(root, { source });
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

function json(res, value, status = 200) {
  res.writeHead(status, { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'no-store' });
  res.end(JSON.stringify(value));
}
