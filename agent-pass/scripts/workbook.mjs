import fs from 'node:fs/promises';
import {createRequire} from 'node:module';
const require=createRequire('C:/Users/A/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/package.json');
const {Workbook,SpreadsheetFile}=require('@oai/artifact-tool');
const root=new URL('../',import.meta.url);
const input=JSON.parse(await fs.readFile(new URL('cache/workbook-input.json',root),'utf8'));
const wb=Workbook.create();let n=0;
for(const table of input){
 const name=(String(++n).padStart(2,'0')+' '+table.file.replace('.csv','')).slice(0,31);
 const sh=wb.worksheets.add(name);sh.showGridLines=false;
 const a=[table.columns,...table.rows];sh.getRangeByIndexes(0,0,a.length,table.columns.length).values=a;
 const header=sh.getRangeByIndexes(0,0,1,table.columns.length);
 header.format={fill:'#203A52',font:{name:'Arial',size:10,bold:true,color:'#FFFFFF'},wrapText:true,rowHeight:45};
 sh.getUsedRange().format.columnWidth=21;sh.getUsedRange().format.font.name='Arial';sh.getUsedRange().format.font.size=10;
 for(let c=0;c<table.columns.length;c++){
  const key=table.columns[c], vals=table.rows.map(r=>r[c]);
  const col=sh.getRangeByIndexes(0,c,a.length,1);
  if(key.includes('candidate_id')) col.format.columnWidth=32;
  if(key.endsWith('_ns')) {col.format.columnWidth=31;col.setNumberFormat('@');}
  else if(key==='figure') col.format.columnWidth=61;
  else if(vals.some(v=>typeof v==='number'&&!Number.isInteger(v))) col.setNumberFormat('0.000000');
  else col.setNumberFormat('0');
 }
 sh.freezePanes.freezeRows(1);sh.freezePanes.freezeColumns(2);
 sh.getRangeByIndexes(0,table.columns.length+1,1,1).values=[['Source: agent-pass/tables/; '+(table.sources||[table.file]).join(', ')+'; pinned inputs in source-manifest.json']];
 sh.getRangeByIndexes(0,table.columns.length+1,1,1).format.columnWidth=100;
}
wb.recalculate();
console.log((await wb.inspect({kind:'sheet',include:'id,name',maxChars:2000})).ndjson);
for(let i=0;i<input.length;i++){
 const sh=wb.worksheets.getItemAt(i);
 const p=await wb.render({sheetName:sh.name,range:'A1:F9',scale:1,format:'png'});
 await fs.writeFile(new URL('cache/workbook-preview-'+i+'.png',root),new Uint8Array(await p.arrayBuffer()));
}
console.log((await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#NUM!',options:{useRegex:true,maxResults:10},maxChars:1000})).ndjson);
await (await SpreadsheetFile.exportXlsx(wb)).save(new URL('research-tables.xlsx',root).pathname.replace(/^\/([A-Za-z]:)/,'$1'));
console.log('Exported '+input.length+' tables, '+input.reduce((s,t)=>s+t.rows.length,0)+' source rows');

