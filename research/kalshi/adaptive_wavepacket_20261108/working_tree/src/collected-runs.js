import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { readProjectFile } from './review-evidence.js';

const canonical = value => JSON.stringify(value && typeof value === 'object' ? Array.isArray(value)
  ? value.map(v=>JSON.parse(canonical(v))) : Object.fromEntries(Object.keys(value).sort().map(k=>[k,JSON.parse(canonical(value[k]))])) : value);
const hash = value => crypto.createHash('sha256').update(value).digest('hex');
const exact = p => typeof p==='string' && p && !p.includes('\\') && !path.posix.isAbsolute(p) && !/^[A-Za-z]:/.test(p) && p.split('/').every(s=>s && s!=='.' && s!=='..') && !p.includes('\0');
const integer = n => typeof n==='string' && /^(0|[1-9][0-9]{0,99})$/.test(n);

export function generateCollectorKey(privateFile, publicFile, collectorId) {
  if(typeof collectorId!=='string' || !/^[A-Za-z0-9._-]{1,80}$/.test(collectorId)) throw Error('Use a collector id with 1–80 letters, digits, dot, underscore or hyphen.');
  const {privateKey,publicKey}=crypto.generateKeyPairSync('ed25519');
  const privateFd=fs.openSync(privateFile,'wx',0o600);
  try {fs.writeFileSync(privateFd,privateKey.export({format:'pem',type:'pkcs8'}));} finally {fs.closeSync(privateFd);}
  // A public-file collision never destroys or replaces an existing key.
  fs.writeFileSync(publicFile,JSON.stringify({version:1,collectors:[{id:collectorId,publicKey:publicKey.export({format:'pem',type:'spki'})}]},null,2)+'\n',{flag:'wx',mode:0o644});
  return {collectorId,publicKeyFingerprint:hash(publicKey.export({format:'der',type:'spki'}))};
}

export async function observePython({root,entry,args=[],sourceHashes,privateKeyFile,collectorId,output,timeoutMs=60000,pythonExecutable='python3'}) {
  root=fs.realpathSync(root);
  if(!exact(entry) || !entry.endsWith('.py') || !sourceHashes?.[entry]) throw Error('Choose an inventoried project-relative Python entry point.');
  const entryReal=fs.realpathSync(path.join(root,entry)), rel=path.relative(root,entryReal);
  if(rel==='..'||rel.startsWith(`..${path.sep}`)||path.isAbsolute(rel))throw Error('Entry point escapes the project.');
  if(!Array.isArray(args)||args.length>100||args.some(a=>typeof a!=='string'||a.length>10000))throw Error('Pass at most 100 string arguments, up to 10,000 characters each.');
  if(!Number.isSafeInteger(timeoutMs)||timeoutMs<100||timeoutMs>3_600_000)throw Error('Observation timeout must be 100–3,600,000 ms.');
  if(typeof pythonExecutable!=='string'||!pythonExecutable||pythonExecutable.includes('\0')||pythonExecutable.length>1024)throw Error('Choose a Python interpreter executable.');
  const keyPath=fs.realpathSync(privateKeyFile), keyRel=path.relative(root,keyPath);
  if(keyRel && keyRel!=='..' && !keyRel.startsWith(`..${path.sep}`) && !path.isAbsolute(keyRel))throw Error('Keep the private collector key outside the mapped project.');
  const keyStat=fs.statSync(keyPath); if(!keyStat.isFile()||keyStat.size>16384)throw Error('Invalid collector key file.');
  const key=crypto.createPrivateKey(fs.readFileSync(keyPath));if(key.asymmetricKeyType!=='ed25519')throw Error('Collector signing requires an Ed25519 key.');
  if(typeof collectorId!=='string'||!/^[A-Za-z0-9._-]{1,80}$/.test(collectorId))throw Error('Invalid collector id.');
  const inventory=Object.fromEntries(Object.entries(sourceHashes).filter(([p,h])=>exact(p)&&p.endsWith('.py')&&/^[a-f0-9]{64}$/.test(h)));
  if(Object.keys(inventory).length>10000)throw Error('Observation supports at most 10,000 Python source identities.');
  let sourceBytes=0;
  for(const [file,expected] of Object.entries(inventory)){
    const bytes=readProjectFile(root,file,1_000_000);sourceBytes+=bytes.length;
    if(sourceBytes>128_000_000)throw Error('Observation source identity budget exceeds 128 MB. Select a smaller project boundary.');
    if(hash(bytes)!==expected)throw Error(`Source changed before observation: ${file}`);
  }
  // Reserve the output before execution; a collision cannot launch a workflow.
  const outputFd=fs.openSync(output,'wx',0o600); let written=false;
  const config={root,entry,arguments:args,sourceHashes:inventory,runId:crypto.randomUUID()};
  try {
    const result=await new Promise((resolve,reject)=>{
      const child=spawn(pythonExecutable,['-I',fileURLToPath(new URL('./python-observer.py',import.meta.url))],{cwd:root,stdio:['pipe','pipe','pipe','pipe']});
      const chunks=[[],[],[]], sizes=[0,0,0]; let timedOut=false, overflow=false, killTimer;
      child.stdout.on('data',b=>{if(sizes[0]<4_000_000)chunks[0].push(b.subarray(0,4_000_000-sizes[0]));sizes[0]+=b.length;});
      child.stderr.on('data',b=>{if(sizes[1]<4_000_000)chunks[1].push(b.subarray(0,4_000_000-sizes[1]));sizes[1]+=b.length;});
      child.stdio[3].on('data',b=>{sizes[2]+=b.length;if(sizes[2]<=16_000_000)chunks[2].push(b);else{overflow=true;child.kill('SIGKILL');}});
      const timer=setTimeout(()=>{timedOut=true;child.kill('SIGTERM');killTimer=setTimeout(()=>child.kill('SIGKILL'),2000);},timeoutMs);
      child.on('error',e=>{clearTimeout(timer);clearTimeout(killTimer);reject(e);});
      child.on('close',(code,signal)=>{clearTimeout(timer);clearTimeout(killTimer);resolve({code,signal,timedOut,overflow,sizes,stdout:Buffer.concat(chunks[0]),stderr:Buffer.concat(chunks[1]),packet:Buffer.concat(chunks[2])});});
      child.stdin.on('error',()=>{});child.stdin.end(JSON.stringify(config));
    });
    let payload;
    try{payload=JSON.parse(result.packet.toString('utf8'));}catch{
      payload={version:1,collector:'python-profile-v1',runId:config.runId,entry,sourceHashes:inventory,exitCode:result.code,
        completeWithinScope:false,sourceChanges:[],calculations:[],relationships:[],operations:[],metrics:{},
        coverage:{reason:result.overflow?'Collector output exceeded 16 MB.':'Collector did not produce a complete packet.'},inputs:[]};
    }
    payload.parent={exitCode:result.code,signal:result.signal,timedOut:result.timedOut,outputLimitExceeded:result.overflow,
      stdoutTruncated:result.sizes[0]>4_000_000,stderrTruncated:result.sizes[1]>4_000_000};
    if(payload.runId!==config.runId||payload.entry!==entry||canonical(payload.sourceHashes)!==canonical(inventory))throw Error('Collector packet does not match the launched source/run.');
    payload.completeWithinScope=Boolean(payload.completeWithinScope&&!result.timedOut&&!result.overflow);
    const receipt={version:1,kind:'buildmap-collected-run',collectorId,payload,signature:crypto.sign(null,Buffer.from(canonical(payload)),key).toString('base64')};
    fs.writeFileSync(outputFd,JSON.stringify(receipt,null,2)+'\n');written=true;
    return {receipt,stdout:result.stdout,stderr:result.stderr};
  }finally{fs.closeSync(outputFd);if(!written)fs.unlinkSync(output);}
}

export function verifyCollectedRun(receipt,trust,sourceHashes,calculations=[],checkInput=null) {
  const refuse=reason=>({status:'refused',reason,collectorId:receipt?.collectorId,verifiedSignature:false});
  if(receipt?.version!==1||receipt.kind!=='buildmap-collected-run'||receipt.payload?.version!==1||receipt.payload.collector!=='python-profile-v1')return refuse('Unsupported collector receipt.');
  const keys=trust?.version===1&&Array.isArray(trust.collectors)?trust.collectors.filter(c=>c&&typeof c==='object'&&c.id===receipt.collectorId):[];
  if(keys.length!==1)return refuse('Collector key is unknown or ambiguous.');
  try{const key=crypto.createPublicKey(keys[0].publicKey);if(key.asymmetricKeyType!=='ed25519'||!crypto.verify(null,Buffer.from(canonical(receipt.payload)),key,Buffer.from(receipt.signature,'base64')))return refuse('Collector signature does not match.');}catch{return refuse('Invalid collector key/signature.');}
  const p=receipt.payload;
  if(typeof p.completeWithinScope!=='boolean'||!Array.isArray(p.sourceChanges)||!p.metrics||typeof p.metrics!=='object'||Array.isArray(p.metrics)||!p.coverage||typeof p.coverage!=='object')return refuse('Invalid collected run metadata.');
  for(const [name,value] of Object.entries(p.metrics))if(value!==null&&(typeof value!=='number'||!Number.isFinite(value)||value<0||name==='cpuUtilizationPercent'&&value>100))return refuse('Invalid collected resource metric.');
  if(!p.sourceHashes||typeof p.sourceHashes!=='object'||Array.isArray(p.sourceHashes)||Object.entries(p.sourceHashes).some(([file,h])=>!exact(file)||!/^[a-f0-9]{64}$/.test(h)))return refuse('Invalid collected source identities.');
  const stale=Object.entries(p.sourceHashes).filter(([file,h])=>sourceHashes[file]!==h).map(([file])=>file);
  if(!Array.isArray(p.calculations)||p.calculations.length>10000||!Array.isArray(p.relationships)||p.relationships.length>10000||!Array.isArray(p.operations)||p.operations.length>10000)return refuse('Collected record limits exceeded.');
  const ids=new Set();
  for(const c of p.calculations){
    if(!c||typeof c.id!=='string'||ids.has(c.id)||!exact(c.path)||typeof c.name!=='string'||!Number.isSafeInteger(c.line)||c.line<1||c.sourceHash!==p.sourceHashes[c.path]||!integer(c.calls)||!integer(c.returns)||!integer(c.elapsedNanoseconds)||!Array.isArray(c.inputGroups)||c.inputGroups.length>256)return refuse('Invalid/ambiguous collected calculation.');
    ids.add(c.id);
    for(const g of c.inputGroups)if(!/^[a-f0-9]{64}$/.test(g.inputDigest)||!integer(g.calls)||!Number.isSafeInteger(g.unavailableReturns)||g.unavailableReturns<0||!g.returnDigests||Array.isArray(g.returnDigests)||Object.keys(g.returnDigests).length>256||Object.entries(g.returnDigests).some(([h,n])=>!/^[a-f0-9]{64}$/.test(h)||!integer(n)))return refuse('Invalid collected value identities.');
  }
  if(p.relationships.some(r=>!ids.has(r.from)||!ids.has(r.to)||!Number.isSafeInteger(r.calls)||r.calls<1))return refuse('Invalid collected call relationship.');
  if(p.operations.some(o=>!o||!exact(o.path)||o.calculationId!==null&&!ids.has(o.calculationId)||!Number.isSafeInteger(o.openAttempts)||o.openAttempts<1||o.mode!==null&&typeof o.mode!=='string'))return refuse('Invalid collected file operation.');
  if(!Array.isArray(p.inputs)||p.inputs.length>10000||p.inputs.some(i=>!i||!exact(i.path)||!['current','unavailable','changed-during-run'].includes(i.status)||i.beforeHash!==null&&!/^[a-f0-9]{64}$/.test(i.beforeHash)||i.afterHash!==null&&!/^[a-f0-9]{64}$/.test(i.afterHash)))return refuse('Invalid collected input identities.');
  const inputChecks=p.inputs.map(i=>{let current=false;if(i.status==='current'&&i.afterHash!==null){try{current=checkInput?checkInput(i.path,i.afterHash):null;}catch{current=false;}}return {path:i.path,current};});
  const inputFreshness=!inputChecks.length?'not-required':inputChecks.every(i=>i.current===true)?'current':inputChecks.some(i=>i.current===false)?'stale-or-unavailable':'not-checked';
  const index=new Map();for(const c of calculations){const key=JSON.stringify([c.source.path,c.source.sourceHash,c.name,c.source.line]);if(!index.has(key))index.set(key,[]);index.get(key).push(c);}
  const links=p.calculations.map(c=>{const matches=index.get(JSON.stringify([c.path,c.sourceHash,c.name,c.line]))||[];return {...c,calculationId:matches.length===1?matches[0].id:null,sourceMatch:matches.length===1?'current-declaration':stale.includes(c.path)?'stale':'observed-uncatalogued-declaration'};});
  const eligible=stale.length===0&&['current','not-required'].includes(inputFreshness)&&p.sourceChanges?.length===0&&p.completeWithinScope&&p.exitCode===0&&p.parent?.exitCode===0&&!p.parent?.timedOut;
  return {status:stale.length?'stale':eligible?'verified-collector-current-source':'verified-collector-partial',verifiedSignature:true,collectorId:receipt.collectorId,
    runId:p.runId,entry:p.entry,staleSources:stale,inputFreshness,inputChecks,eligibleForComparison:Boolean(eligible),payload:p,calculations:links,
    limitation:'Signature verifies the configured collector identity and these receipt bytes; it does not certify result correctness or hostile-code isolation.'};
}

export function observedReuseGroups(run) {
  if(!run.eligibleForComparison)return [];
  return run.calculations.filter(c=>!c.resumable).flatMap(c=>c.inputGroups.filter(g=>BigInt(g.calls)>1n).map(g=>({
    calculationId:c.calculationId,observedId:c.id,path:c.path,name:c.name,inputDigest:g.inputDigest,calls:g.calls,
    distinctOutputDigests:Object.keys(g.returnDigests).length,
    stableObservedOutputs:Object.keys(g.returnDigests).length===1&&BigInt(Object.values(g.returnDigests)[0])===BigInt(g.calls)&&g.unavailableReturns===0,
    sourceHash:c.sourceHash,basis:'same directional built-in input identities within this signed finite run',
    review:'Matching outputs in these observations do not prove purity, intentional-observation equivalence or safe caching. Review side effects and product contracts.'
  })));
}

export function compareCollectedRuns(before,after,{calculation=null,codeReview=null}={}) {
  const refused=reason=>({status:'refused',reason,baselineRunId:before?.runId,currentRunId:after?.runId});
  const successful=r=>r?.verifiedSignature&&r.payload?.completeWithinScope&&r.payload.exitCode===0&&r.payload.parent?.exitCode===0&&!r.payload.parent?.timedOut&&r.payload.sourceChanges?.length===0;
  if(!successful(before)||!successful(after)||!['current','not-required'].includes(before.inputFreshness)||!after.eligibleForComparison)return refused('Both runs need successful complete signed observations and current input identities; the candidate source must be current.');
  if(before.runId===after.runId)return refused('Choose distinct collected runs.');
  const a=before.payload,b=after.payload;
  if(a.entry!==b.entry||a.argumentIdentity!==b.argumentIdentity||canonical(a.environment)!==canonical(b.environment))return refused('Entry, exact argument identity or measured environment differ.');
  const knownInputs=r=>Array.isArray(r.inputs)&&r.inputs.every(i=>i.status==='current')&&!r.operations.some(o=>o.mode===null||o.mode.includes('+'));
  if(!knownInputs(a)||!knownInputs(b))return refused('Observed project input identity is incomplete, changed or includes an unclassified descriptor/update-mode open.');
  const inputKey=r=>canonical(r.inputs.map(i=>[i.path,i.beforeHash]).sort(([x],[y])=>x.localeCompare(y)));
  if(inputKey(a)!==inputKey(b))return refused('Observed project input file identities differ.');
  const changed=[...new Set([...Object.keys(a.sourceHashes),...Object.keys(b.sourceHashes)])].filter(p=>a.sourceHashes[p]!==b.sourceHashes[p]).sort();
  if(changed.length&&(!codeReview?.currentBindings||typeof codeReview.note!=='string'||!codeReview.note.trim()||canonical([...(codeReview.paths||[])].sort())!==canonical(changed)||!calculation))return refused('Changed source needs a current bound equivalence review naming every changed path and an observed calculation to compare.');
  let equivalentValues=null;
  if(calculation){
    const candidates=r=>r.calculations.filter(c=>c.path===calculation.path&&c.name===calculation.name&&!c.resumable);
    const left=candidates(a),right=candidates(b);if(left.length!==1||right.length!==1)return refused('No unique non-resumable observed calculation matches both runs.');
    const groups=c=>new Map(c.inputGroups.map(g=>[g.inputDigest,g]));
    const l=groups(left[0]),r=groups(right[0]);
    const covered=c=>c.inputGroups.reduce((n,g)=>n+BigInt(g.calls),0n)===BigInt(c.calls);
    if(!covered(left[0])||!covered(right[0])||l.size===0||l.size!==r.size)return refused('Observed value coverage is incomplete or directional input identities differ.');
    for(const [id,g] of l){const h=r.get(id),lg=Object.keys(g.returnDigests),rg=h&&Object.keys(h.returnDigests);
      if(!h||g.unavailableReturns||h.unavailableReturns||lg.length!==1||rg.length!==1||lg[0]!==rg[0]||g.returnDigests[lg[0]]!==g.calls||h.returnDigests[rg[0]]!==h.calls)return refused('Finite observed input/output identities are unequal, unavailable or nondeterministic.');}
    equivalentValues={path:calculation.path,name:calculation.name,directionalInputGroups:l.size,baselineCalls:left[0].calls,currentCalls:right[0].calls,
      verdict:'equal output identities for the covered finite observations; not general purity/equivalence'};
  }
  return {status:'comparable-signed-observations',baselineRunId:before.runId,currentRunId:after.runId,changedSourcePaths:changed,
    finiteValueComparison:equivalentValues,metricDifferences:Object.fromEntries(['elapsedSeconds','cpuSeconds','cpuUtilizationPercent','peakMemoryBytes'].map(k=>[k,typeof a.metrics[k]==='number'&&typeof b.metrics[k]==='number'?b.metrics[k]-a.metrics[k]:null])),
    scope:'Current minus baseline; exact captured Python/project-input/argument/environment scope. External/transitive/native I/O and observer overhead remain explicit limits. No automatic optimization or reuse activation.'};
}

export function readCollectedRuns(root,sourceHashes,calculations) {
  let analysis,trust;
  try{analysis=JSON.parse(readProjectFile(root,'.buildmap/analysis.json',1_000_000));}catch(e){return {runs:[],diagnostics:e.code==='ENOENT'?[]:[e.message]};}
  const paths=analysis.collectedRuns ?? [];
  if(!Array.isArray(paths)||paths.length>20||paths.some(p=>!exact(p))||new Set(paths).size!==paths.length)return {runs:[],diagnostics:['collectedRuns requires at most 20 unique project-relative receipt paths.']};
  if(!paths.length)return {runs:[],comparisons:[],diagnostics:[]};
  try{trust=JSON.parse(readProjectFile(root,'.buildmap/collectors.json',128_000));}catch(e){return {runs:[],diagnostics:['Collector trust document unavailable: '+e.message]};}
  let bytes=0,inputBytes=0;const runs=[],diagnostics=[],inputCache=new Map();
  const currentInput=(file,expected)=>{if(!inputCache.has(file)){try{if(inputCache.size>=256||inputBytes>=4_000_000)throw Error('Input identity read budget exceeded.');const data=readProjectFile(root,file,1_000_000);inputBytes+=data.length;inputCache.set(file,inputBytes<=4_000_000?hash(data):null);}catch{inputCache.set(file,null);}}return inputCache.get(file)===expected;};
  for(const file of paths){try{const data=readProjectFile(root,file,16_000_000);bytes+=data.length;if(bytes>32_000_000)throw Error('Collected receipt budget exceeds 32 MB.');runs.push({file,...verifyCollectedRun(JSON.parse(data),trust,sourceHashes,calculations,currentInput)});}catch(e){diagnostics.push(`${file}: ${e.message}`);}}
  const comparisons=[];
  const requests=analysis.collectedComparisons ?? [];
  if(!Array.isArray(requests)||requests.length>20)diagnostics.push('collectedComparisons supports at most 20 requests.');
  else for(const request of requests){
    try{
      if(!request||typeof request.baselineRunId!=='string'||typeof request.currentRunId!=='string')throw Error('Comparison requires baselineRunId/currentRunId.');
      const select=id=>runs.filter(r=>r.runId===id);const left=select(request.baselineRunId),right=select(request.currentRunId);
      if(left.length!==1||right.length!==1)throw Error('Comparison run id is missing or ambiguous.');
      let review=null;
      if(request.codeReview){const binding=request.codeReview.bindings;if(!binding||typeof binding!=='object'||Array.isArray(binding)||Object.keys(binding).length===0||Object.keys(binding).length>64)throw Error('Code review needs 1–64 current receipt bindings.');
        let size=0;const current=Object.entries(binding).every(([p,h])=>{const bytes=readProjectFile(root,p,1_000_000);size+=bytes.length;return size<=4_000_000&&hash(bytes)===h;});
        review={...request.codeReview,currentBindings:current};}
      comparisons.push(compareCollectedRuns(left[0],right[0],{calculation:request.calculation,codeReview:review}));
    }catch(e){comparisons.push({status:'refused',reason:e.message});}
  }
  return {runs,comparisons,diagnostics};
}
