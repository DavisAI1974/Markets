import { parse } from 'acorn';
import { explainFunctions } from './code-guide.js';

const functions = new Set(['FunctionDeclaration', 'FunctionExpression', 'ArrowFunctionExpression']);
const httpModules = new Set(['http', 'node:http']);
const string = n => n?.type === 'Literal' && typeof n.value === 'string' ? n.value
  : n?.type === 'TemplateLiteral' && n.expressions.length === 0 ? n.quasis[0].value.cooked : null;
const identifier = (n, name) => n?.type === 'Identifier' && n.name === name;
const property = n => n?.type === 'MemberExpression' ? (n.computed ? string(n.property) : n.property.name) : null;
const member = (n, object, key) => property(n) === key && identifier(n.object, object);
const location = n => ({ line: n.loc.start.line, column: n.loc.start.column + 1 });

// Iterative AST traversal. Source syntax is evidence of a reference, not proof
// that a call executes, serves this browser, or runs in any particular origin.
function walk(root, visit, enterFunctions = true) {
  const stack = [root];
  while (stack.length) {
    const node = stack.pop();
    if (!node?.type || (!enterFunctions && functions.has(node.type))) continue;
    visit(node);
    for (const value of Object.values(node)) {
      if (Array.isArray(value)) {
        for (let i = value.length - 1; i >= 0; i--) if (value[i]?.type) stack.push(value[i]);
      } else if (value?.type) stack.push(value);
    }
  }
}

function bindingNames(pattern, add) {
  if (!pattern) return;
  if (pattern.type === 'Identifier') add(pattern.name);
  else if (pattern.type === 'RestElement') bindingNames(pattern.argument, add);
  else if (pattern.type === 'AssignmentPattern') bindingNames(pattern.left, add);
  else if (pattern.type === 'ArrayPattern') pattern.elements.forEach(p => bindingNames(p, add));
  else if (pattern.type === 'ObjectPattern') pattern.properties.forEach(p => bindingNames(p.type === 'RestElement' ? p.argument : p.value, add));
}

export function analyzeJavaScript(source, ext = '.js') {
  let ast;
  try { ast = parse(source, { ecmaVersion: 'latest', sourceType: ext === '.cjs' ? 'commonjs' : 'module', locations: true }); }
  catch (err) {
    return { imports: [], requests: [], providers: [], error: `JavaScript parsing failed at ${err.loc?.line || '?'}:${(err.loc?.column ?? -1) + 1}; source references were skipped.` };
  }
  const bindings = new Map();
  const add = name => bindings.set(name, (bindings.get(name) || 0) + 1);
  walk(ast, n => {
    if (n.type === 'VariableDeclarator') bindingNames(n.id, add);
    if (functions.has(n.type)) { bindingNames(n.id, add); n.params.forEach(p => bindingNames(p, add)); }
    if (n.type === 'ClassDeclaration' || n.type === 'ClassExpression') bindingNames(n.id, add);
    if (n.type === 'ImportDeclaration') n.specifiers.forEach(s => add(s.local.name));
    if (n.type === 'CatchClause') bindingNames(n.param, add);
    if (n.type === 'AssignmentExpression') bindingNames(n.left, add);
    if (n.type === 'UpdateExpression') bindingNames(n.argument, add);
  });
  const objects = new Set(), factories = new Set(), imports = new Set();
  for (const statement of ast.body) {
    if (statement.type === 'ImportDeclaration' && httpModules.has(string(statement.source))) {
      for (const spec of statement.specifiers) {
        if (spec.type === 'ImportDefaultSpecifier' || spec.type === 'ImportNamespaceSpecifier') objects.add(spec.local.name);
        if (spec.type === 'ImportSpecifier' && spec.imported.name === 'createServer') factories.add(spec.local.name);
      }
    }
    if (statement.type === 'VariableDeclaration' && !bindings.has('require')) for (const d of statement.declarations) {
      if (d.init?.type === 'CallExpression' && identifier(d.init.callee, 'require') && httpModules.has(string(d.init.arguments[0]))) {
        if (d.id.type === 'Identifier') objects.add(d.id.name);
        if (d.id.type === 'ObjectPattern') for (const p of d.id.properties) {
          if (p.key?.name === 'createServer' && p.value?.type === 'Identifier') factories.add(p.value.name);
        }
      }
    }
  }
  const responders = responseHelpers(ast, bindings);
  const requests = [], providers = [];
  walk(ast, n => {
    if (['ImportDeclaration', 'ExportNamedDeclaration', 'ExportAllDeclaration'].includes(n.type)) {
      const spec = string(n.source); if (spec !== null) imports.add(spec);
    }
    if (n.type === 'ImportExpression') { const spec = string(n.source); if (spec !== null) imports.add(spec); }
    if (n.type !== 'CallExpression') return;
    if (identifier(n.callee, 'require') && !bindings.has('require')) {
      const spec = string(n.arguments[0]); if (spec !== null) imports.add(spec);
    }
    if (identifier(n.callee, 'fetch') && !bindings.has('fetch')) {
      const endpoint = string(n.arguments[0]);
      if (endpoint?.startsWith('/') && !endpoint.startsWith('//')) {
        const method = requestMethod(n.arguments[1]);
        const url = new URL(endpoint, 'http://buildmap.invalid');
        if (method) requests.push({ endpoint, path: url.pathname, rawPath: url.pathname + url.search, method, ...location(n) });
      }
    }
    const name = n.callee?.type === 'Identifier' ? n.callee.name : n.callee?.object?.name;
    if (bindings.get(name) !== 1) return;
    if ((factories.has(name) && identifier(n.callee, name)) || (objects.has(name) && member(n.callee, name, 'createServer'))) {
      const handler = n.arguments[0];
      if (functions.has(handler?.type) && handler.params[0]?.type === 'Identifier' && handler.params[1]?.type === 'Identifier') {
        providers.push(...handlerPaths(handler, bindings, responders));
      }
    }
  });
  return { imports: [...imports], requests, providers, functions: explainFunctions(ast, bindings, source) };
}

function requestMethod(options) {
  if (!options) return 'GET';
  if (options.type !== 'ObjectExpression' || options.properties.some(p => p.type === 'SpreadElement' || p.computed)) return null;
  let method = 'GET';
  for (const p of options.properties) if ((p.key.name || string(p.key)) === 'method') {
    const value = string(p.value); if (!value) return null; method = value.toUpperCase();
  }
  return method;
}

function responseHelpers(ast, bindings) {
  const helpers = new Map();
  for (const top of ast.body) {
    const statement = top.type === 'ExportNamedDeclaration' ? top.declaration : top;
    const definitions = statement?.type === 'FunctionDeclaration' ? [[statement.id.name, statement]]
      : statement?.type === 'VariableDeclaration' ? statement.declarations.filter(d => d.id.type === 'Identifier' && functions.has(d.init?.type)).map(d => [d.id.name, d.init]) : [];
    for (const [name, fn] of definitions) {
      if (bindings.get(name) !== 1) continue;
      const positions = new Set();
      walk(fn.body, call => {
        if (call.type !== 'CallExpression' || !['end', 'write', 'writeHead'].includes(property(call.callee))) return;
        fn.params.forEach((p, i) => { if (p.type === 'Identifier' && identifier(call.callee.object, p.name)) positions.add(i); });
      }, false);
      if (positions.size) helpers.set(name, positions);
    }
  }
  return helpers;
}

function handlerPaths(handler, bindings, responders) {
  const req = handler.params[0].name, res = handler.params[1].name, urls = new Set(), paths = [];
  const locals = new Map([[req, 1], [res, 1]]);
  const add = name => locals.set(name, (locals.get(name) || 0) + 1);
  walk(handler.body, n => {
    if (n.type === 'VariableDeclarator') bindingNames(n.id, add);
    if (n.type === 'CatchClause') bindingNames(n.param, add);
    if (n.type === 'AssignmentExpression') bindingNames(n.left, add);
    if (n.type === 'UpdateExpression') bindingNames(n.argument, add);
  }, false);
  if (locals.get(req) !== 1 || locals.get(res) !== 1) return paths;
  // Only inline callbacks and a direct request URL parse are recognized. Names
  // with multiple bindings/reassignments are conservatively left unresolved.
  if (!bindings.has('URL')) walk(handler.body, n => {
    const first = n.init?.arguments?.[0];
    const requestURL = member(first, req, 'url') || (first?.type === 'LogicalExpression' && first.operator === '||' && member(first.left, req, 'url'));
    if (n.type === 'VariableDeclarator' && n.id.type === 'Identifier' && locals.get(n.id.name) === 1 &&
      n.init?.type === 'NewExpression' && identifier(n.init.callee, 'URL') && requestURL) urls.add(n.id.name);
  }, false);
  const conditions = test => {
    if (test?.type === 'LogicalExpression') return [...conditions(test.left), ...conditions(test.right)];
    if (test?.type !== 'BinaryExpression' || !['===', '=='].includes(test.operator)) return [];
    for (const [target, literal] of [[test.left, test.right], [test.right, test.left]]) {
      const endpoint = string(literal);
      if (!endpoint?.startsWith('/') || endpoint.startsWith('//')) continue;
      if (member(target, req, 'url')) return [{ endpoint, raw: true }];
      if (property(target) === 'pathname' && urls.has(target.object?.name)) return [{ endpoint, raw: false }];
    }
    return [];
  };
  walk(handler.body, n => {
    if (n.type !== 'IfStatement') return;
    let response = false;
    walk(n.consequent, call => {
      if (call.type !== 'CallExpression') return;
      if (identifier(call.callee?.object, res) && ['end', 'write', 'writeHead'].includes(property(call.callee))) response = true;
      if (call.callee.type === 'Identifier' && [...(responders.get(call.callee.name) || [])].some(i => identifier(call.arguments[i], res))) response = true;
    }, false);
    if (response) for (const condition of conditions(n.test)) paths.push({ ...condition, method: handlerMethod(n.test, req), ...location(n.test) });
  }, false);
  return paths;
}

function handlerMethod(test, req) {
  if (test.type === 'BinaryExpression' && ['===', '=='].includes(test.operator)) {
    for (const [target, value] of [[test.left, test.right], [test.right, test.left]]) {
      if (member(target, req, 'method') && string(value)) return string(value).toUpperCase();
    }
  }
  if (test.type === 'LogicalExpression' && test.operator === '&&') {
    const a = handlerMethod(test.left, req), b = handlerMethod(test.right, req);
    return a && b && a !== b ? null : a || b;
  }
  return null;
}
