import fs from 'node:fs';
import path from 'node:path';
import readline from 'node:readline';
import crypto from 'node:crypto';
import { scanProject } from './scan.js';

// Explicit local setup is separate from read-only mapping. Describe the goal,
// never invent components, connections, evidence, or a walkthrough plan.
export async function initializeProject(target, { input = process.stdin, output = process.stdout } = {}) {
  if (/^https?:\/\//i.test(target)) throw new Error('--init needs a local project folder. Clone a remote repository locally first.');
  const root = path.resolve(target);
  const folder = path.join(root, '.buildmap');
  const destination = path.join(folder, 'project.json');
  if (fs.existsSync(root) && !fs.statSync(root).isDirectory()) throw new Error(`Not a directory: ${root}`);
  if (fs.existsSync(destination)) throw new Error('This project already has .buildmap/project.json. Keep its plan and edit it directly; setup will not overwrite it.');
  try {
    if (!fs.lstatSync(folder).isDirectory() || fs.lstatSync(folder).isSymbolicLink()) throw new Error('Setup needs a regular .buildmap directory inside the project.');
  } catch (err) { if (err.code !== 'ENOENT') throw err; }
  output.write('Describe what you want to build. Setup saves only your project description; existing source and evidence stay intact.\n');
  const reader = readline.createInterface({ input, output, terminal: Boolean(input.isTTY && output.isTTY) });
  const lines = reader[Symbol.asyncIterator]();
  const ask = async prompt => {
    output.write(prompt);
    const next = await lines.next();
    if (next.done) throw new Error('Setup stopped before all answers were received. No project description was written.');
    return next.value.trim();
  };
  let manifest;
  try {
    const defaultName = path.basename(root) || 'My project';
    const name = await ask(`Project name [${defaultName}]: `) || defaultName;
    const mission = await ask('What should this project help someone accomplish? ');
    if (!mission) throw new Error('A goal is needed to start the description. No project description was written.');
    const experience = await ask('What should someone see or experience when it is finished? [optional] ');
    const behavior = await ask('What should the finished product do? [Enter to use your goal] ') || mission;
    manifest = { name, mission, finishedProduct: { ...(experience ? { experience } : {}), behavior }, components: [] };
  } finally { reader.close(); }
  fs.mkdirSync(folder, { recursive: true });
  fs.writeFileSync(destination, JSON.stringify(manifest, null, 2) + '\n', { flag: 'wx' });
  output.write(`Saved the intended goal and finished product to ${destination}.\nNo implementation or proof was created. Map the folder to discover existing source; add planned pieces when their jobs are clear.\n`);
  return { root, manifest, path: destination };
}

// Append an owner-described journey using the existing map. Ordering is a plan,
// not discovered wiring, an observed handoff, or a receipt.
export async function createWalkthrough(target, { input = process.stdin, output = process.stdout } = {}) {
  const plan = editablePlan(target, '--walkthrough');
  const { root, destination, manifest, map, evidence } = plan;
  const pieces = map.nodes.filter(n => n.kind !== 'mission');
  if (!pieces.length) throw new Error('No pieces are mapped yet. Add source or declare planned pieces first; walkthrough setup does not invent them.');
  const reserved = new Set([...(manifest.outcomes || []).map(o => o.id), ...Object.keys(evidence?.outcomes || {})]);
  output.write('Describe one result and the pieces that should build toward it. This saves a plan, not evidence that it works.\n');
  output.write(`Current project goal: ${map.project.intent.text}\n\nMapped pieces (numbers are only for selection):\n`);
  pieces.forEach((n, i) => output.write(`${i + 1}. ${n.name} [${n.id}] — ${n.implementation}; ${n.files.join(', ') || 'no files assigned'}\n`));
  const reader = readline.createInterface({ input, output, terminal: Boolean(input.isTTY && output.isTTY) });
  const lines = reader[Symbol.asyncIterator]();
  const ask = async prompt => {
    output.write(prompt);
    const next = await lines.next();
    if (next.done) throw new Error('Walkthrough setup stopped before all answers were received. No plan was changed.');
    return next.value.trim();
  };
  const required = async prompt => {
    for (;;) { const answer = await ask(prompt); if (answer) return answer; output.write('Please describe this in your own words.\n'); }
  };
  const choose = value => /^\d+$/.test(value) && Number(value) >= 1 && Number(value) <= pieces.length ? pieces[Number(value) - 1] : null;
  let outcome;
  try {
    const name = await required('Name this walkthrough: ');
    const goal = await required('What should someone accomplish by the end? ');
    const baseId = name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') || 'walkthrough';
    let id = baseId;
    for (let suffix = 2; reserved.has(id); suffix++) id = `${baseId}-${suffix}`;
    const steps = [];
    for (;;) {
      const selection = await ask(`Piece for step ${steps.length + 1} [number, or Enter to finish]: `);
      if (!selection) { if (steps.length) break; output.write('A walkthrough needs at least one step.\n'); continue; }
      const piece = choose(selection);
      if (!piece) { output.write('Choose a mapped piece number from the list.\n'); continue; }
      const label = await ask(`What happens in this step? [${piece.name}] `) || piece.name;
      const expected = await required('What result should this step produce? ');
      const explanation = await ask('Explain how this step helps the goal [optional]: ');
      steps.push({ id: `step-${steps.length + 1}`, nodeId: piece.id, label, expected, ...(explanation ? { explanation } : {}) });
    }
    let supports;
    for (;;) {
      const answer = await ask('Supporting pieces, such as tests [numbers separated by commas, or Enter for none]: ');
      const selections = answer ? answer.split(',').map(v => choose(v.trim())) : [];
      if (selections.every(Boolean)) { supports = [...new Set(selections.map(n => n.id))]; break; }
      output.write('Use mapped piece numbers separated by commas.\n');
    }
    outcome = { id, name, goal, steps, supports };
    output.write(`\nReview before saving: ${name}\nGoal: ${goal}\n`);
    steps.forEach((s, i) => output.write(`${i + 1}. ${s.label} [${s.nodeId}]\n   Expected: ${s.expected}\n${s.explanation ? `   Why: ${s.explanation}\n` : ''}`));
    output.write(`Supporting pieces: ${supports.join(', ') || 'none'}\n`);
    output.write('This is intended behavior. Existing evidence stays as recorded; this walkthrough starts unproved.\n');
    if ((await ask('Save this walkthrough? [yes/No] ')).toLowerCase() !== 'yes') {
      output.write('Cancelled. No plan was changed.\n'); return null;
    }
  } finally { reader.close(); }
  plan.append('outcomes', outcome);
  output.write(`Saved walkthrough "${outcome.name}" (${outcome.id}). Select it under Your goals in the free map or open Walkthrough · Free to review its steps.\nNo code, connections, or proof was created.\n`);
  return { root, outcome, path: destination };
}


// Authoring appends a reviewed declaration or extends one captured component.
// Re-read before an atomic rename; never replace edits made during the interview.
function editablePlan(target, flag) {
  if (/^https?:\/\//i.test(target)) throw new Error(`${flag} needs a local project folder. Clone a remote repository locally first.`);
  const root = path.resolve(target), folder = path.join(root, '.buildmap'), destination = path.join(folder, 'project.json');
  const regular = (file, directory = false) => {
    let stat;
    try { stat = fs.lstatSync(file); } catch (err) {
      if (err.code === 'ENOENT') throw new Error('Create a project description first with --init, then add a piece or walkthrough.');
      throw err;
    }
    if (stat.isSymbolicLink() || !(directory ? stat.isDirectory() : stat.isFile() && stat.nlink === 1))
      throw new Error('Plan authoring needs a regular .buildmap directory and an unlinked project.json file inside it.');
    return stat;
  };
  const folderStat = regular(folder, true), originalStat = regular(destination), original = fs.readFileSync(destination, 'utf8');
  let manifest;
  try { manifest = JSON.parse(original); } catch { throw new Error('Fix the invalid project.json before adding a declaration. No plan was changed.'); }
  if (!manifest || typeof manifest !== 'object' || Array.isArray(manifest)) throw new Error('project.json must contain a project object. No plan was changed.');
  const map = scanProject(root);
  if (map.diagnostics.some(d => ['invalid-config', 'invalid-outcome'].includes(d.code))) throw new Error('Review the invalid project plan findings before adding a declaration. No plan was changed.');
  const evidencePath = path.join(folder, 'evidence.json');
  const readEvidence = () => {
    if (!fs.existsSync(evidencePath)) return {};
    try { return JSON.parse(fs.readFileSync(evidencePath, 'utf8')); } catch { throw new Error('Review the unreadable evidence.json before adding a declaration. No plan was changed.'); }
  };
  const evidence = readEvidence();
  return { root, destination, manifest, map, evidence, append(collection, record, replaceIndex = null) {
    const currentFolder = regular(folder, true), currentFile = regular(destination);
    if (currentFolder.dev !== folderStat.dev || currentFolder.ino !== folderStat.ino ||
        currentFile.dev !== originalStat.dev || currentFile.ino !== originalStat.ino || fs.readFileSync(destination, 'utf8') !== original)
      throw new Error('The project plan changed during setup. Start again from the current plan; no plan was changed by this command.');
    const latest = readEvidence();
    if (replaceIndex === null && Object.hasOwn(latest?.[collection] || {}, record.id)) throw new Error('An evidence claim now uses this declaration id. Start again; no plan was changed.');
    if (replaceIndex !== null && JSON.stringify(latest?.components?.[record.id]) !== JSON.stringify(evidence?.components?.[record.id]))
      throw new Error('The selected piece evidence changed during setup. Review the current claim and start again; no plan was changed.');
    const declarations = [...(manifest[collection] || [])];
    if (replaceIndex === null) declarations.push(record); else declarations[replaceIndex] = record;
    const temp = path.join(folder, `.project-${process.pid}-${crypto.randomUUID()}.tmp`);
    try {
      fs.writeFileSync(temp, JSON.stringify({ ...manifest, [collection]: declarations }, null, 2) + '\n', { flag: 'wx', mode: originalStat.mode & 0o777 });
      fs.renameSync(temp, destination);
    } finally { fs.rmSync(temp, { force: true }); }
  } };
}

export async function createPiece(target, { input = process.stdin, output = process.stdout, extend = false } = {}) {
  const plan = editablePlan(target, extend ? '--extend-piece' : '--piece');
  const { root, destination, manifest, map, evidence } = plan;
  const declared = map.nodes.filter(n => n.kind === 'component');
  if (extend && !declared.length) throw new Error('No declared pieces to extend. Create one with --piece first.');
  let selected = null, replaceIndex = null;
  const available = map.nodes.filter(n => n.kind === 'file').map(n => n.files[0]);
  const owned = new Set(map.nodes.filter(n => n.kind === 'component').flatMap(n => n.files));
  const referenced = new Set(map.outcomes.flatMap(o => o.nodeIds));
  const reserved = new Set([...map.nodes.map(n => n.id), ...Object.keys(evidence?.components || {})]);
  const checkPath = raw => {
    const rel = raw.startsWith('./') ? raw.slice(2) : raw;
    if (!rel || rel.includes('\\') || rel.includes('\0') || path.posix.isAbsolute(rel) || /^[A-Za-z]:/.test(rel) ||
        path.posix.normalize(rel) !== rel || rel === '.' || rel === '..' || rel.startsWith('../') || rel.endsWith('/') || /[*?]/.test(rel))
      throw new Error('Use an exact project-relative file path, without traversal, backslashes or wildcard patterns.');
    if (owned.has(rel) && !selected?.files.includes(rel)) throw new Error(`${rel} already belongs to a declared piece. This command never moves another piece's files.`);
    if (referenced.has(`file:${rel}`)) throw new Error(`${rel} is used by an existing walkthrough. Review its piece references before regrouping; this command leaves that walkthrough intact.`);
    let current = root;
    for (const [i, part] of rel.split('/').entries()) {
      current = path.join(current, part);
      let stat;
      try { stat = fs.lstatSync(current); } catch (err) { if (err.code === 'ENOENT') break; throw err; }
      if (stat.isSymbolicLink()) throw new Error('Choose regular paths inside the project; linked files/directories are not accepted by piece setup.');
      if (i < rel.split('/').length - 1 ? !stat.isDirectory() : !stat.isFile()) throw new Error('Implementation paths must name files, with directories as their parents.');
    }
    return rel;
  };
  output.write(extend ? 'Add files to an existing piece. Its identity, descriptions, goals, source and evidence stay intact. Bound records may become stale when scope expands.\n'
    : 'Describe one piece and the exact files that belong to it. Source and evidence stay intact; missing files remain planned.\n');
  if (extend) declared.forEach((n, i) => output.write(`Piece ${i + 1}. ${n.name} [${n.id}] — ${n.files.join(', ') || 'no files assigned'}\n`));
  output.write('Available ungrouped files (numbers are only for selection):\n');
  available.forEach((file, i) => output.write(`${i + 1}. ${file}\n`));
  if (!available.length) output.write('None yet. You can describe planned file paths below.\n');
  const reader = readline.createInterface({ input, output, terminal: Boolean(input.isTTY && output.isTTY) });
  const lines = reader[Symbol.asyncIterator]();
  const ask = async prompt => {
    output.write(prompt); const next = await lines.next();
    if (next.done) throw new Error('Piece setup stopped before all answers were received. No plan was changed.');
    return next.value.trim();
  };
  const required = async prompt => { for (;;) { const value = await ask(prompt); if (value) return value; output.write('Please describe this in your own words.\n'); } };
  let component, additions;
  try {
    if (extend) for (;;) {
      const choice = await ask('Which existing piece should receive files? [piece number]: ');
      if (!/^\d+$/.test(choice) || !declared[Number(choice) - 1]) { output.write('Choose a declared piece number.\n'); continue; }
      replaceIndex = Number(choice) - 1; selected = declared[replaceIndex];
      // Plan validation forbids filtered/duplicate declarations. Keep this
      // positional correspondence explicit before replacing an original entry.
      if (manifest.components?.length !== declared.length || !manifest.components[replaceIndex] ||
          (manifest.components[replaceIndex].id && manifest.components[replaceIndex].id !== selected.id))
        throw new Error('The selected piece does not match its original declaration. No plan was changed.');
      if (selected.conflictingFiles.length) throw new Error('Resolve this piece\'s overlapping ownership before extending it. No plan was changed.');
      const receipt = evidence?.components?.[selected.id];
      if (receipt && ['computing', 'verified', 'live'].includes(receipt.status) && receipt.sourceHashes === undefined)
        throw new Error('This piece has an unbound behavior claim. Record its actual observation with full source hashes before extending scope; the existing claim is untouched.');
      break;
    }
    const name = selected ? selected.name : await required('Name this piece: ');
    const purpose = selected ? selected.purpose : await required('What job should it do? ');
    const contributes = selected ? selected.contributes : await ask('How does it help the project goal? [optional] ');
    const files = new Set(selected?.files || []);
    for (;;) {
      const answer = await ask('Existing files [numbers separated by commas, or Enter for none]: ');
      if (!answer) break;
      try {
        const selections = answer.split(',').map(v => {
          if (!/^\d+$/.test(v.trim()) || !available[Number(v.trim()) - 1]) throw new Error('Choose available file numbers from the list.');
          return checkPath(available[Number(v.trim()) - 1]);
        });
        selections.forEach(f => files.add(f)); break;
      } catch (err) { output.write(`${err.message}\n`); }
    }
    for (;;) {
      const answer = await ask('Additional or planned file path [relative to project, Enter to finish]: ');
      if (!answer) break;
      try { files.add(checkPath(answer)); } catch (err) { output.write(`${err.message}\n`); }
    }
    const base = name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') || 'piece';
    let id = selected?.id || base; if (!selected) for (let suffix = 2; reserved.has(id); suffix++) id = `${base}-${suffix}`;
    if (selected && files.size === selected.files.length) { output.write('No additional files selected. No plan was changed.\n'); return null; }
    const originalPiece = selected && manifest.components[replaceIndex];
    const originalFiles = originalPiece && (originalPiece.files || originalPiece.file || []);
    additions = [...files].filter(f => !selected?.files.includes(f));
    // Retain authored spelling/order/duplicates and legacy fields. Only the
    // additions use normalized exact paths; pin any previously inferred id.
    component = selected ? { ...originalPiece, id: originalPiece.id || id,
      files: [...(Array.isArray(originalFiles) ? originalFiles : [originalFiles]), ...additions] }
      : { id, name, purpose, ...(contributes ? { contributes } : {}), files: [...files] };
    output.write(`\nReview before saving: ${name} [${id}]\nJob: ${purpose}\nContribution: ${contributes || 'not described'}\n`);
    files.forEach(f => output.write(`- ${f} — ${fs.existsSync(path.join(root, f)) ? 'present' : 'planned / missing'}\n`));
    if (!files.size) output.write('No files assigned yet — this piece stays planned.\n');
    output.write('Grouping does not prove component behavior. File-only receipts stay file-only; walkthroughs and evidence are not rewritten.\n');
    if (selected) output.write('The piece id and goal references are preserved. Existing bound piece and walkthrough examples can be rejected as stale or incomplete after adding files. Repeat relevant observations/checks before recording new hashes.\n');
    if ((await ask('Save this piece? [yes/No] ')).toLowerCase() !== 'yes') { output.write('Cancelled. No plan was changed.\n'); return null; }
  } finally { reader.close(); }
  additions.forEach(checkPath); // New paths may have changed while answering.
  plan.append('components', component, replaceIndex);
  output.write(`Saved piece "${component.name}" (${component.id}). Open the free map to inspect its complete file list and gaps.\nNo source, connections or proof was created.\n`);
  return { root, component, path: destination };
}
