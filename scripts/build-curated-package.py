"""从人工维护的 JSON 底稿生成阅读版和导入清单；不访问网络，不写数据库。"""
import argparse
import hashlib
import html
import json
from pathlib import Path
from collections import Counter
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from curation.product import render_edition, render_resource

STATUS = {'rules':'已取得规则或正式通知','partial':'部分资料，细则有缺口','report':'仅取得活动报道','identity':'赛事身份待确认'}
KNOWN_ROUTE_STATUSES = {'公告显示开放','对应届次已截止','已确认渠道，期限待核','校内推荐安排待核'}
FIELD_LABELS = dict(title='现用赛事名',edition='实际届次',summary='简述',description='详情',level='赛事级别',
    organizer='主办承办单位',tracks='赛道与分组',eligibility='参赛资格',participation_type='参赛形式',
    team_size_min='队伍最少人数',team_size_max='队伍最多人数',registration_method='报名与材料要求',
    registration_url='报名入口',campus_arrangements='同济校内安排',registration_deadline='报名截止日期',
    submission_deadline='作品提交截止日期',campus_deadline='校内截止日期',deadline_notes='日期说明',
    registration_deadline_at='报名截止时刻',submission_deadline_at='提交截止时刻',campus_deadline_at='校内截止时刻',
    registration_deadline_timezone='报名来源时区',submission_deadline_timezone='提交来源时区',campus_deadline_timezone='校内来源时区')

def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')

def text_resource(r):
    return render_resource(r)

def source_lines(s):
    return f"{s['id']}｜{s['title']}｜发布：{s.get('publisher') or '待核'}｜发布日期：{s.get('published_on') or '未核实'}｜核验：{s['checked_on']}\n{s['url']}\n定位：{s['locator']}"

def page(title, content):
    return '<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+html.escape(title)+'</title><style>body{max-width:1180px;margin:40px auto;padding:0 24px;font:16px/1.8 system-ui,"Microsoft YaHei",sans-serif;color:#223347;background:#f5f7fa}header,section{background:white;padding:24px 30px;margin-bottom:20px;border-radius:10px}h1{font-size:26px;line-height:1.4}h2{font-size:21px}a{color:#1764a0}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:inherit}table{border-collapse:collapse;width:100%;font-size:14px}td,th{padding:10px;border-bottom:1px solid #d9e2eb;text-align:left;vertical-align:top}.badge{color:#805315;background:#fff1d6;padding:5px 9px;border-radius:5px}.small{font-size:13px;color:#536679}.table-scroll{overflow-x:auto}.catalog-table{min-width:1030px}.catalog-table td:nth-child(2){min-width:210px}.controls{display:flex;gap:12px;margin:15px 0}.controls input{flex:1;min-width:100px}.controls input,.controls select{font:inherit;padding:8px;border:1px solid #bccada;border-radius:5px}.entry-link{display:inline-block;padding:8px 14px;background:#e9f1f8;border-radius:5px;font-weight:600}.route-details{border-left:3px solid #c8d8e7;padding-left:18px}tr[hidden]{display:none}@media(max-width:700px){body{padding:0 12px;margin:20px auto}header,section{padding:18px}.controls{display:block}.controls>*{box-sizing:border-box;width:100%;margin:5px 0}}</style>'+content+'</html>'

def pre(text): return '<pre>'+html.escape(text)+'</pre>'
def section(title, text): return '<section><h2>'+html.escape(title)+'</h2>'+pre(text)+'</section>'

def attachment_urls(a): return set([a['url']]+a.get('url_aliases',[]))

def attachment_links(items, prefix):
    links=''.join('<p><a href="'+prefix+html.escape(a['path'],quote=True)+'">'+html.escape(a['original_filename'])+'</a>'+(' <a href="'+prefix+html.escape(a['text_path'],quote=True)+'">提取文本（待审核）</a>' if a.get('text_path') else '')+'</p>' for a in items)
    return '<details><summary>展开 '+str(len(items))+' 份附件</summary>'+links+'</details>' if len(items)>8 else links

def registration_default():
    return dict(edition='未核定',status='待核对',kind='未核定',url='',
        method='本轮尚未核定报名路径，不能据此认定没有报名渠道。',
        timing='报名届次、截止时间和开放状态待核。',sources=[],checked_on=None)

def registration_text(entry, route, sources):
    adopted=next(ed for ed in entry['editions'] if ed['id']==entry['adopted_edition_id'])
    lines=[f"目录编号：{entry['code']}",f"赛事名称：{entry['name']}",
        '目录年份：2026',f"原档案采用资料：{adopted['label']}",f"报名信息适用届次：{route['edition']}",
        f"报名核对结果：{route['status']}",f"报名方式：{route['kind']}",
        f"报名入口／官方指引：{route['url'] or '尚未核定'}",f"操作说明：{route['method']}",
        f"时间与限制：{route['timing']}",f"核验日期：{route.get('checked_on') or '未核验'}",
        '报名信息与原档案按各自适用届次阅读，不将不同届次的规则或截止时间拼接。',
        '开放状态依据核验日的官方公告，未登录提交或缴费；资料待审核。']
    if route.get('source_note'):lines.append('附件说明：'+route['source_note'])
    if sources:lines.extend(['','报名信息依据：','\n\n'.join(source_lines(s) for s in sources)])
    return '\n'.join(lines)

def registration_section(route, sources, adopted_label, local_source):
    out='<section id="registration"><h2>报名入口与方式</h2>'
    out+='<p><span class="badge">'+html.escape(route['status'])+'</span>　适用：'+html.escape(route['edition'])+'</p>'
    out+='<p class="small">赛事档案采用 '+html.escape(adopted_label)+'；报名信息按这里标明的届次单独适用。</p>'
    if route['url']:
        label='打开报名入口／官方指引'
        if route['status']=='仅发现导航，待核':label='查看官网报名导航（待核）'
        if route['status']=='仅活动申请，非独立报名':label='查看夏令营申请（非独立竞赛报名）'
        out+='<p><a class="entry-link" target="_blank" rel="noopener noreferrer" href="'+html.escape(route['url'],quote=True)+'">'+label+'</a></p>'
    out+='<div class="route-details"><p><strong>'+html.escape(route['kind'])+'</strong></p><p>'+html.escape(route['method'])+'</p><p>'+html.escape(route['timing'])+'</p></div>'
    if sources:
        out+='<p>'+ '　'.join('<a target="_blank" rel="noopener noreferrer" href="'+html.escape(s['url'],quote=True)+'">依据'+str(i+1)+'：'+html.escape(s['title'])+'</a>' for i,s in enumerate(sources))+'</p>'
    if local_source:
        out+='<p><a href="../../'+html.escape(local_source,quote=True)+'">查看已留存的原始报名通知</a></p>'
    out+='<p class="small">核验：'+html.escape(route.get('checked_on') or '未核验')+'。开放状态仅依据公告，未登录提交或缴费；资料待审核。</p></section>'
    return out

def build(filename):
    root=filename.resolve().parent
    data=json.loads(filename.read_text(encoding='utf-8-sig'))
    entries=data['entries'];resources={r['id']:r for r in data['resources']}
    scope=data.get('work_scope',{})
    deferred=set(scope.get('deferred_numbers',[]))
    active_codes={e['code'] for e in entries if e['number'] not in deferred}
    assert len(entries)==125 and {e['number'] for e in entries}==set(range(131,256))
    registration_review=data.get('registration_review',{})
    registration_records=registration_review.get('records',[])
    registration_by_number={r['number']:r for r in registration_records}
    assert len(registration_by_number)==len(registration_records), '重复的报名信息目录编号'
    assert set(registration_by_number)<={e['number'] for e in entries}, '报名信息超出目录范围'
    known_sources={s['url']:s for e in entries for ed in e['editions'] for s in ed['sources']}
    manifest=dict(schema_version=1,package_id=data['package_id'],review=data['review'],catalog=[],competitions=[],resources=[],documents=[])
    used={};index=[]
    for entry in entries:
        code=entry['code']; adopted=next(e for e in entry['editions'] if e['id']==entry['adopted_edition_id'])
        manifest['catalog'].append({k:entry[k] for k in ['code','name','grade','levels','departments']} | {'source_url':data['catalog_source_url']})
        competition_codes=[]
        for ed in entry['editions']:
            folder=root/'赛事档案'/code/ed['id'];folder.mkdir(parents=True,exist_ok=True)
            event_code='curated-'+ed['id']
            actual=entry['identity_status']!='unconfirmed' and ed['year'] is not None and ed['evidence_status']!='identity'
            historical=ed['year'] is not None and ed['year']<2026
            caveat='历史资料：仅适用于'+ed['label']+'，不得作为2026当前报名依据。' if historical else '资料仅适用于'+ed['label']+'；日期以来源对应届次为准。'
            facts='\n'.join(f"• {f['text']} [{f['source_id']}；{f['locator']}]" for f in ed['facts'])
            fields='\n'.join(FIELD_LABELS.get(k,k)+'：'+str({'individual':'个人赛','team':'团队赛','both':'个人或团队',
                'university':'校级','national':'全国','international':'国际'}.get(v,v) if isinstance(v,str) else v) for k,v in ed['fields'].items())
            body=render_edition(entry, ed)
            if actual:
                fields_out={'title':entry.get('current_name') or entry['name'],'edition':ed['label'],
                    'summary':ed['summary'][:500],'description':body,'deadline_notes':caveat+'\n'+'\n'.join(ed['gaps'])}
                fields_out.update(ed['fields'])
                src=[]
                for i,s in enumerate(ed['sources']):
                    src.append({'source_type':'campus' if '.edu.cn' in s['url'] else 'official',
                        'source_name':(s.get('publisher') or s['title'])[:200], 'source_url':s['url'],
                        'is_primary':i==0,'source_published_on':s.get('published_on')})
                manifest['competitions'].append(dict(code=event_code,catalog_codes=[code],fields=fields_out,sources=src))
                competition_codes.append(event_code)
            attachments=[a for a in data['attachments'] if code in a['catalog_codes'] and a.get('status')=='archived' and any(s['url'] in attachment_urls(a) for s in ed['sources'])]
            doc=dict(code='doc-'+ed['id'],title=entry['name']+'｜'+ed['label'],body=body,edition=ed['label'],
                catalog_codes=[code],competition_codes=[event_code] if actual else [],resource_codes=[],sources=ed['sources'],
                attachments=attachments,metadata={'historical':historical,'evidence_status':ed['evidence_status'],
                    'review_status':'pending','facts':ed['facts'],'requirements':ed.get('requirements',{}),
                    'gaps':ed['gaps'],'catalog_year':2026})
            manifest['documents'].append(doc)
            (folder/'赛事说明.txt').write_text(body,encoding='utf-8')
            (folder/'来源清单.txt').write_text('\n\n'.join(source_lines(s) for s in ed['sources']),encoding='utf-8')
            parts='<header><p><a href="../index.html">返回赛事主页</a>　<a href="../index.html#registration">查看报名入口与适用届次</a>　<a href="../index.html#learning">学习资料</a></p><h1>'+html.escape(doc['title'])+'</h1><span class="badge">待审核 · '+STATUS[ed['evidence_status']]+'</span></header>'+section('赛事档案',body)
            parts+='<section><h2>来源与附件</h2>'+''.join('<p><a href="'+html.escape(s['url'],quote=True)+'">'+html.escape(s['title'])+'</a><br><span class="small">'+html.escape(source_lines(s).split('\n')[0])+'</span></p>' for s in ed['sources'])
            parts+=attachment_links(attachments,'../../../')+'</section>'
            (folder/'赛事说明.html').write_text(page(doc['title'],parts),encoding='utf-8')
        reading=[]; reading_html=[]
        for item in entry['learning']:
            r=resources[item['resource_id']];reading.append(str(item['order'])+'. '+text_resource(r)+'\n本项推荐理由：'+item['reason'])
            block='<section><h2>'+str(item['order'])+'. '+html.escape(r['title'])+'</h2>'+pre(text_resource(r)+'\n本项推荐理由：'+item['reason'])
            block+='<p><a href="'+html.escape(r['url'],quote=True)+'">打开资源原文</a></p>'
            block+=attachment_links([a for a in data['attachments'] if a.get('status')=='archived' and r['url'] in attachment_urls(a)],'../../')
            reading_html.append(block+'</section>')
            use=used.setdefault(r['id'],{'catalog_codes':[],'competition_codes':[]})
            use['catalog_codes'].append(code)
            # Resources retain their own edition/scope in text and link to catalog identity.
            # Do not automatically bind every historical resource to every competition edition.
        learning='\n\n'.join(reading)
        p=root/'赛事档案'/code
        route=registration_default()
        observed=registration_by_number.get(entry['number'])
        if observed:route.update(observed,checked_on=registration_review.get('checked_on'))
        if entry['number'] in deferred:
            route['status']='用户暂缓';route['method']='本轮按用户要求暂缓补查。原有资料保留，报名信息未重新复核。'
        route_sources=[]
        for i,url in enumerate(route['sources']):
            source=dict(known_sources.get(url) or dict(id='reg-src-'+hashlib.sha256(url.encode()).hexdigest()[:16],
                url=url,title=entry['name']+'报名相关来源（发布单位待核）',publisher=None,published_on=None,
                locator='报名方式、提交要求和时间安排相关段落'))
            source['checked_on']=route['checked_on']
            route_sources.append(source)
        route_attachments=[]
        if route.get('local_source'):
            route_attachments=[a for a in data['attachments'] if a.get('status')=='archived' and code in a['catalog_codes']
                and a['original_filename']==Path(route['local_source']).name]
        route_local_source=route_attachments[0]['path'] if route_attachments else route.get('local_source')
        route_body=registration_text(entry,route,route_sources)
        (p/'报名说明.txt').write_text(route_body,encoding='utf-8')
        if observed:
            manifest['documents'].append(dict(code='registration-'+code,title=entry['name']+'｜报名入口与方式',
                body=route_body,edition=route['edition'],catalog_codes=[code],competition_codes=[],resource_codes=[],
                sources=route_sources,attachments=route_attachments,
                metadata={'scope':'报名路径核对；按声明届次适用，不替换既有届次规则','catalog_year':2026,
                    'review_status':'pending','registration_review':route}))
        (p/'学习资料导读.txt').write_text(learning,encoding='utf-8')
        if len(entry['learning'])<3:
            entry['gaps']=list(dict.fromkeys(entry['gaps']+['有效学习资料少于3份；未用泛泛链接补足，仍需补对应题库或实操课程。']))
        (p/'缺口与检索记录.txt').write_text('缺口：\n'+'\n'.join(entry['gaps'])+'\n\n检索记录：\n'+json.dumps(entry['research'],ensure_ascii=False,indent=2),encoding='utf-8')
        part='<header><p><a href="../../开始阅读.html">返回赛事总览</a>　<a href="#registration">报名入口</a>　<a href="#learning">学习资料</a></p><h1>'+html.escape(code+' '+entry['name'])+'</h1><p>目录2026 · '+html.escape(entry['grade'])+' · '+html.escape('、'.join(entry['departments']))+'</p><p class="badge">待审核；采用资料：'+html.escape(adopted['label'])+'</p><p>'+html.escape(adopted['summary'])+'</p></header>'
        part+=registration_section(route,route_sources,adopted['label'],route_local_source)
        retained=[a for a in data['attachments'] if a.get('status')=='archived' and code in a['catalog_codes']]
        if retained:
            part+='<section><h2>本项目录留存附件</h2><p>各文件按标题和原文届次使用。提取文本未经全文复核，关键条款以赛事正文及原件为准。</p>'+attachment_links(retained,'../../')+'</section>'
            attachment_sources=[]
            for a in retained:
                if a['url'] not in {s['url'] for s in attachment_sources}:
                    attachment_sources.append(dict(url=a['url'],title=a['original_filename'],publisher=None,published_on=None,checked_on=a.get('verified_on',data['checked_on']),locator='留存附件；具体关键事实见对应赛事正文'))
            manifest['documents'].append(dict(code='attachments-'+code,title=entry['name']+'｜附件目录',
                body='附件按原件实际届次使用，未逐页审核的提取文本不作为已核规则。\n'+'\n'.join(a['original_filename']+'\n原件：'+a['path']+'\n来源：'+a['url']+'\n文本状态：'+a.get('text_status','not_extracted') for a in retained),
                catalog_codes=[code],competition_codes=[],resource_codes=[],sources=attachment_sources,attachments=retained,
                metadata={'scope':'目录关联附件，实际届次以原文件为准','review_status':'pending'}))
        part+='<section><h2>届次档案</h2>'+''.join('<p><a href="'+e['id']+'/赛事说明.html">'+html.escape(e['label'])+'</a> — '+STATUS[e['evidence_status']]+'</p>' for e in entry['editions'])+'</section>'
        part+='<section id="learning"><h2>学习资料导读</h2><p>以下资源与上方报名信息共同对应本项目录。各份资料的适用范围和访问条件分别列明。</p></section>'+''.join(reading_html)+section('缺口', '\n'.join(entry['gaps']))
        (p/'index.html').write_text(page(entry['name'],part),encoding='utf-8')
        manifest['documents'].append(dict(code='guide-'+code,title=entry['name']+'｜学习资料导读',body=learning,
            catalog_codes=[code],competition_codes=[],resource_codes=['learn-'+i['resource_id'] for i in entry['learning']],
            sources=[{'url':resources[i['resource_id']]['url'],'title':resources[i['resource_id']]['title'],
                'publisher':resources[i['resource_id']]['provider'],'checked_on':data['checked_on'],
                'published_on':resources[i['resource_id']].get('published_on'),'locator':resources[i['resource_id']]['locator']} for i in entry['learning']],
            attachments=[a for a in data['attachments'] if a.get('status')=='archived' and
                attachment_urls(a) & {resources[i['resource_id']]['url'] for i in entry['learning']}],
            metadata={'scope':'通用备赛资料；与赛事届次规则分开','review_status':'pending'}))
        index.append({'code':code,'name':entry['name'],'grade':entry['grade'],'departments':'、'.join(entry['departments']),
            'batch':entry['batch'],'sample':entry['sample'],'edition':adopted['label'],
            'evidence':STATUS[adopted['evidence_status']],'current_status':entry['current_edition_status'],
            'resources':len(entry['learning']),'gaps':'；'.join(entry['gaps']),'review':'用户暂缓' if entry['number'] in deferred else '待审核',
            'work_status':'用户暂缓' if entry['number'] in deferred else '本轮已处理',
            'source':adopted['sources'][0]['url'],'file':f'赛事档案/{code}/index.html',
            'registration':route})
    for rid,use in used.items():
        r=resources[rid]
        manifest['resources'].append(dict(code='learn-'+rid,catalog_codes=sorted(set(use['catalog_codes'])),
            competition_codes=sorted(set(use['competition_codes'])),fields={'title':r['title'],'description':text_resource(r),
                'provider':r['provider'],'access_url':r['url'],'source_note':r['scope']+'；核验 '+r['checked_on'],'availability':'available'}))
    # This delivery imports only the 116 active records. Deferred data remains in the canonical source and reading views.
    manifest['work_scope']=scope
    for kind in ['catalog','competitions','resources','documents']:
        manifest[kind]=[row for row in manifest[kind] if (row['code'] in active_codes if kind=='catalog' else bool(set(row['catalog_codes']) & active_codes))]
        if kind!='catalog':
            for row in manifest[kind]:row['catalog_codes']=[c for c in row['catalog_codes'] if c in active_codes]
    write_json(root/'导入清单.json',manifest)
    write_json(root/'附件清单.json',data['attachments'])
    (root/'导入底稿.jsonl').write_text('\n'.join(json.dumps({'type':kind,**row},ensure_ascii=False) for kind in ['catalog','competitions','resources','documents'] for row in manifest[kind])+'\n',encoding='utf-8')
    write_json(root/'索引数据.json',index)
    totals={'catalog_count':len(entries),'active_catalog_count':len(active_codes),'deferred_numbers':sorted(deferred),'processed_active_count':len(scope.get('reviewed_active_numbers',[])),'edition_records':len(manifest['competitions']),'documents':len(manifest['documents']),
        'unique_resources':len(manifest['resources']),'learning_links':sum(r['resources'] for r in index),
        'under_three_resources':[r['code'] for r in index if r['resources']<3],
        'identity_unconfirmed':[e['code'] for e in entries if e['identity_status']=='unconfirmed'],
        'evidence_counts':dict(Counter(r['evidence'] for r in index)),'review_status':'pending','full_research_acceptance':False}
    totals['active_evidence_counts']=dict(Counter(r['evidence'] for r in index if r['code'] in active_codes))
    totals['active_learning_links']=sum(r['resources'] for r in index if r['code'] in active_codes)
    totals['attachments']=dict(Counter(a['status'] for a in data['attachments']))
    totals['local_acceptance']=scope.get('local_acceptance')
    route_counts=Counter(r['registration']['status'] for r in index)
    totals['registration_review']={'checked_on':registration_review.get('checked_on'),
        'explicit_routes':sum(route_counts[s] for s in KNOWN_ROUTE_STATUSES),
        'open_by_notice':route_counts['公告显示开放'],
        'unconfirmed':len(active_codes)-sum(route_counts[s] for s in KNOWN_ROUTE_STATUSES),
        'status_counts':dict(route_counts),'active_review_complete':len(scope.get('reviewed_active_numbers',[]))==len(active_codes),'complete':False}
    write_json(root/'交付统计.json',totals)
    for batch in range(1,6):
        rows=[r for r in index if r['batch']==batch]
        write_json(root/'批次报告'/f'第{batch}批-缺口.json',rows)
        report=f"第{batch}批：{rows[0]['code']}—{rows[-1]['code']}，目录25项，本轮处理{sum(r['code'] in active_codes for r in rows)}项。\n状态：待审核；用户暂缓项不在导入底稿内，完成检索不代表完整规则验收。\n"+'\n'.join(r['code']+' '+r['name']+' ['+r['work_status']+']\n采用：'+r['edition']+'；'+r['evidence']+'；学习资源'+str(r['resources'])+'份\n缺口：'+r['gaps']+'\n' for r in rows)
        (root/'批次报告'/f'第{batch}批-阅读报告.txt').write_text(report,encoding='utf-8')
    rows=''
    for r in index:
        route=r['registration']
        rows+='<tr data-search="'+html.escape(r['code']+' '+r['name']+' '+r['edition']+' '+route['edition'],quote=True)+'" data-status="'+html.escape(route['status'],quote=True)+'"><td>'+r['code']+'</td><td><a href="'+r['file']+'">'+html.escape(r['name'])+'</a></td><td>'+html.escape(r['edition'])+'</td><td>'+r['evidence']+'</td><td>'+str(r['resources'])+'</td><td>'+html.escape(route['edition'])+'</td><td>'+html.escape(route['status'])+'</td><td><a href="'+r['file']+'#registration">查看报名说明</a></td></tr>'
    body='<header><h1>同济2026 · 131—255赛事资料库</h1><p>125项目录记录；本轮已处理116项，9项用户暂缓。导入底稿只包含这116项。</p><p>'+str(totals['edition_records'])+'个具体届次候选 / '+str(totals['unique_resources'])+'份复用学习资源</p><p class="badge">审核草稿 · 尚有公开资料缺口 · 未写入目标数据库</p><p>先看五项样例：'+ ' · '.join('<a href="赛事档案/2026'+str(n)+'/index.html">'+str(n)+'</a>' for n in [131,141,173,179,244])+'</p></header>'
    body+='<section><h2>报名信息已合并到赛事档案</h2><p>每项赛事主页同时展示赛事概览、报名入口与方式、各届详细规则、学习资料及来源附件。</p><p>已明确报名路径 '+str(totals['registration_review']['explicit_routes'])+' 项，其中官方公告显示开放 '+str(totals['registration_review']['open_by_notice'])+' 项；仍待核定 '+str(totals['registration_review']['unconfirmed'])+' 项。核验日期：'+html.escape(registration_review.get('checked_on') or '未核验')+'。</p><p>报名状态按所标届次与核验日理解。2027届入口、往届截止时间和夏令营申请分别标记；未核定不等于没有报名渠道。</p><p><a class="entry-link" href="总索引.xlsx">打开整合后的Excel总索引</a></p></section>'
    body+=section('阅读与维护说明','本包按实际资料届次归档。历史日期不用于当前报名。身份未确认项仅生成目录知识记录。\n整理底稿.json为唯一维护源；报名信息维护在registration_review中；导入清单、阅读版和Excel均从底稿生成。\n原始附件集中按SHA-256留存；课程和视频只提供链接。未审核文档不会进入学生AI检索。\n全文缺失、只找到报道和访问限制都在各档案缺口中列出；尚未达到125项完整规则验收。')
    body+='<section><div class="controls"><input id="catalog-search" type="search" aria-label="搜索赛事" placeholder="搜索赛事名称、编号或届次"><select id="registration-filter" aria-label="筛选报名情况"><option value="all">全部125项</option><option value="known">已明确报名路径</option><option value="open">公告显示开放</option><option value="pending">报名路径待核定</option></select></div><p id="visible-count" class="small"></p><div class="table-scroll"><table class="catalog-table"><thead><tr><th>编号</th><th>赛事详情</th><th>采用资料届次</th><th>资料状态</th><th>学习份数</th><th>报名适用届次</th><th>报名核对结果</th><th>报名说明</th></tr></thead><tbody>'+rows+'</tbody></table></div></section>'
    body=body.replace('<option value="all">全部125项</option>','<option value="active">本轮116项</option><option value="all">全部125项</option><option value="deferred">暂缓9项</option>')
    body=body.replace('已明确报名路径 ','已确认报名方式（含学校推荐和期限待核） ')
    body+='''<script>const search=document.getElementById('catalog-search'),filter=document.getElementById('registration-filter'),rows=[...document.querySelectorAll('tbody tr')];function update(){const q=search.value.trim().toLowerCase();let count=0;for(const row of rows){const s=row.dataset.status,known=['公告显示开放','对应届次已截止','已确认渠道，期限待核','校内推荐安排待核'].includes(s);const visible=(filter.value==='all'||(filter.value==='active'&&s!=='用户暂缓')||(filter.value==='deferred'&&s==='用户暂缓')||(filter.value==='known'&&known)||(filter.value==='open'&&s==='公告显示开放')||(filter.value==='pending'&&!known&&s!=='用户暂缓'))&&row.dataset.search.toLowerCase().includes(q);row.hidden=!visible;if(visible)count++;}document.getElementById('visible-count').textContent='显示 '+count+' 项';}search.addEventListener('input',update);filter.addEventListener('change',update);update();</script>'''
    if scope.get('local_acceptance',{}).get('status')=='passed':
        body=body.replace('审核草稿 · 尚有公开资料缺口 · 未写入目标数据库','已导入本地开发库草稿 · 尚有公开资料缺口 · 未发布')
        body=body.replace('<h2>报名信息已合并到赛事档案</h2>','<h2>报名信息已合并到赛事档案</h2><p><a class="entry-link" href="入库与维护说明.txt">查看资料交付与入库说明</a></p>')
    (root/'开始阅读.html').write_text(page('同济2026赛事资料库',body),encoding='utf-8')
    (root/'赛事报名入口清单（核对中）.html').write_text(page('报名信息已整合','<header><h1>报名信息已整合到赛事档案</h1><p>请从总览筛选报名状态，并同时查看对应届次、完整说明、学习资源及附件。</p><p><a class="entry-link" href="开始阅读.html">打开最新赛事资料总览</a></p><p><a href="总索引.xlsx">打开最新总索引</a></p></header>'),encoding='utf-8')
    (root/'使用说明.txt').write_text('阅读入口：开始阅读.html；汇总：总索引.xlsx。\n唯一事实维护源：整理底稿.json。\n入库输入：导入清单.json；先校验、预演，再由接收方确认目标库后导入草稿。\n命令、权限、目录关联和版本说明见本包《入库与维护说明.txt》。\n首次入库不需要重新生成Excel或阅读版，也不依赖Codex工具。\n交付文件以工程docs/curated-delivery-files.json为准，保留相对目录及附件。\n本机验收记录仅用于本机追溯，不使用其中的账号ID或执行清单在其他库导入。\n赛事日期以所标实际届次为准；已知缺口保留，草稿入库不表示公开发布。\n资料包根目录需要持久保存，数据库记录其根路径及附件相对路径。\n',encoding='utf-8')
    print(json.dumps(totals,ensure_ascii=False))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('source',type=Path);args=parser.parse_args();build(args.source)
