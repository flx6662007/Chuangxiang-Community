"""Offline validation; Python 3 standard library only. Does not modify the package."""
from pathlib import Path
from collections import Counter
from datetime import date
from html.parser import HTMLParser
from urllib.parse import urlsplit, unquote
import csv, hashlib, json, re, sys, zipfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent
FIELDS = {'id','title','unit','summary','participation','evidenceNote','date','verifiedOn','sourceUrl'}
NS = {'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
MANIFESTS = {'文件清单.json','文件清单.sha256'}

def read(name):
    return json.loads((ROOT/name).read_text(encoding='utf-8-sig'))

def sha(data):
    return hashlib.sha256(data).hexdigest()

def normalized(data):
    return data.decode('utf-8-sig').replace('\r\n','\n').replace('\r','\n').encode('utf-8')

class Page(HTMLParser):
    def __init__(self):
        super().__init__(); self.links=[]
    def handle_starttag(self, tag, attrs):
        for k,v in attrs:
            if k in ('href','src') and v:
                self.links.append(v)

def validate(check_manifest=True):
    checks=0
    def require(cond, label):
        nonlocal checks
        if not cond: raise ValueError(label)
        checks+=1
    m=read('整理底稿.json'); records=m['records']; cards=[r['card'] for r in records]
    require(len(records)==90, '90 records')
    require(len({c['id'] for c in cards})==90, 'unique IDs')
    require(read('科研卡片候选.json')=={'laboratories':cards}, 'nine-field export equals master')
    require(Counter(r['review']['temporalStatus'] for r in records)=={'长期招募':44,'时效待确认':31,'历史已结束':15}, 'temporal totals')
    require(len(m['baselineSixReview'])==6, 'six baseline reviews')
    require({'tongji-li-bing','tongji-jiang-shuo','tongji-meng-xiangzhou','tongji-evs','tongji-nanophononics','tongji-ipoe'} <= {c['id'] for c in cards}, 'stable baseline IDs')
    require(m['attachments']==[], 'zero downloaded attachments')
    sources={s['id']:s for s in m['sources']}
    require(len(sources)==len(m['sources'])==91, '91 unique related sources')
    require(set(sources)=={sid for r in records for sid in r['review']['sourceIds']}, 'only referenced sources')
    with (ROOT/'来源清单.csv').open(encoding='utf-8-sig',newline='') as f:
        rows=list(csv.reader(f))
    require(len(rows)==92 and {r[0] for r in rows[1:]}==set(sources), 'source CSV matches master')
    for r in records:
        c=r['card']; v=r['review']; rid=c['id']
        require(set(c)==FIELDS and all(isinstance(x,str) for x in c.values()), rid+' fields')
        require(v['decision']=='已核查' and v['readingLevel']=='官方正文已读', rid+' verified only')
        require(bool(v['undergraduateEvidence']) and bool(v['evidenceLocation']), rid+' evidence')
        require(c['sourceUrl'] in v['sourceUrls'], rid+' main source')
        require(all(s in sources for s in v['sourceIds']), rid+' source references')
        require(c['verifiedOn']=='2026-10-03', rid+' verification date')
        require(not c['date'] or date.fromisoformat(c['date'])<=date.fromisoformat(c['verifiedOn']), rid+' publication date')
        require(read('逐项档案/'+rid+'.json')==r, rid+' archive JSON matches master')
        p=(ROOT/'逐项档案'/f'{rid}.html').read_text(encoding='utf-8')
        require(c['sourceUrl'].replace('&','&amp;') in p, rid+' archive official source')
    text=(ROOT/'开始阅读.html').read_text(encoding='utf-8')
    embedded=re.search(r'<script id="records" type="application/json">(.*?)</script>',text,re.S)
    require(embedded is not None and json.loads(embedded[1])==records, 'HTML records match master')
    require('待核与排除.html' not in text and '院系覆盖与检索.html' not in text, 'verified-only navigation')
    local_links=0
    for f in ROOT.rglob('*.html'):
        page=Page();page.feed(f.read_text(encoding='utf-8'))
        for link in page.links:
            u=urlsplit(link)
            if not u.scheme and not u.netloc and u.path:
                require((f.parent/unquote(u.path)).resolve().is_file(), str(f.relative_to(ROOT))+' local link '+link)
                local_links+=1
    with zipfile.ZipFile(ROOT/'总索引.xlsx') as z:
        require(z.testzip() is None, 'XLSX CRC')
        book=ET.fromstring(z.read('xl/workbook.xml'))
        sheets=book.findall('s:sheets/s:sheet',NS)
        require(len(sheets)==1 and sheets[0].get('name')=='科研索引', 'one verified-only sheet')
        strings=[]
        if 'xl/sharedStrings.xml' in z.namelist():
            strings=[''.join(x.itertext()) for x in ET.fromstring(z.read('xl/sharedStrings.xml')).findall('s:si',NS)]
        xml=ET.fromstring(z.read('xl/worksheets/sheet1.xml'))
        cells={}
        for cell in xml.findall('.//s:sheetData/s:row/s:c',NS):
            v=cell.find('s:v',NS); val=v.text if v is not None else ''
            if cell.get('t')=='s': val=strings[int(val)]
            elif cell.get('t')=='inlineStr': val=''.join(cell.find('s:is',NS).itertext())
            require(cell.get('t')!='e' and cell.find('s:f',NS) is None, 'no cell error or unsupported formula')
            cells[cell.get('r')]=val or ''
        require(len([x for x in xml.findall('s:sheetData/s:row',NS) if int(x.get('r'))>=6])==90, '90 Excel data rows')
        for i,r in enumerate(records,6):
            c=r['card']
            vals=[c['title'],c['unit'],r['review']['temporalStatus'],c['date'],c['verifiedOn'],c['summary'],c['participation'],c['evidenceNote'],c['sourceUrl'],c['id']]
            for j,val in enumerate(vals):
                actual=cells.get(chr(65+j)+str(i),'')
                if j in (3,4) and val:
                    require(float(actual)==(date.fromisoformat(val)-date(1899,12,30)).days, f'Excel date {i}:{j}')
                else: require(actual==val, f'Excel content {i}:{j}')
    manifest_files=0; raw_matches=0
    if check_manifest:
        manifest=read('文件清单.json'); paths={x['path'] for x in manifest['files']}
        actual={f.relative_to(ROOT).as_posix() for f in ROOT.rglob('*') if f.is_file() and f.name not in MANIFESTS}
        require(paths==actual, 'manifest file set')
        for entry in manifest['files']:
            f=(ROOT/entry['path']).resolve()
            require(f.is_relative_to(ROOT), 'manifest path stays inside package')
            b=f.read_bytes(); raw=sha(b)==entry['sha256'];raw_matches+=raw
            norm=entry.get('normalizedUtf8LfSha256')
            require(raw or bool(norm and sha(normalized(b))==norm), entry['path']+' SHA-256')
            manifest_files+=1
        expected=''.join(f"{e['sha256']}  {e['path']}\n" for e in manifest['files'])
        require((ROOT/'文件清单.sha256').read_text(encoding='utf-8')==expected, 'SHA-256 text manifest matches JSON')
    return {'passed':True,'records':90,'sources':91,'checks':checks,'localHtmlLinks':local_links,'manifestFiles':manifest_files,'rawHashMatches':raw_matches,'spreadsheet':{'sheets':1,'rows':90,'cellValuesChecked':900}}

if __name__=='__main__':
    try: print(json.dumps(validate(),ensure_ascii=False))
    except Exception as e:
        print('FAIL: '+str(e),file=sys.stderr);sys.exit(1)
