// Explicit dogfood evidence authoring after the tests and browser baseline pass.
// This observes only BuildMap's declared inspect-build example, then reviews it.
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import {fileURLToPath} from 'node:url';
import {once} from 'node:events';
import {readIntent} from '../src/intent.js';
import {scanProject} from '../src/scan.js';
import {startServer} from '../src/server.js';
import {snapshotHtml} from '../src/export.js';
import http from 'node:http';
const {chromium}=await import(process.env.BUILDMAP_PLAYWRIGHT_MODULE || 'playwright-core');
const root=fileURLToPath(new URL('../',import.meta.url));
const manifestPath=path.join(root,'.buildmap/project.json'), evidencePath=path.join(root,'.buildmap/evidence.json');
const manifestBytes=await fs.readFile(manifestPath,'utf8'), evidenceBytes=await fs.readFile(evidencePath,'utf8');
const manifest=JSON.parse(manifestBytes), evidence=JSON.parse(evidenceBytes);
assert.equal(manifest.name,'BuildMap');assert.deepEqual(manifest.completion,{label:'MVP',outcomeIds:['inspect-build']});
assert.ok(evidence.outcomes && typeof evidence.outcomes==='object' && !Array.isArray(evidence.outcomes));
assert.ok((await fs.lstat(evidencePath)).isFile() && !(await fs.lstat(evidencePath)).isSymbolicLink());
const digest=bytes=>crypto.createHash('sha256').update(bytes).digest('hex');
const selectedInputs=['.buildmap/project.json','.buildmap/record-mvp-example.mjs','.buildmap/browser-check.mjs','package.json','package-lock.json'];
const inputHashes=Object.fromEntries(await Promise.all(selectedInputs.map(async file=>[file,digest(await fs.readFile(path.join(root,file)))])));
const selected=map=>({fingerprint:map.fingerprint,intent:map.project.intent,finishedProduct:map.project.finishedProduct,
 counts:map.project.counts,pieces:map.nodes.filter(n=>n.kind!=='mission').map(n=>({id:n.id,status:n.status,baseStatus:n.baseStatus,files:n.files,purpose:n.purpose})),
 outcomes:map.outcomes.map(o=>({id:o.id,status:o.status,stepCount:o.steps.length,firstGap:o.firstGap?.label || null})),
 gaps:map.gaps.map(g=>({kind:g.kind,nodeId:g.nodeId,outcomeId:g.outcomeId || null}))});
const intentInput={mission:manifest.mission};
const intentOutput=readIntent(root,manifest);
assert.equal(intentOutput.text,manifest.mission);assert.equal(intentOutput.confidence,'declared');
const map=scanProject(root), outcome=map.outcomes.find(o=>o.id==='inspect-build');
assert.deepEqual(outcome.steps.map(s=>[s.id,s.nodeId]),[['intent','intent'],['scan','scanner'],['serve','server'],['inspect','visualizer']]);
assert.deepEqual(map.project.intent,intentOutput);assert.equal(map.project.counts.verified,5);assert.equal(map.project.counts.live,0);
const scanOutput=selected(map);
const server=startServer({root,port:0});await once(server,'listening');
const url=`http://127.0.0.1:${server.address().port}`;
let browser, exportServer, temporary;
try {
 const response=await fetch(`${url}/api/map`);assert.equal(response.status,200);
 const served=await response.json();assert.deepEqual(selected(served),scanOutput);
 const serveOutput={httpStatus:response.status,...selected(served)};
 browser=await chromium.launch(process.env.BUILDMAP_BROWSER_EXECUTABLE ? {executablePath:process.env.BUILDMAP_BROWSER_EXECUTABLE} : {});
 const page=await browser.newPage({viewport:{width:1440,height:1000}});const errors=[];
 page.on('pageerror',e=>errors.push(e.message));
 const browserMapPromise=page.waitForResponse(r=>r.url()===`${url}/api/map` && r.status()===200);
 await page.goto(url);const browserMap=await (await browserMapPromise).json();assert.deepEqual(selected(browserMap),selected(served));
 await page.locator('#search').fill('Interactive visualizer');await page.locator('#search').press('Enter');
 assert.equal(await page.locator('#detail > h2').innerText(),'Interactive visualizer');
 const visualizer=served.nodes.find(n=>n.id==='visualizer'), pieceText=await page.locator('#detail').innerText();
 assert.ok(pieceText.includes(visualizer.purpose));
 const files=await page.locator('#detail .file-list li').allInnerTexts();assert.deepEqual(files,visualizer.files);
 for(const heading of ['What the files show:','What someone recorded:','Does the record still match?','What it does not establish:']) assert.ok(pieceText.includes(heading));
 await page.locator('#outcomes .outcome-choice').click();
 const title=await page.locator('#detail > h2').innerText();assert.equal(title,outcome.name);
 const labels=await page.locator('.walkthrough-steps h3').allInnerTexts();assert.deepEqual(labels,outcome.steps.map(s=>s.label));
 const samples=await page.locator('.walkthrough-steps li').allInnerTexts();
 const point=await page.locator('.detail-section').filter({has:page.getByRole('heading',{name:'Next point to review',exact:true})}).innerText();
 assert.ok(await page.locator('.finished-product').innerText());
 const inspectInput={fingerprint:browserMap.fingerprint,pieceId:visualizer.id,outcomeId:outcome.id};
 const inspectOutput={piece:{name:visualizer.name,purpose:visualizer.purpose,files},
   evidenceReview:{fileFactsVisible:true,recordDescriptionVisible:true,bindingReviewVisible:true,limitsVisible:true},
   walkthrough:{name:title,labels,recordedSamplesVisible:samples.map(s=>s.includes('Recorded sample')),nextPointShown:point},
   destinationVisible:true,pageErrors:errors};
 assert.deepEqual(errors,[]);
 const proof={status:'verified',recordedAt:new Date().toISOString(),
   command:`node .buildmap/record-mvp-example.mjs (Node ${process.version}; local Chromium ${browser.version()})`,
   note:'A current local intent-to-scan-to-HTTP-to-browser example passed. Selected input/output fields were captured from real calls and browser DOM reads. ReadIntent and scanning read the same manifest; HTTP and browser responses matched the scanner fingerprint and selected fields. The browser located the visualizer, checked its purpose/files/evidence headings, and read the free goal steps, existing reported samples, next review point and intended destination. These are automated visibility/content checks, not a human comprehension study, an instrumented execution trace, independent receipt authentication, exhaustive accessibility/device coverage or live deployment.',
   definitionHash:outcome.definitionHash,sourceHashes:outcome.sourceHashes,inputHashes,
   example:{name:'Open the current local BuildMap MVP and review its visualizer and goal',input:intentInput,output:inspectOutput,steps:[
     {stepId:'intent',result:'observed',input:intentInput,output:intentOutput,note:'Actual readIntent result from the current declared manifest.'},
     {stepId:'scan',result:'observed',handoff:'The scanner read the same root and recovered intent equal to the prior readIntent result; selected snapshot fields were checked.',input:{root},output:scanOutput,note:'Actual scanProject result, selected fields only.'},
     {stepId:'serve',result:'observed',handoff:'GET /api/map on the local server returned a rescanned snapshot whose fingerprint and selected fields equaled the prior scan.',input:{url:`${url}/api/map`,method:'GET'},output:serveOutput,note:'Actual HTTP 200 and selected response fields.'},
     {stepId:'inspect',result:'observed',handoff:'The browser fetched /api/map from that same local origin. Its response fingerprint and selected fields matched the prior HTTP observation; the rendered UI was then inspected.',input:inspectInput,output:inspectOutput,note:'Actual Chromium DOM reads and content assertions; reported samples were read, not re-executed by the viewer.'}
   ]}};
 const updated={...evidence,outcomes:{...evidence.outcomes,'inspect-build':proof},completion:{status:'verified',recordedAt:proof.recordedAt,
   note:'Reviewed only the declared MVP scope against its current complete named inspect-build example. The local browser baseline and visibility/content check support that scoped result; broader roadmap, full accessibility, other devices/browsers and live use are outside this review.',
   definitionHash:map.project.completion.definitionHash,outcomeEvidenceHashes:{'inspect-build':digest(JSON.stringify(proof))}}};
 // Lease the files read at the start; never replace someone else's newer record.
 assert.equal(await fs.readFile(manifestPath,'utf8'),manifestBytes,'The manifest changed during observation.');
 assert.equal(await fs.readFile(evidencePath,'utf8'),evidenceBytes,'The evidence changed during observation.');
 assert.deepEqual(scanProject(root).outcomes.find(o=>o.id===outcome.id).sourceHashes,outcome.sourceHashes,'Implementation changed during observation.');
 for(const [file,hash] of Object.entries(inputHashes)) assert.equal(digest(await fs.readFile(path.join(root,file))),hash,`${file} changed during observation.`);
 temporary=`${evidencePath}.${crypto.randomUUID()}.tmp`;
 await fs.writeFile(temporary,JSON.stringify(updated,null,2)+'\n',{flag:'wx',mode:(await fs.stat(evidencePath)).mode & 0o777});
 assert.equal(await fs.readFile(evidencePath,'utf8'),evidenceBytes,'The evidence changed before saving.');
 await fs.rename(temporary,evidencePath);temporary=null;
 const checked=scanProject(root);assert.equal(checked.outcomes.find(o=>o.id===outcome.id).status,'verified');assert.equal(checked.project.completion.status,'verified');
 assert.equal(checked.nodes.find(n=>n.kind==='mission').status,'planned');assert.equal(checked.project.counts.live,0);
 await page.locator('.node.mission .status-chip').filter({hasText:/MVP verified/i}).waitFor();
 await page.locator('#search').fill('');
 await page.locator('.node.mission').click();assert.ok((await page.locator('.completion-review').innerText()).includes('current verified walkthrough examples'));
 await page.locator('.completion-review button').click();assert.ok((await page.locator('#detail').innerText()).includes('All steps and handoffs have a current recorded example'));
 // Observe the completed scope in the shared export client without writing HTML.
 const html=snapshotHtml(checked);
 exportServer=http.createServer((req,res)=>{res.writeHead(200,{'content-type':'text/html; charset=utf-8'});res.end(html);}).listen(0,'127.0.0.1');await once(exportServer,'listening');
 const offline=await browser.newPage({viewport:{width:390,height:844}});
 await offline.goto(`http://127.0.0.1:${exportServer.address().port}`);
 await offline.locator('.node.mission .status-chip').filter({hasText:/MVP verified/i}).waitFor();await offline.locator('.node.mission').click();
 await offline.locator('.completion-review button').click();assert.equal(await offline.locator('.walkthrough-steps li').count(),4);
 assert.equal(await offline.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
 if(process.env.BUILDMAP_BROWSER_REPORT) await fs.writeFile(process.env.BUILDMAP_BROWSER_REPORT,JSON.stringify({recordedAt:proof.recordedAt,browser:browser.version(),node:process.version,
   outcomeStatus:checked.outcomes.find(o=>o.id===outcome.id).status,completionStatus:checked.project.completion.status,missionState:'planned',live:0,
   sourceHashes:outcome.sourceHashes,inputHashes,checks:['Complete real four-step selected-field example','Current explicit completion review','Live final-box refresh and goal link','390px in-memory export completion and goal link'],scope:proof.note},null,2)+'\n');
 console.log('Recorded the complete current MVP example; final box shows MVP verified in live and exported views. No live claim.');
} finally {
 await browser?.close();if(exportServer)await new Promise(resolve=>exportServer.close(resolve));
 await new Promise(resolve=>server.close(resolve));if(temporary)await fs.rm(temporary,{force:true});
}
