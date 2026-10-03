import fs from 'node:fs/promises';
import path from 'node:path';
import {createRequire} from 'node:module';
import {pathToFileURL} from 'node:url';

if (!process.argv[2] || !process.argv[3]) throw new Error('Usage: node build-research-index.mjs PACKAGE_ROOT BUNDLED_NODE_MODULES');
const root = path.resolve(process.argv[2]);
const requireRuntime = createRequire(path.join(path.dirname(path.resolve(process.argv[3])), 'package.json'));
const {Workbook, SpreadsheetFile} = await import(pathToFileURL(requireRuntime.resolve('@oai/artifact-tool')).href);
const data = JSON.parse(await fs.readFile(path.join(root, '整理底稿.json'), 'utf8'));
const rows = JSON.parse(await fs.readFile(path.join(root, '索引数据.json'), 'utf8'));
const wb = Workbook.create();
const index = wb.worksheets.add('赛事总索引');
const learning = wb.worksheets.add('学习资源');
const resources = new Map(data.resources.map(r => [r.id, r]));
const learningRows = data.entries.flatMap(e => e.learning.map(l => {
  const r = resources.get(l.resource_id);
  return [e.code, l.order, r.title, r.kind, r.summary, l.reason, r.scope, r.prerequisites,
    r.how_to_start, r.language, r.access, r.url, r.provider, r.checked_on];
}));
function layout(sheet, title, headers, values, widths, tableName) {
  sheet.showGridLines = false;
  sheet.getRangeByIndexes(0, 0, values.length + 7, headers.length).format.font = {name:'Microsoft YaHei',size:11,color:'#243B53'};
  sheet.mergeCells('A1:H2'); sheet.getRange('A1').values = [[title]];
  sheet.getRange('A1:H2').format = {fill:'#173B55',font:{name:'Microsoft YaHei',size:21,bold:true,color:'#FFFFFF'},verticalAlignment:'center'};
  sheet.mergeCells('A3:H3'); sheet.getRange('A3').values = [['2026-10-03核验。按实际届次使用；资料待审核，仍有细则缺口。']];
  sheet.getRange('A3:H3').format = {rowHeight:32,font:{name:'Microsoft YaHei',size:10,color:'#60758A'}};
  sheet.getRangeByIndexes(6,0,1,headers.length).values = [headers];
  sheet.getRangeByIndexes(7,0,values.length,headers.length).values = values;
  sheet.getRangeByIndexes(6,0,values.length+1,headers.length).format.wrapText = true;
  sheet.getRangeByIndexes(6,0,1,headers.length).format = {fill:'#267D91',font:{name:'Microsoft YaHei',bold:true,color:'#FFFFFF'},rowHeight:35,wrapText:true};
  sheet.getRangeByIndexes(7,0,values.length,headers.length).format.verticalAlignment = 'top';
  widths.forEach((width,i) => sheet.getRangeByIndexes(0,i,values.length+7,1).format.columnWidthPx = width);
  values.forEach((row,i) => {
    const lines = Math.max(...row.map((cell,j) => String(cell ?? '').split('\n').reduce((n,line) => n + Math.max(1,Math.ceil(line.length / Math.max(6,Math.floor(widths[j]/12)))),0)));
    sheet.getRangeByIndexes(i+7,0,1,headers.length).format.rowHeight = Math.max(90,lines*17+15);
    if (i % 2) sheet.getRangeByIndexes(i+7,0,1,headers.length).format.fill = '#F0F5F9';
  });
  const end = String.fromCharCode(64+headers.length);
  const table = sheet.tables.add(`A7:${end}${values.length+7}`,true,tableName);
  table.showFilterButton = true; table.style = 'TableStyleLight9';
  sheet.freezePanes.freezeRows(7); sheet.freezePanes.freezeColumns(2);
}
layout(index,`同济2026 · 第${data.catalog_scope.start}—${data.catalog_scope.end}项赛事资料`,
  ['批次','目录编号','赛事原名','采用资料届次','2026资料情况','证据状态','学习份数','审核状态','缺口与限制','主来源URL','阅读版路径','责任学院','目录等级','报名入口／指引','报名方式','报名／提交时间说明'],
  rows.map(r => [r.batch,r.code,r.name,r.edition,r.current_status,r.evidence,r.resources,r.review,r.gaps,r.source,r.file,r.departments,r.grade,
    r.registration.registration_url || '',r.registration.registration_method || '尚未明确',
    `报名日期：${r.registration.registration_deadline || '未给出精确日期'}\n提交日期：${r.registration.submission_deadline || '未给出精确日期'}\n${r.registration.deadline_notes || ''}`]),
  [55,95,330,240,230,190,75,100,580,380,330,170,75,380,420,480],'ResearchCatalog');
const last = rows.length + 7;
index.getRange('A5').values = [['覆盖项数']];index.getRange('B5').formulas = [[`=COUNTA(B8:B${last})`]];
index.getRange('D5').values = [['学习关联数']];index.getRange('E5').formulas = [[`=SUM(G8:G${last})`]];
index.getRange('F5').values = [['少于3份']];index.getRange('G5').formulas = [[`=COUNTIF(G8:G${last},"<3")`]];
index.getRange('A5:H5').format = {fill:'#E3EFF3',font:{name:'Microsoft YaHei',bold:true,color:'#173B55'},rowHeight:30};
index.getRange('E5').format.horizontalAlignment = 'left';
index.getRange(`G8:G${last}`).conditionalFormats.add('cellIs',{operator:'lessThan',formula:3,format:{fill:'#FFE1D5',font:{color:'#9B3623',bold:true}}});
layout(learning,'精选学习资料 · 适用范围与入门顺序',
  ['目录编号','顺序','资源名称','类型','中文摘要','推荐理由','适用届次／范围','基础要求','建议入门顺序','语言','访问条件','资源URL','发布方','核验日期'],
  learningRows,[95,55,340,110,420,460,400,300,450,130,430,400,220,120],'ResearchLearning');
learning.getRange('A5').values = [['学习关联数']];learning.getRange('B5').formulas = [[`=COUNTA(A8:A${learningRows.length+7})`]];
learning.getRange('D5').values = [['去重资源数']];learning.getRange('E5').values = [[data.resources.length]];
wb.recalculate();
const summary = await wb.inspect({kind:'region',sheetId:'赛事总索引',range:'A5:H5',maxChars:2500});
const errors = await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!',options:{useRegex:true,maxResults:100}});
await fs.mkdir(path.join(root,'验收报告'),{recursive:true});
await fs.writeFile(path.join(root,'验收报告','工作簿检查.json'),JSON.stringify({summary,errors},null,2));
console.log(JSON.stringify(summary));
const previewRoot = path.join(root,'验收报告','索引预览');await fs.mkdir(previewRoot,{recursive:true});
for (const [sheetName,range,label] of [['赛事总索引','A1:H12','总索引'],['学习资源','A1:H10','学习资源']]) {
  const rendered = await wb.render({sheetName,range,scale:1,format:'png'});
  await fs.writeFile(path.join(previewRoot,label+'.png'),new Uint8Array(await rendered.arrayBuffer()));
}
const exported = await SpreadsheetFile.exportXlsx(wb);await exported.save(path.join(root,'总索引.xlsx'));
console.log(JSON.stringify({rows:rows.length,learningRows:learningRows.length,uniqueResources:data.resources.length,output:path.join(root,'总索引.xlsx')}));
