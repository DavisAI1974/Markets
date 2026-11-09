import path from 'node:path';
import { analyzeJavaScript } from './javascript.js';

const JS_EXT = ['.js', '.mjs', '.cjs', '.jsx', '.ts', '.tsx'];

// Lightweight lexical discovery, not a language parser. Skip comments and treat
// quoted text as single tokens so examples in strings do not become imports.
function jsSpecs(source) {
  const tokens = [...source.matchAll(/\/\*[\s\S]*?\*\/|\/\/[^\n]*|`(?:\\[\s\S]|[^`])*`|'(?:\\[\s\S]|[^'\\])*'|"(?:\\[\s\S]|[^"\\])*"|[A-Za-z_$][\w$]*|[^\s]/g)]
    .map(m => m[0]).filter(t => !t.startsWith('//') && !t.startsWith('/*'));
  const specs = new Set();
  const quoted = t => t && /^["']/.test(t);
  for (let i = 0; i < tokens.length; i++) {
    const token = tokens[i];
    if (tokens[i - 1] === '.') continue;
    if ((token === 'require' || token === 'import') && tokens[i + 1] === '(' && quoted(tokens[i + 2]) &&
      [')', ','].includes(tokens[i + 3])) {
      specs.add(tokens[i + 2].slice(1, -1));
    } else if (token === 'import' && quoted(tokens[i + 1])) {
      specs.add(tokens[i + 1].slice(1, -1));
    } else if ((token === 'import' || token === 'export') && tokens[i + 1] !== '(' && tokens[i + 1] !== 'default') {
      for (let j = i + 1; j < tokens.length; j++) {
        if ([';', 'import', 'export'].includes(tokens[j])) break;
        if (tokens[j] === 'from' && quoted(tokens[j + 1])) {
          specs.add(tokens[j + 1].slice(1, -1)); break;
        }
        // An exported body/default expression is not a re-export declaration.
        if (['function', 'class', 'const', 'let', 'var'].includes(tokens[j])) break;
      }
    }
  }
  return [...specs];
}

// Python import forms: 'module' = a dotted module path that must resolve to a
// file; 'symbol' = `from X import name`, where name may be a module or a name
// defined in X; 'sibling' = `from . import name` with no named package part.
function pythonImports(source) {
  const masked = source.replace(/'''[\s\S]*?'''|"""[\s\S]*?"""|'(?:\\.|[^'\\\n])*'|"(?:\\.|[^"\\\n])*"|#[^\n]*/g, m => m.replace(/[^\n]/g, ' '))
    .replace(/\\\r?\n/g, ' '); // Backslash continuation joins the logical line.
  const forms = new Map();
  const add = (spec, form) => { if (!forms.has(spec) || form === 'module') forms.set(spec, form); };
  // A parenthesized name list may span lines; comments inside it are already blanked.
  for (const match of masked.matchAll(/^[ \t]*from[ \t]+([.\w]+)[ \t]+import[ \t]+(\([^)]*\)|[^\n]+)/gm)) {
    const [, module, names] = match;
    const dotsOnly = /^\.+$/.test(module);
    if (!dotsOnly) add(module, 'module');
    for (const name of names.replace(/[()]/g, '').split(',')) {
      const item = name.trim().split(/\s+/)[0];
      if (item && item !== '*') add(`${module}${module.endsWith('.') ? '' : '.'}${item}`, dotsOnly ? 'sibling' : 'symbol');
    }
  }
  for (const match of masked.matchAll(/^[ \t]*import[ \t]+([^\n]+)/gm)) {
    for (const item of match[1].split(',')) { const spec = item.trim().split(/\s+/)[0]; if (spec) add(spec, 'module'); }
  }
  return forms;
}

function pythonSpecs(source) { return [...pythonImports(source).keys()]; }

export function sourceReferences(source, ext, { allowReturnOutsideFunction = false } = {}) {
  if (['.js', '.mjs', '.cjs'].includes(ext)) return analyzeJavaScript(source, ext, { allowReturnOutsideFunction });
  if (ext === '.py') {
    const forms = pythonImports(source);
    return { imports: [...forms.keys()], importForms: Object.fromEntries(forms), requests: [], providers: [] };
  }
  return { imports: lexicalSpecs(source, ext), requests: [], providers: [] };
}

export function importSpecs(source, ext) { return sourceReferences(source, ext).imports; }

function lexicalSpecs(source, ext) {
  if (JS_EXT.includes(ext)) return jsSpecs(source);
  if (ext === '.py') return pythonSpecs(source);
  if (['.html', '.htm'].includes(ext)) {
    const clean = source.replace(/<!--[\s\S]*?-->/g, '');
    return [...clean.matchAll(/<(?:script|link)\b[^>]*?\b(?:src|href)\s*=\s*["']([^"']+)["'][^>]*>/gi)].map(m => m[1]);
  }
  if (ext === '.css') {
    const clean = source.replace(/\/\*[\s\S]*?\*\//g, '');
    return [...clean.matchAll(/@import\s+(?:url\(\s*)?["']([^"']+)["']/g)].map(m => m[1]);
  }
  return [];
}

export function resolveImport(fromFile, spec, fileSet, ext) {
  if (ext === '.py') return pythonCandidates(fromFile, spec).find(c => fileSet.has(c)) || null;
  const asset = ['.html', '.htm', '.css'].includes(ext);
  if (!asset && !spec.startsWith('.')) return null;
  if (/^(?:[a-z]+:|\/\/|#)/i.test(spec)) return null;
  const local = spec.split(/[?#]/)[0];
  const base = path.posix.normalize(local.startsWith('/') ? local.slice(1) : path.posix.join(path.posix.dirname(fromFile), local));
  const candidates = [base];
  if (!asset) {
    // TypeScript commonly imports its emitted .js filename.
    if (base.endsWith('.js')) candidates.push(base.slice(0, -3) + '.ts', base.slice(0, -3) + '.tsx');
    candidates.push(...JS_EXT.map(e => base + e), ...JS_EXT.map(e => `${base}/index${e}`));
  }
  return candidates.find(c => fileSet.has(c)) || null;
}

// Candidate files for a Python spec, in resolution order. Non-relative specs
// are tried from the importer's directory first (sys.path[0] for a script),
// then from the project root; this is the same base order as the workflow
// call-link resolver (workflow.js moduleCandidates), so map edges and call
// links agree on which file a name came from.
export function pythonCandidates(fromFile, spec) {
  return [...new Set(pythonCandidateGroups(fromFile, spec).flat())];
}

// One candidate group per base, in resolution order. A relative spec has one
// base; a non-relative spec has the importer directory, then the root.
export function pythonCandidateGroups(fromFile, spec) {
  const dots = spec.match(/^\.+/)?.[0].length || 0;
  const module = spec.slice(dots).replaceAll('.', '/');
  const importerDir = path.posix.dirname(fromFile);
  let bases;
  if (dots) {
    let base = importerDir;
    for (let i = 1; i < dots; i++) base = path.posix.dirname(base);
    bases = [base];
  } else bases = importerDir === '.' ? [''] : [importerDir, ''];
  return bases.map(base => {
    const stem = path.posix.join(base, module);
    return [`${stem}.py`, `${stem}/__init__.py`];
  });
}
