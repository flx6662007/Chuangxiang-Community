"""NCDA 官方专项赛表格适配器；作品投稿与队伍报名分别处理。"""
from dataclasses import dataclass
from datetime import date
import re
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup, Comment

from .http import FetchError, checked_url


def text_of(node):
    return '\n'.join(re.sub(r'[\t \xa0\u3000]+', ' ', line).strip()
                     for line in node.get_text('').splitlines() if line.strip())


@dataclass
class NcdaExtracted:
    title: str
    body: str
    published_on: date | None
    candidate: dict
    evidence: dict
    missing: list
    errors: list


class NcdaAdapter:
    key = 'ncda'
    hosts = ('www.ncda.org.cn', 'ncda.org.cn')
    base_url = 'https://www.ncda.org.cn/'
    name = '未来设计师 NCDA 官方专项赛'
    category_code, category_name = 'art-and-design', '艺术与设计'
    path_pattern = r'^/dsjs/dsnr/(?:mtsd|gysd|sjtzs)/(9[A-Z]\d)/?$'

    def __init__(self, rule_version):
        self.rule_version = rule_version

    def accept_link(self, title, url):
        return bool(re.fullmatch(self.path_pattern, urlsplit(url).path))

    def discover(self, page):
        soup = BeautifulSoup(page.text, 'html.parser')
        for node in soup.find_all(string=lambda value: isinstance(value, Comment)):
            node.extract()
        urls = []
        # 只发现官网专项赛征稿入口；往届奖项/展览/教师赛等不作为新招募赛事。
        # 此标签只控制发现范围，是否已经截止仍以详情中的投稿日期为准。
        for anchor in soup.select('.zbdw a[href]'):
            card = anchor.parent.get_text(' ', strip=True)
            url = urljoin(page.url, anchor['href'])
            if not re.search(r'征稿|投稿|截稿', card) or not self.accept_link('', url):
                continue
            try:
                url = checked_url(url, self.hosts, resolve=False)
            except FetchError:
                continue
            # 同一来源统一域名、路径尾斜线，避免相对链接/别名重复建档。
            url = self.base_url.rstrip('/') + urlsplit(url).path.rstrip('/') + '/'
            if url not in urls:
                urls.append(url)
        return urls

    def parse(self, page):
        match = re.fullmatch(self.path_pattern, urlsplit(page.url).path)
        if not match:
            raise FetchError('not_competition_notice', '不是受支持的 NCDA 专项赛事页。')
        track_code = match.group(1)
        soup = BeautifulSoup(page.text, 'html.parser')
        for node in soup.find_all(string=lambda value: isinstance(value, Comment)):
            node.extract()
        root = soup.select_one('#main .dsjs')
        table = root.select_one('table.peixun_table') if root else None
        if table is None:
            raise FetchError('layout_changed', 'NCDA 专项赛正文表格结构改变，等待维护。')
        for node in root.select('script,style,iframe,form'):
            node.decompose()
        for node in root.select('br'):
            node.replace_with('\n')
        for node in root.select('p,li'):
            node.append('\n')

        # 官网使用两列表格及左侧合并行，只有一格的后续行须归入原标签。
        groups, active, remaining = [], None, 0
        for row in table.find_all('tr'):
            if row.find_parent('table') is not table:
                continue
            cells = row.find_all(['td', 'th'], recursive=False)
            if len(cells) == 2:
                if remaining:
                    raise FetchError('layout_changed', 'NCDA 表格上一字段合并行尚未结束。')
                label = re.sub(r'\s+', '', text_of(cells[0]))
                active = [label, text_of(cells[1])]
                groups.append(active)
                try:
                    remaining = int(cells[0].get('rowspan', 1)) - 1
                except ValueError as exc:
                    raise FetchError('layout_changed', 'NCDA 表格合并行无效。') from exc
                if not 0 <= remaining <= 50:
                    raise FetchError('layout_changed', 'NCDA 表格合并行超出限制。')
            elif len(cells) == 1 and remaining and active:
                active[1] += '\n' + text_of(cells[0])
                remaining -= 1
            elif cells:
                raise FetchError('layout_changed', 'NCDA 表格列数或合并行不符合规则。')
        if remaining:
            raise FetchError('layout_changed', 'NCDA 表格合并行不完整。')
        fields = {}
        for label, value in groups:
            if label in fields:
                raise FetchError('layout_changed', 'NCDA 表格出现重复字段标签。')
            fields[label] = value
        name_block = fields.get('赛项名称', '')
        title_quote = re.split(r'\n?【(?:归类|赛项)代码】', name_block, maxsplit=1)[0].strip()
        title_quote = re.sub(r'^【赛项名称】\s*', '', title_quote)
        title = re.sub(r'\s+', ' ', title_quote).strip()
        header = next((text_of(p) for p in root.find_all('p', recursive=False)
                       if re.match(r'^20\d{2}.*(?:未来设计师|NCDA)', text_of(p))), '')
        identity = '\n'.join(filter(None, [header, name_block]))
        years = set(re.findall(r'(?<!\d)20\d{2}(?!\d)', identity))
        if not title or len(title) > 200 or len(years) != 1:
            raise FetchError('missing_edition_evidence', 'NCDA 赛项名称或正文年度不明确，不能从页脚/投稿日期猜届次。')
        year = years.pop()
        # 赛项代码若出现，必须与当前页面匹配；不能把其他赛项表格误映射过来。
        named_codes = set(re.findall(r'(?<![A-Z0-9])9[A-Z]\d(?![A-Z0-9])', name_block + fields.get('赛项代码', '')))
        if named_codes and named_codes != {track_code}:
            raise FetchError('conflicting_competition_identity', '正文赛项代码与网址不一致。')
        body = '\n'.join(filter(None, [header, *[label + '\n' + value for label, value in groups]]))
        if not 100 <= len(body) <= 150000:
            raise FetchError('invalid_body', 'NCDA 正文为空、过短或超过上限。')
        candidate = dict(code=f'ncda-{year}-{track_code.lower()}', title=title, edition=year,
                         category_code=self.category_code, category_name=self.category_name,
                         level='unknown', organizer='', summary='', description='', tracks='', eligibility='',
                         participation_type='unknown', team_size_min=None, team_size_max=None,
                         registration_method='', registration_url='', registration_deadline=None,
                         submission_deadline=None, deadline_notes='', rule_version=self.rule_version)
        evidence = {'title': title_quote, 'edition': header or name_block,
                    'category_code': '适配器分类：NCDA 艺术与设计专项赛事'}
        errors = []

        def put(field, value, quote):
            if value not in ('', None) and quote:
                if quote not in body:
                    raise FetchError('evidence_outside_body', 'NCDA 字段依据不在当前赛项正文。')
                candidate[field], evidence[field] = value, quote

        organizer_block = fields.get('主办单位', '')
        if not organizer_block:
            organization = fields.get('命题单位', '') or fields.get('组织构架', '')
            organizer_match = re.search(r'【主办单位】[：:]?\s*([^\n]+)', organization)
            organizer_block = organizer_match.group(1).strip() if organizer_match else ''
        put('organizer', organizer_block[:500], organizer_block)
        eligibility_block = fields.get('参赛对象', '') or fields.get('参赛对象及赛程', '')
        eligibility = eligibility_block.split('【时间节点】', 1)[0].strip()
        eligibility = re.sub(r'^【参赛对象】\s*', '', eligibility)
        put('eligibility', eligibility[:5000], eligibility)
        if re.search(r'个人\s*[/／]\s*团队.*?均可参赛', eligibility, re.S):
            put('participation_type', 'both', eligibility)
        # “每件作品作者数”与报名团队成员数不是同一字段。保留原文，不自动换算。
        author_lines = [line for block in (eligibility, fields.get('作品要求', ''))
                        for line in block.splitlines() if re.search(r'(?:作者|创作人员)', line) and '最多' in line]
        if author_lines:
            candidate['author_limit_note'] = '\n'.join(author_lines)
            evidence['author_limit_note'] = author_lines
        schedule = fields.get('赛程安排', '')
        if '【时间节点】' in eligibility_block:
            schedule = eligibility_block.split('【时间节点】', 1)[1].strip()
        if schedule:
            put('deadline_notes', schedule[:5000], schedule)
        deadline_values, deadline_quotes = [], []
        for line in schedule.splitlines():
            if not re.search(r'投稿时间|省赛征稿|截稿(?:日期|时间)', line):
                continue
            dates = list(re.finditer(r'(20\d{2})年(\d{1,2})月(\d{1,2})日', line))
            if not dates:
                continue
            if re.search(r'延期|延长|调整为|原定|更改为|变更为|推迟|提前', line):
                errors.append('ambiguous_deadline:submission_deadline')
                continue
            if len(dates) == 2:
                separator = line[dates[0].end():dates[1].start()]
                if not re.fullmatch(r'\s*[—–－~～至到\-]\s*', separator):
                    errors.append('ambiguous_deadline:submission_deadline')
                    continue
            elif len(dates) != 1:
                errors.append('ambiguous_deadline:submission_deadline')
                continue
            try:
                start = date(*map(int, dates[0].groups()))
                deadline = date(*map(int, dates[-1].groups()))
            except ValueError:
                errors.append('invalid_deadline:submission_deadline')
                continue
            if start > deadline or deadline.year not in (int(year), int(year) + 1):
                errors.append('date_outside_edition:submission_deadline')
                continue
            deadline_values.append(deadline.isoformat())
            deadline_quotes.append(line)
        if len(set(deadline_values)) > 1:
            errors.append('ambiguous_deadline:submission_deadline')
        if deadline_values and not errors:
            put('submission_deadline', deadline_values[0], deadline_quotes[0])
        content = fields.get('竞赛内容', '')
        put('tracks', content[:2000], content)
        method = fields.get('投稿要求', '') or fields.get('投稿方式及要求', '')
        put('registration_method', method[:1500], method)
        # 入口必须确实存在于当前官方正文表格，禁止从无关页脚拿链接。
        for anchor in table.select('a[href]'):
            url = urljoin(page.url, anchor['href'])
            parts = urlsplit(url)
            if (parts.scheme == 'https' and parts.hostname == 'www.fd.show'
                    and not parts.username and not parts.password and parts.port in (None, 443)):
                candidate['registration_url'] = url
                quote = '【官方赛项正文入口】' + url
                body += '\n' + quote
                evidence['registration_url'] = quote
                break
        if not candidate['organizer'] or not candidate['eligibility']:
            errors.append('missing_required_evidence')
        summary = [title]
        if candidate['organizer']:
            summary.append('主办：' + candidate['organizer'])
        if candidate['submission_deadline']:
            summary.append('作品投稿截止：' + candidate['submission_deadline'])
        candidate['summary'] = '；'.join(summary)[:500]
        descriptions = ['参赛对象：' + eligibility] if eligibility else []
        if author_lines:
            descriptions.append('作品作者限制：' + '\n'.join(author_lines)
                                + '\n此处为作品作者/创作人员限制，不直接作为平台招募队伍人数上限。')
        for label, value in [('竞赛内容', candidate['tracks']), ('官方投稿方式', candidate['registration_method']), ('赛程安排', schedule)]:
            if value:
                descriptions.append(label + '：' + value)
        descriptions.append('本页提供作品投稿时间，未注明独立报名截止；平台暂不自动开启组队招募。')
        candidate['description'] = '\n\n'.join(descriptions)[:20000]
        missing = [field for field in ('organizer', 'eligibility', 'registration_deadline', 'submission_deadline',
                                      'registration_url', 'team_size_max') if not candidate.get(field)]
        return NcdaExtracted(title, body, None, candidate, evidence, missing, sorted(set(errors)))
