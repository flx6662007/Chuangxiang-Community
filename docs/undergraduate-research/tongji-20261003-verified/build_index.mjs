import fs from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import {createRequire} from 'node:module';
import {fileURLToPath,pathToFileURL} from 'node:url';
const req=createRequire(import.meta.url);
const packageDir=process.argv[2]||path.dirname(fileURLToPath(import.meta.url));
const qaDir=process.argv[3]||path.join(packageDir,'.qa');
let lib;
try { lib=req.resolve('@oai/artifact-tool'); }
catch {lib=req.resolve('@oai/artifact-tool',{paths:[path.join(os.homedir(),'.cache/codex-runtimes/codex-primary-runtime/dependencies/node')]});}
const {Workbook,SpreadsheetFile}=await import(pathToFileURL(lib));
const m=JSON.parse(await fs.readFile(path.join(packageDir,'整理底稿.json'),'utf8'));
const wb=Workbook.create();
const toDate=d=>d?new Date(d+'T00:00:00Z'):null;
const col=i=>String.fromCharCode(65+i);
const specs=[
 {name:'科研索引',title:'同济本科科研招募 · 已核查记录',tab:'#087C78',headers:['招募主题','所属单位','时效','原文发布日期','核查日期','科研简介','本科参与与限制','本科依据及核查提示','官方原文链接','稳定编号'],widths:[340,265,112,116,116,390,440,590,420,230],rows:m.records.map(r=>{const c=r.card;return[c.title,c.unit,r.review.temporalStatus,toDate(c.date),toDate(c.verifiedOn),c.summary,c.participation,c.evidenceNote,c.sourceUrl,c.id]}),note:`${m.records.length} 条已核查，其中 ${m.statistics.historicalRecords} 条历史已结束。正文核查不代表当前有空缺；日期空白表示原文未注明。`,linkCol:8,dates:[3,4]},
];
for(const [idx,sp] of specs.entries()){
 const s=wb.worksheets.add(sp.name),last=sp.rows.length+5,end=col(sp.headers.length-1);
 s.showGridLines=false;s.tabColor=sp.tab;
 const used=s.getRange(`A1:${end}${last}`);
 used.format={fill:'#FFFFFF',font:{name:'Microsoft YaHei',size:11,color:'#1C3148'},verticalAlignment:'top',wrapText:true};
 sp.widths.forEach((w,i)=>s.getRange(`${col(i)}1:${col(i)}${last}`).format.columnWidthPx=w);
 s.getRange('A1:D1').merge();s.getRange('A1').values=[[sp.title]];
 s.getRange(`A1:${end}1`).format={fill:'#172B43',font:{size:21,bold:true,color:'#FFFFFF'},rowHeightPx:54,verticalAlignment:'center'};
 s.getRange('A2:D2').merge();s.getRange('A2').values=[[sp.note]];s.getRange(`A2:${end}2`).format={font:{size:11,color:'#53667A'},rowHeightPx:44};
 s.getRange('A3:D3').merge();s.getRange('A3').values=[['事实源：整理底稿.json  |  核查：2026-10-03  |  链接列可复制；可点击来源见 HTML 阅读页']];s.getRange(`A3:${end}3`).format={font:{size:10,color:'#53667A'},rowHeightPx:30};
 s.getRange(`A5:${end}5`).values=[sp.headers];s.getRange(`A6:${end}${last}`).values=sp.rows;
 const table=s.tables.add(`A5:${end}${last}`,true,'ResearchTable'+idx);table.showFilterButton=true;
 s.getRange(`A5:${end}5`).format={fill:'#244C72',font:{bold:true,color:'#FFFFFF'},rowHeightPx:34,verticalAlignment:'center'};
 for(const [i,row] of sp.rows.entries()){
  const height=Math.min(360,Math.max(90,...row.map((v,j)=>{if(v==null||v instanceof Date||typeof v==='number')return 32;return Math.ceil(String(v).split('\n').reduce((sum,l)=>sum+Math.max(1,Math.ceil([...l].reduce((a,c)=>a+(c.charCodeAt(0)>255?11:6),0)/(sp.widths[j]-18))),0)*19+18)})));
  const rg=s.getRange(`A${i+6}:${end}${i+6}`);rg.format.rowHeightPx=height;
  if(i%2===1)rg.format.fill='#F4F7FA';
  const t=sp.name==='科研索引'?row[2]:sp.name==='待核排除'?row[1]:'';
  if(t){const cell=s.getRange(`${sp.name==='科研索引'?'C':'B'}${i+6}`);cell.format={fill:t==='历史已结束'?'#F4E7E6':t==='长期招募'?'#E6F3EF':t==='排除'?'#EAEFF3':'#FFF0D5',font:{bold:true,color:t==='历史已结束'?'#913D38':'#264B51'}};}
 }
 for(const j of sp.dates)s.getRange(`${col(j)}6:${col(j)}${last}`).setNumberFormat('yyyy-mm-dd');
 const lc=col(sp.linkCol);
 s.getRange(`${lc}6:${lc}${last}`).format.font.color='#087C78';
 s.freezePanes.freezeRows(5);s.freezePanes.freezeColumns(1);
}
await wb.recalculate();
await fs.mkdir(qaDir,{recursive:true});
for(const sp of specs){
 const inspection=await wb.inspect({kind:'region',sheetId:sp.name,range:'A5:D8',maxChars:2500,tableMaxRows:4,tableMaxCols:4});
 await fs.writeFile(path.join(qaDir,sp.name+'-inspect.json'),JSON.stringify(inspection,null,2));
 if(process.argv.includes('--render')){
  const preview=await wb.render({sheetName:sp.name,range:'A1:D8',scale:1,format:'png'});
  await fs.writeFile(path.join(qaDir,sp.name+'.png'),new Uint8Array(await preview.arrayBuffer()));
 }
}
const xlsx=await SpreadsheetFile.exportXlsx(wb);await xlsx.save(path.join(packageDir,'总索引.xlsx'));
console.log(JSON.stringify({sheets:specs.map(s=>({name:s.name,rows:s.rows.length})),output:path.join(packageDir,'总索引.xlsx')}));
