import fs from 'node:fs';

const publicDir = new URL('../public/', import.meta.url);

// Retain one client for HTTP, DOM checks and self-contained exports.
export function clientSource() {
  const tasks = fs.readFileSync(new URL('guide-tasks.js', publicDir), 'utf8').replace(/^export /gm, '');
  const app = fs.readFileSync(new URL('app.js', publicDir), 'utf8').replace(/^import \{[^\n]+\} from '\.\/guide-tasks\.js';\n/, '');
  return `${tasks}\n${app}`;
}

// A snapshot carries map metadata and the existing client, not repository source.
// Escape '<' in the data block so untrusted descriptions cannot close its script.
export function snapshotHtml(map) {
  const template = fs.readFileSync(new URL('index.html', publicDir), 'utf8');
  const css = fs.readFileSync(new URL('styles.css', publicDir), 'utf8');
  const client = clientSource();
  const data = JSON.stringify(map).replaceAll('<', '\\u003c');
  return template
    .replace('<link rel="stylesheet" href="./styles.css" />', () => `<style>${css.replace(/<\/style/gi, '<\\/style')}</style>`)
    .replace('<script type="module" src="./app.js"></script>', () => `<script id="buildmapSnapshot" type="application/json">${data}</script>\n<script type="module">${client.replace(/<\/script/gi, '<\\/script')}</script>`);
}
