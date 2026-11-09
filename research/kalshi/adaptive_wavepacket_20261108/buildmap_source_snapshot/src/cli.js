#!/usr/bin/env node
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import { spawnSync } from 'node:child_process';
import { startServer } from './server.js';
import { scanProject } from './scan.js';
import { snapshotHtml } from './export.js';
import { initializeProject, createWalkthrough, createPiece } from './setup.js';
import { importMeasurements } from './measurements.js';
import { readAnalysisDocument } from './review-evidence.js';
import { observePython, generateCollectorKey } from './collected-runs.js';

export function parseArgs(args) {
  const options = { target: '.', port: 4173, host: '127.0.0.1', json: false, html: null, ref: null, init: false, walkthrough: false, piece: false, extendPiece: false, workflowAll: false, help: false };
  let targetSeen = false;
  for (let i = 0; i < args.length; i++) {
    const arg = args[i];
    if (arg === '--help' || arg === '-h') options.help = true;
    else if (arg === '--init') options.init = true;
    else if (arg === '--walkthrough') options.walkthrough = true;
    else if (arg === '--piece') options.piece = true;
    else if (arg === '--extend-piece') options.extendPiece = true;
    else if (arg === '--json') options.json = true;
    else if (arg === '--workflow-all') options.workflowAll = true;
    else if (['--port','--host','--html','--ref','--import-measurements','--analysis-output','--observe-python','--observe-args','--observe-timeout','--python-runtime','--collector-key','--collector-id','--observation-output','--new-collector-key','--collector-public'].includes(arg)) {
      const value = args[++i];
      if (!value || value.startsWith('--')) throw new Error(`Missing value for ${arg}.`);
      options[arg.slice(2)] = arg === '--port' ? Number(value) : value;
    } else if (arg.startsWith('-')) throw new Error(`Unknown option: ${arg}.`);
    else if (targetSeen) throw new Error('Pass one project path or GitHub URL.');
    else { options.target = arg; targetSeen = true; }
  }
  if (options.ref && !options.help && !/^https:\/\/github\.com\//i.test(options.target)) throw new Error('--ref applies to GitHub URL input. For local mapping, check out the branch yourself.');
  if (options.ref?.startsWith('-')) throw new Error('--ref must name a branch or tag.');
  if (options.json && options.html) throw new Error('Choose --json or --html, not both.');
  const observing=Boolean(options['observe-python']), keygen=Boolean(options['new-collector-key']);
  if(observing||keygen){
    if(observing&&keygen||options.json||options.html||options.init||options.walkthrough||options.piece||options.extendPiece||options.workflowAll||options.ref||options['import-measurements']||/^https?:/.test(options.target))throw Error('Observation/key creation is a separate explicit local operation.');
    if(!options['collector-id']||observing&&(!options['collector-key']||!options['observation-output'])||keygen&&!options['collector-public'])throw Error('Observation needs collector-id/key/output; key creation needs collector-id/public output.');
  }else if(['observe-args','observe-timeout','python-runtime','collector-key','collector-id','observation-output','collector-public'].some(k=>options[k]))throw Error('Collector options require --observe-python or --new-collector-key.');
  if (Boolean(options['import-measurements']) !== Boolean(options['analysis-output'])) throw Error('Measurement import requires both --import-measurements INPUT and --analysis-output NEW_FILE.');
  if (options['import-measurements'] && (options.json || options.html || options.init || options.piece || options.extendPiece || options.walkthrough || options.workflowAll || options.ref || /^https?:/.test(options.target))) throw Error('Measurement import is a separate local operation.');
  if (options.workflowAll && !options.help && (!(options.json || options.html) || options.init || options.walkthrough || options.piece || options.extendPiece)) throw new Error('--workflow-all requires a one-shot --json or --html export; it does not run during live polling or setup.');
  if (options.init && !options.help && (options.json || options.html || options.ref || /^https?:\/\//i.test(options.target))) throw new Error('--init is local setup only. Run mapping or exports separately after setup.');
  if (options.walkthrough && !options.help && (options.init || options.json || options.html || options.ref || /^https?:\/\//i.test(options.target))) throw new Error('--walkthrough is local plan authoring only. Run initial setup, mapping or exports separately.');
  if (options.piece && !options.help && (options.init || options.walkthrough || options.json || options.html || options.ref || /^https?:\/\//i.test(options.target))) throw new Error('--piece is local plan authoring only. Run setup, walkthroughs, mapping or exports separately.');
  if (options.extendPiece && !options.help && (options.init || options.walkthrough || options.piece || options.json || options.html || options.ref || /^https?:\/\//i.test(options.target))) throw new Error('--extend-piece is local plan authoring only. Run other setup, mapping or exports separately.');
  if (!Number.isInteger(options.port) || options.port < 0 || options.port > 65535) throw new Error('--port must be an integer from 0 to 65535.');
  return options;
}

export function prepareTarget(target, log = console.log, ref = null) {
  if (ref && !/^https:\/\/github\.com\//i.test(target)) throw new Error('--ref applies to GitHub URL input. For local mapping, check out the branch yourself.');
  if (/^https?:\/\//i.test(target)) {
    if (!/^https:\/\/github\.com\/[\w.-]+\/[\w.-]+\/?$/i.test(target)) throw new Error('Use a repository URL like https://github.com/owner/repo, or a local path.');
    const clean = target.replace(/\/$/, '').replace(/\.git$/, '');
    if (ref) {
      const check = spawnSync('git', ['check-ref-format', '--allow-onelevel', ref], { encoding: 'utf8' });
      if (ref.startsWith('-') || check.status !== 0) throw new Error('Invalid branch/tag name, or Git is unavailable.');
    }
    const dest = fs.mkdtempSync(path.join(os.tmpdir(), 'buildmap-'));
    log(`Cloning ${clean}${ref ? ` at ${ref}` : ''} for read-only mapping…`);
    const result = spawnSync('git', ['clone', '--depth', '1', ...(ref ? ['--branch', ref, '--single-branch'] : []), '--', clean, dest], { stdio: ['ignore', 'ignore', 'inherit'] });
    if (result.status !== 0) {
      fs.rmSync(dest, { recursive: true, force: true });
      throw new Error(`Could not clone the repository${ref ? ` at branch/tag ${ref}` : ''}. Check its visibility and branch/tag name. For private repositories, clone it yourself and pass the local path.`);
    }
    const revision = spawnSync('git', ['-C', dest, 'rev-parse', '--verify', 'HEAD'], { encoding: 'utf8' });
    const branch = spawnSync('git', ['-C', dest, 'symbolic-ref', '--quiet', '--short', 'HEAD'], { encoding: 'utf8' });
    const source = { kind: 'github', url: clean, repoName: clean.split('/').at(-1), requestedRef: ref, ref: ref || (branch.status === 0 ? branch.stdout.trim() : null), revision: revision.status === 0 ? revision.stdout.trim() : null, snapshot: true };
    return { root: dest, source, cleanup: () => fs.rmSync(dest, { recursive: true, force: true }) };
  }
  const full = path.resolve(target);
  if (!fs.existsSync(full)) { fs.mkdirSync(full, { recursive: true }); log(`Created empty project folder: ${full}`); }
  if (!fs.statSync(full).isDirectory()) throw new Error(`Not a directory: ${full}`);
  return { root: full, cleanup: () => {} };
}

async function main() {
  try {
    const options = parseArgs(process.argv.slice(2));
    if (options.help) {
      console.log(`BuildMap v0.1\n\nUsage:\n  buildmap [project-path-or-github-url] [--port 4173] [--host 127.0.0.1] [--ref branch-or-tag] [--json | --html output.html]\n  buildmap [local-project-path] --init\n  buildmap [local-project-path] --walkthrough\n  buildmap [local-project-path] --piece\n  buildmap [local-project-path] --extend-piece\n\n--extend-piece adds files to one existing piece after review, retaining its identity, fields, goals and evidence.\n--piece groups unassigned files or declares a planned piece through a reviewed local interview. It preserves source/evidence and never grants proof.\n--walkthrough guides you through one goal, ordered existing pieces, expected results, and support assignments. Review before saving; existing plans are retained and no proof is recorded.\n--init asks four plain-English questions and saves an initial project description, then exits. Existing plans are never overwritten; code and evidence are untouched.\n--workflow-all analyzes every eligible Python file in bounded sequential batches for a one-shot --json or --html snapshot. Workflow/config files remain visible; unsupported semantics stay unknown.\n--observe-python ENTRY --collector-key PRIVATE --collector-id ID --observation-output NEW_FILE explicitly runs a local Python test script and signs its observation. Optional --observe-args JSON, --observe-timeout MS, --python-runtime EXECUTABLE.\n--new-collector-key PRIVATE --collector-public NEW_FILE --collector-id ID creates a local signing key/public trust document. Keep private keys outside projects.\n--import-measurements INPUT --analysis-output NEW_FILE imports structured JSON/NDJSON observations and stage events to a new review file, never overwriting existing data.\n--json prints one map snapshot, including gaps and source hashes, then exits.\n--html writes a self-contained interactive snapshot to a new file, then exits.\n--ref selects a branch or tag for GitHub URL input; omitted uses the default branch.\n\nExamples:\n  buildmap ../my-project --init\n  buildmap ../my-project --piece\n  buildmap ../my-project --extend-piece\n  buildmap ../my-project --walkthrough\n  buildmap .\n  buildmap --port 5000 ../my-project\n  buildmap https://github.com/owner/repo\n  buildmap https://github.com/owner/repo --ref feature/map\n  buildmap . --json\n  buildmap . --html ../buildmap.html\n`);
      return;
    }
    if(options['new-collector-key']) {
      const made=generateCollectorKey(path.resolve(options['new-collector-key']),path.resolve(options['collector-public']),options['collector-id']);
      console.log(`Created collector ${made.collectorId}. Public key fingerprint: ${made.publicKeyFingerprint}. Keep the private key outside mapped projects.`);return;
    }
    if(options['observe-python']) {
      const root=path.resolve(options.target), map=scanProject(root,{workflowAll:true});
      const hashes=Object.assign({},...map.nodes.filter(n=>n.kind!=='mission').map(n=>n.sourceHashes));
      const result=await observePython({root,entry:options['observe-python'],args:JSON.parse(options['observe-args']||'[]'),sourceHashes:hashes,
        privateKeyFile:path.resolve(options['collector-key']),collectorId:options['collector-id'],output:path.resolve(options['observation-output']),timeoutMs:Number(options['observe-timeout']||60000),pythonExecutable:options['python-runtime']||'python3'});
      process.stdout.write(result.stdout);process.stderr.write(result.stderr);
      console.log(`Collected run ${result.receipt.payload.runId}: exit ${result.receipt.payload.exitCode}; complete within scope: ${result.receipt.payload.completeWithinScope}. Receipt: ${path.resolve(options['observation-output'])}`);
      process.exitCode=result.receipt.payload.parent.exitCode===0&&!result.receipt.payload.parent.timedOut?0:1;return;
    }
    if (options.init || options.walkthrough || options.piece || options.extendPiece) {
      const result = options.init ? await initializeProject(options.target) : options.piece || options.extendPiece ? await createPiece(options.target, { extend: options.extendPiece }) : await createWalkthrough(options.target);
      if (!result) return;
      const { root } = result;
      const quotedRoot = "'" + root.replaceAll("'", "'\\''") + "'";
      console.log(`Next, open the map: node src/cli.js ${quotedRoot}`);
      return;
    }
    if (options['import-measurements']) {
      const root = path.resolve(options.target), base = readAnalysisDocument(root);
      const imported = importMeasurements(root, path.resolve(options['import-measurements']), base);
      const output = path.resolve(options['analysis-output']);
      const json = JSON.stringify(imported.document, null, 2);
      if (Buffer.byteLength(json) > 1_000_000) throw Error('Merged analysis exceeds 1 MB.');
      fs.writeFileSync(output, json + '\n', { flag: 'wx' });
      console.log(`Imported ${imported.imported} observation(s) and ${imported.importedEvents} event(s) to ${output}. ${imported.note}`); return;
    }
    const { root, cleanup, source } = prepareTarget(options.target, options.json ? console.error : console.log, options.ref);
    process.once('exit', cleanup);
    if (options.json) { console.log(JSON.stringify(scanProject(root, { source, workflowAll: options.workflowAll }), null, 2)); return; }
    if (options.html) {
      const output = path.resolve(options.html);
      fs.writeFileSync(output, snapshotHtml(scanProject(root, { source, workflowAll: options.workflowAll })), { flag: 'wx' });
      console.log(`Snapshot saved: ${output}`);
      return;
    }
    const server = startServer({ root, source, host: options.host, port: options.port });
    server.once('error', err => { console.error(`BuildMap could not start: ${err.message}`); process.exitCode = 1; });
    for (const signal of ['SIGINT', 'SIGTERM']) process.once(signal, () => server.close());
  } catch (err) { console.error(`BuildMap: ${err.message}`); process.exitCode = 1; }
}
if (process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href) main();
