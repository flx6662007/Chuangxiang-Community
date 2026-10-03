"""将人工整理的 89 项资料输出为离线可检索 HTML 和结构化 JSON。"""
import collections
import html
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
payload = json.loads((OUT / '整理底稿.json').read_text(encoding='utf-8'))
rows = sorted(payload['entries'], key=lambda r: r['code'])
assert [r['code'] for r in rows] == [str(2026000 + i) for i in range(1, 90)]
DATA = ROOT / 'backend/competition_catalog/data'
catalog = {r['code']: r['name'] for r in json.loads((DATA / 'tongji-2026.json').read_text(encoding='utf-8'))['entries']}
assert all(r['name'] == catalog[r['code']] for r in rows)
sources = [s for r in rows for s in r['competition_sources']]
resources = [s for r in rows for s in r['learning_resources']]
counts = {'competitions': len(rows), 'competition_sources': len(sources), 'learning_resources': len(resources),
          'unique_urls': len({s['url'] for s in sources + resources}),
          'evidence': dict(collections.Counter(s['verified_by'] for s in sources + resources))}
e = lambda value: html.escape(str(value), quote=True)
evidence = {'page_read': '已读来源页面', 'official_index': '已确认索引 / 入口', 'search_result': '仅搜索结果 · 待核对'}
types = {'rules': '规则与模板', 'problems': '赛题与样题', 'course': '课程与教程', 'examples': '作品与案例',
         'tools': '技术工具', 'dataset': '数据集', 'code': '示例代码'}
uncertain = {'2026052', '2026057', '2026063', '2026064', '2026067'}

def link(s):
    return f'<a href="{e(s["url"])}" target="_blank" rel="noopener noreferrer">{e(s["title"])} ↗</a>'

def badge(s):
    v = s['verified_by']
    return f'<span class="tag {e(v)}">{e(evidence[v])}</span>'

cards = []
for r in rows:
    n = int(r['code']) - 2026000
    source_html = ''.join(f'<li>{link(s)}<p class="meta">{e(s["provider"])} · '
                         f'{e({"official":"官方来源", "university":"高校发布"}.get(s["source_type"],s["source_type"]))}'
                         f' · {e(s.get("published_on") or "未注明发布日期")} {badge(s)}</p>'
                         f'<p>{e(s["summary"])}</p></li>' for s in r['competition_sources'])
    resource_html = ''.join(f'<li>{link(s)}<p class="meta">{e(types[s["type"]])} · {e(s["level"])} · '
                           f'{e(s["access"])} {badge(s)}</p><p><b>适用：</b>{e(s["applies_to"])}</p>'
                           f'<p><b>用途：</b>{e(s["why_useful"])}</p><p>{e(s["summary"])}</p>'
                           f'<p class="meta">提供方：{e(s["provider"])}</p></li>' for s in r['learning_resources'])
    gaps = ''.join(f'<li>{e(g)}</li>' for g in r['gaps'])
    search = e(str(n) + ' ' + json.dumps(r, ensure_ascii=False))
    read = any(s['verified_by'] == 'page_read' for s in r['competition_sources'])
    flags = ('待确认对应关系' if r['code'] in uncertain else '已读赛事来源' if read else '赛事来源正文待补')
    cards.append(f'''<details class="entry" data-search="{search}" data-uncertain="{str(r['code'] in uncertain).lower()}" data-read="{str(read).lower()}" id="c{n}">
<summary><span class="num">{n:02}</span><span><strong>{e(r['name'])}</strong><small>{e(r['code'])} · {len(r['learning_resources'])} 条学习资料 · {flags}</small></span><span class="plus">＋</span></summary>
<div class="content"><p class="edition"><b>届次与适用范围：</b>{e(r['edition_note'])}</p><p>{e(r['overview'])}</p>
<h3>赛事信息与来源</h3><ul class="sources">{source_html}</ul><h3>学习资料</h3><ol class="resources">{resource_html}</ol>
<aside><h3>待补内容</h3><ul>{gaps}</ul></aside></div></details>''')

page = '''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>赛事与学习资料｜目录 1–89</title>
<style>
:root{color-scheme:light;--ink:#172945;--blue:#235ccb;--line:#dce4ef;--muted:#5c6f85}*{box-sizing:border-box}body{margin:0;background:#f3f6fa;color:var(--ink);font-family:system-ui,"Microsoft YaHei",sans-serif;line-height:1.75}main{max-width:1080px;margin:auto;padding:48px 24px 80px}header{margin-bottom:28px}.eyebrow{color:var(--blue);font-weight:700;letter-spacing:2px;font-size:13px}h1{font-size:34px;letter-spacing:-1px;margin:7px 0 10px}h2{font-size:21px}h3{font-size:17px;margin:24px 0 10px}p{margin:8px 0}a{color:var(--blue);text-decoration:none}a:hover{text-decoration:underline}.lead{color:var(--muted);max-width:870px}.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:24px 0}.stat{border:1px solid var(--line);border-radius:12px;padding:16px 20px;background:#fff}.stat b{font-size:29px;display:block;line-height:1.25}.stat span{font-size:13px;color:var(--muted)}.note{background:#eaf1ff;border-left:4px solid var(--blue);padding:14px 20px;border-radius:4px 10px 10px 4px;font-size:14px}.toolbar{position:sticky;top:0;background:#f3f6faf5;backdrop-filter:blur(8px);padding:16px 0;z-index:2;display:flex;gap:10px;flex-wrap:wrap}input,select,button{font:inherit;border:1px solid var(--line);border-radius:8px;padding:9px 12px;background:#fff;color:var(--ink)}input{flex:1;min-width:230px}button{cursor:pointer}button:hover{background:#eaf1ff}.result{color:var(--muted);font-size:13px;margin:0 0 12px}.entry{background:white;border:1px solid var(--line);border-radius:12px;margin:10px 0;overflow:hidden}.entry[hidden]{display:none}summary{display:flex;align-items:center;gap:16px;padding:19px 22px;cursor:pointer;list-style:none}summary::-webkit-details-marker{display:none}summary strong{font-size:17px}summary small{display:block;color:var(--muted);font-size:12px;margin-top:4px}.num{font-size:22px;font-weight:700;color:var(--blue);min-width:34px}.plus{margin-left:auto;color:var(--muted)}details[open] .plus{transform:rotate(45deg)}.content{border-top:1px solid var(--line);padding:20px 28px 25px}.edition{background:#f3f6fa;padding:12px 16px;border-radius:7px}.sources,.resources{padding-left:25px}.sources>li,.resources>li{padding:10px 0 17px;border-bottom:1px solid #edf0f5}.sources>li>a,.resources>li>a{font-weight:650;overflow-wrap:anywhere}.meta{color:var(--muted);font-size:12px}.tag{display:inline-block;padding:1px 7px;border-radius:4px;background:#eef2f7;margin:3px 0 3px 4px;font-size:11px}.page_read{background:#e5f4ed;color:#216849}.official_index{background:#edf0fa;color:#525e91}.search_result{background:#fff0df;color:#8b5717}aside{background:#fff8ed;padding:1px 16px 12px;border-radius:8px;margin-top:24px;font-size:14px}aside h3{margin-top:13px}aside ul{padding-left:22px}footer{border-top:1px solid var(--line);padding-top:20px;margin-top:32px;font-size:13px;color:var(--muted)}.download{display:inline-block;border:1px solid var(--line);background:white;border-radius:8px;padding:8px 12px;margin-top:15px}.empty{padding:25px;background:white;border-radius:10px}.legend{font-size:13px;color:var(--muted);margin-top:12px}@media(max-width:650px){main{padding:28px 14px}h1{font-size:27px}.stats{grid-template-columns:repeat(2,1fr)}summary{padding:16px 13px;gap:10px}.content{padding:14px}.toolbar{position:static}.tag{margin-left:0}}@media print{.toolbar,.download{display:none}body{background:#fff}main{max-width:none;padding:0}.entry{break-inside:avoid}.content{display:block}a{color:#222}.stats{grid-template-columns:repeat(4,1fr)}}
</style></head><body><main><header><div class="eyebrow">创享 · 人工整理资料</div><h1>赛事信息与学习资料</h1><p class="lead">依据《同济大学本科生学科竞赛目录（2026版）》第 1–89 项整理，保留原目录名称和编号。查找日期：2026 年 10 月 3 日。</p>
<div class="stats"><div class="stat"><b>89</b><span>目录赛事</span></div><div class="stat"><b>121</b><span>赛事来源条目</span></div><div class="stat"><b>212</b><span>学习资料条目</span></div><div class="stat"><b>267</b><span>不同来源链接</span></div></div>
<div class="note"><b>本版保存的是来源链接、人工摘要与缺项记录。</b>学习资料包括规则、模板、赛题、课程及案例，条目数量不等于已下载文件数量。往届资料可用于学习，不代表本届仍可报名；学校校赛期限与全国赛期限不能混用。后台存档不等于已接通 AI 问答。</div>
<p class="legend"><span class="tag page_read">已读来源页面</span> 已阅读链接页面，但不代表页面内所有附件、视频均已读取。<br><span class="tag official_index">已确认索引 / 入口</span> 已找到附件或资料入口，内容待进一步核对。<br><span class="tag search_result">仅搜索结果 · 待核对</span> 直接访问受限或正文未读，不作为已完成核验。</p>
<a class="download" href="整理底稿.json" download>下载结构化 JSON</a></header>
<div class="toolbar"><input id="search" type="search" placeholder="搜索编号、赛事、方向、课程或工具" aria-label="搜索赛事与资料"><select id="filter" aria-label="筛选"><option value="all">全部赛事</option><option value="uncertain">对应范围重点待确认（5项）</option><option value="unread">赛事来源正文待补</option></select><button id="expand">展开当前结果</button><button id="collapse">收起</button></div><p id="result" class="result" aria-live="polite"></p>
<section id="entries">__CARDS__</section><p class="empty" id="empty" hidden>没有匹配结果，请更换关键词。</p>
<footer><p><b>后续知识库使用：</b>每项资料已保留目录编号、来源、届次、适用方向、核验程度及缺项。后续补充获得授权的正文或笔记，再按赛事与届次分段并建立检索；搜索线索和未确认对应关系应先核对。</p><p>第 52、57、63、64、67 项的限定主题、届次或赛事对应关系尚需明确，已在各项中列出。第 68 项在原表涉及两个负责部门，此处合并为同一赛事。报告不包含目录中的教师联系方式。</p></footer></main>
<script>const entries=[...document.querySelectorAll('.entry')],q=document.querySelector('#search'),filter=document.querySelector('#filter');function update(){const value=q.value.trim().toLocaleLowerCase();let count=0;entries.forEach(el=>{const ok=el.dataset.search.toLocaleLowerCase().includes(value)&&(filter.value==='all'||filter.value==='uncertain'&&el.dataset.uncertain==='true'||filter.value==='unread'&&el.dataset.read==='false');el.hidden=!ok;if(ok)count++});document.querySelector('#result').textContent=`显示 ${count} / ${entries.length} 项 · 点击赛事名称查看来源与学习资料`;document.querySelector('#empty').hidden=count>0}q.addEventListener('input',update);filter.addEventListener('change',update);document.querySelector('#expand').addEventListener('click',()=>entries.filter(el=>!el.hidden).forEach(el=>el.open=true));document.querySelector('#collapse').addEventListener('click',()=>entries.forEach(el=>el.open=false));update();if(location.hash){const el=document.querySelector(location.hash);if(el&&el.classList.contains('entry'))el.open=true}</script></body></html>'''
page = page.replace('__CARDS__', '\n'.join(cards))
report = OUT / '开始阅读.html'
report.write_text(page, encoding='utf-8')
print(json.dumps({'report': str(report), **counts}, ensure_ascii=False))


# Markdown 阅读版供 GitHub 直接浏览；来源事实只维护 整理底稿.json。
def md(value):
    return str(value).replace('\\', '\\\\').replace('[', '\\[').replace(']', '\\]').replace('<', '&lt;').replace('>', '&gt;')

for first, last in ((1, 22), (23, 44), (45, 66), (67, 89)):
    lines = [f'# 赛事资料 {first:03}—{last:03}', '', '[返回资料说明](README.md)', '',
             '来源查找日期：2026-10-03。已读页面不代表其附件全文已读；索引及搜索线索另行标注。', '']
    for r in rows[first - 1:last]:
        lines += [f"## {int(r['code']) - 2026000:03} · {md(r['name'])}", '',
                  f"目录编号：`{r['code']}`", '', f"**届次与范围：** {md(r['edition_note'])}", '', md(r['overview']), '',
                  '### 赛事来源', '']
        for s in r['competition_sources']:
            lines += [f"- [{md(s['title'])}](<{s['url']}>) · {md(s['provider'])}",
                      f"  - 核验程度：{evidence[s['verified_by']]}；发布日期：{s.get('published_on') or '未注明'}。",
                      f"  - {md(s['summary'])}", '']
        lines += ['### 学习资料', '']
        for s in r['learning_resources']:
            lines += [f"- [{md(s['title'])}](<{s['url']}>)", f"  - {types[s['type']]} · {md(s['level'])} · {md(s['access'])} · {evidence[s['verified_by']]}",
                      f"  - 适用：{md(s['applies_to'])}。用途：{md(s['why_useful'])}",
                      f"  - {md(s['summary'])}", f"  - 提供方：{md(s['provider'])}", '']
        lines += ['### 待补内容', ''] + ['- ' + md(g) for g in r['gaps']] + ['']
    (OUT / f'{first:03}-{last:03}.md').write_text('\n'.join(lines), encoding='utf-8')
