"""两个官方站点的受限规则解析；提取范围只取文章正文，不取导航、页脚或相关文章。"""
from dataclasses import dataclass
from datetime import date
import hashlib
import re
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup

from .http import FetchError, checked_url

RULE_VERSION = 'official-html-2026-09-v1'


def normalized(text):
    return '\n'.join(re.sub(r'[\t \xa0\u3000]+', ' ', line).strip() for line in text.splitlines() if line.strip())


def section(text, heading):
    match = re.search(r'(?:^|\n)[一二三四五六七八九十]+[、．.]\s*' + heading + r'\s*\n(.*?)(?=\n[一二三四五六七八九十]+[、．.]|\Z)', text, re.S)
    return match.group(1).strip() if match else ''


def first_line(text, pattern):
    return next((line for line in text.splitlines() if re.search(pattern, line)), '')


def chinese_date(text):
    match = re.search(r'(20\d{2})[年-](\d{1,2})[月-](\d{1,2})(?:日)?', text)
    if not match:
        return None
    try:
        return date(*map(int, match.groups()))
    except ValueError:
        return None


@dataclass
class Extracted:
    title: str
    body: str
    published_on: date | None
    candidate: dict
    evidence: dict
    missing: list
    errors: list


class Adapter:
    key = ''
    hosts = ()
    category_code = ''
    category_name = ''
    base_url = ''
    name = ''

    def discover(self, page):
        soup = BeautifulSoup(page.text, 'html.parser')
        rows = []
        for anchor in soup.select('a[href]'):
            title = normalized(anchor.get_text(' ', strip=True))
            url = urljoin(page.url, anchor['href'])
            if self.accept_link(title, url):
                try:
                    url = checked_url(url, self.hosts, resolve=False)
                except FetchError:
                    continue
                if url not in rows:
                    rows.append(url)
        return rows

    def parse(self, page):
        soup = BeautifulSoup(page.text, 'html.parser')
        root = soup.select_one('.article-content')
        title_element = soup.select_one(self.title_selector)
        if not root or not title_element:
            raise FetchError('layout_changed', '官方页面正文或标题结构改变，等待适配器维护。')
        title = normalized(title_element.get_text(' ', strip=True))
        if not self.accept_link(title, page.url):
            raise FetchError('not_competition_notice', '文章不是当前适配器支持的具体届次参赛通知。')
        for node in root.select('script,style,iframe,form'):
            node.decompose()
        for node in root.select('br'):
            node.replace_with('\n')
        for node in root.select('p,h1,h2,h3,h4,h5,h6,li,tr'):
            node.append('\n')
        body = normalized(root.get_text(''))
        if not 100 <= len(body) <= 200000:
            raise FetchError('invalid_body', '官方正文为空、过短或超过上限。')
        meta = soup.select_one(self.meta_selector)
        published = chinese_date(meta.get_text(' ', strip=True)) if meta else None
        year = re.search(r'20\d{2}', title).group(0)
        canonical_title = re.sub(r'赛题及竞赛规则$|报名通知$', '', title).strip()
        code = self.key + '-' + year + '-' + hashlib.sha256(canonical_title.encode()).hexdigest()[:12]
        candidate = dict(code=code, title=canonical_title, edition=self.edition(title, year),
                         category_code=self.category_code, category_name=self.category_name,
                         level='unknown', organizer='', summary='', description='', tracks='', eligibility='',
                         participation_type='unknown', team_size_min=None, team_size_max=None,
                         registration_method='', registration_url='', registration_deadline=None,
                         submission_deadline=None, deadline_notes='', rule_version=RULE_VERSION)
        evidence = {'title': title, 'edition': title, 'category_code': self.category_basis}
        def put(field, value, quote):
            if value not in ('', None) and quote:
                if quote not in body and quote != title:
                    raise FetchError('evidence_outside_body', '字段依据不在当前通知正文内。')
                candidate[field], evidence[field] = value, quote
        self.fields(candidate, body, root, soup, put)
        # 导航报名链接也属于此次页面证据。显式标注后纳入哈希，避免链接改变而正文不变时被误判 unchanged。
        for field, link in candidate.get('source_link_evidence', {}).items():
            quote = '【官方页面导航链接】' + link['label'] + '：' + link['url']
            body += '\n' + quote
            evidence[field] = quote
        # 简介和详情是可回查的结构化摘录，完整原文仅留在内部 SourceVersion。
        summary_parts = [candidate['title']]
        if candidate['organizer']:
            summary_parts.append('主办：' + candidate['organizer'])
        if candidate['registration_deadline']:
            summary_parts.append('报名截止日期：' + candidate['registration_deadline'])
        candidate['summary'] = '；'.join(summary_parts)[:500]
        details = []
        for label, field in [('参赛对象', 'eligibility'), ('赛题方向', 'tracks'), ('报名方式', 'registration_method'), ('时间说明', 'deadline_notes')]:
            if candidate[field]:
                details.append(label + '：' + candidate[field])
        candidate['description'] = '\n\n'.join(details) or '已收录官方参赛通知。具体规则与更新以来源原文为准。'
        evidence['summary'] = '\n'.join(evidence.get(f, '') for f in ('title', 'organizer', 'registration_deadline'))
        evidence['description'] = '\n'.join(evidence.get(f, '') for f in ('eligibility', 'tracks', 'registration_method', 'deadline_notes'))
        missing = [f for f in ('organizer', 'eligibility', 'registration_deadline', 'registration_url', 'team_size_max') if not candidate.get(f)]
        errors = candidate.pop('_extraction_errors', [])
        if not candidate['organizer'] or not candidate['eligibility']:
            errors.append('missing_required_evidence')
        if candidate['team_size_max'] and candidate['team_size_min'] and candidate['team_size_min'] > candidate['team_size_max']:
            errors.append('invalid_team_size')
        # 来源日期不同于比赛年度。报名年份必须明确匹配届次，不能从页脚猜年份。
        for field in ('registration_deadline', 'submission_deadline'):
            if candidate[field] and int(candidate[field][:4]) not in (int(year), int(year) + 1):
                errors.append('date_outside_edition:' + field)
        return Extracted(title, body, published, candidate, evidence, missing, errors)

    def edition(self, title, year):
        return year

    def common_fields(self, data, body, put):
        organizer = first_line(body, r'^主办(?:单位)?[：:]')
        if organizer:
            put('organizer', re.split(r'[：:]', organizer, maxsplit=1)[1].strip()[:500], organizer)
        deadline_quotes = []
        for field, pattern in [('registration_deadline', r'报名(?:截止|（截止)'), ('submission_deadline', r'(?:论文|作品)提交截止')]:
            lines = [line for line in body.splitlines() if re.search(pattern, line) and chinese_date(line[re.search(pattern, line).end():])]
            line = lines[0] if lines else ''
            dates = {match.group(0) for item in lines for match in re.finditer(r'20\d{2}[年-]\d{1,2}[月-]\d{1,2}日?', item[re.search(pattern, item).end():])}
            if len(dates) > 1 or any(re.search(r'延期|延长|调整|原定|更改|变更|推迟|提前', item) for item in lines):
                data.setdefault('_extraction_errors', []).append('ambiguous_deadline:' + field)
                deadline_quotes.extend(lines)
                continue
            day = chinese_date(line[re.search(pattern, line).end():]) if line else None
            if day:
                put(field, day.isoformat(), line)
                deadline_quotes.append(line)
        if deadline_quotes:
            notes = '\n'.join(deadline_quotes)
            # 官网未明示时区，不写入精确时刻；原文的小时完整保留。
            put('deadline_notes', notes, notes if notes in body else deadline_quotes[0])


class AicompAdapter(Adapter):
    key = 'aicomp'
    hosts = ('www.aicomp.cn', 'aicomp.cn')
    base_url = 'https://www.aicomp.cn/tracks/tracks-5'
    name = 'AIC 官方算法主题赛'
    title_selector = '.article-title .title'
    meta_selector = '.article-title'
    category_code, category_name = 'artificial-intelligence', '人工智能'
    category_basis = '适配器分类：AIC 官方算法主题赛'

    def accept_link(self, title, url):
        return bool(re.search(r'/tracks/tracks-5/\d+\.html$', urlsplit(url).path)
                    and re.match(r'20\d{2}\s*AIC', title) and '赛题及竞赛规则' in title)

    def fields(self, data, body, root, soup, put):
        self.common_fields(data, body, put)
        eligibility = section(body, '参赛对象')
        put('eligibility', eligibility[:2500], eligibility)
        if '全球' in eligibility:
            put('level', 'international', eligibility)
        elif '全国' in eligibility:
            put('level', 'national', eligibility)
        team_line = first_line(body, r'(?:每支|每个|每队).*?(?:团队|队伍|参赛队).*?(?:不超过|至多|最多)\s*\d+\s*[人名]')
        if team_line:
            maximums = set()
            for pattern in (
                r'(?:每支|每个|每队)(?:参赛)?(?:团队|队伍|参赛队)(?:学生|队员|成员)?(?:人数)?\s*(?:不得超过|不超过|至多|最多)\s*(\d+)\s*人',
                r'(?:学生|参赛选手|队员|参赛成员)(?:人数)?\s*(?:不得超过|不超过|至多|最多)\s*(\d+)\s*[人名]',
                r'(?:不得超过|不超过|至多|最多)\s*(\d+)\s*名学生',
            ):
                maximums.update(int(match.group(1)) for match in re.finditer(pattern, team_line))
            if len(maximums) == 1:
                put('team_size_max', maximums.pop(), team_line)
                put('participation_type', 'team', team_line)
            else:
                data.setdefault('_extraction_errors', []).append('ambiguous_team_size')
            if '单人' in team_line:
                put('team_size_min', 1, team_line)
                put('participation_type', 'both', team_line)
            if eligibility and body.index(team_line) > body.index(eligibility):
                eligibility_with_rules = body[body.index(eligibility):body.index(team_line) + len(team_line)]
                put('eligibility', eligibility_with_rules[:2500], eligibility_with_rules)
        tracks = section(body, '赛题说明') or section(body, '赛题方向')
        if tracks:
            headings = re.findall(r'^（[一二三四五六七八九十]+）[^\n]+', tracks, re.M)
            put('tracks', '\n'.join(headings)[:2000] if headings else tracks[:600], tracks)
        registration = first_line(body, r'(?:参赛者|参赛选手).*?(?:官方网站|官网).*?注册')
        put('registration_method', registration[:1500], registration)
        # 报名入口须确实来自页面链接，且限该赛事官方注册子域名。
        for anchor in soup.select('a[href]'):
            url = urljoin(self.base_url, anchor['href'])
            if urlsplit(url).hostname == 'reg.aicomp.cn' and '报名' in anchor.get_text():
                data['registration_url'] = url
                data.setdefault('source_link_evidence', {})['registration_url'] = {'url': url, 'label': anchor.get_text(strip=True), 'scope': 'official_navigation'}
                break
        if registration and data['registration_deadline']:
            data['deadline_notes'] = '\n'.join(filter(None, [data['deadline_notes'], registration]))


class NmmcmAdapter(Adapter):
    key = 'nmmcm'
    hosts = ('www.nmmcm.org.cn', 'nmmcm.org.cn')
    base_url = 'https://www.nmmcm.org.cn/'
    name = '数维杯官方赛事通知'
    title_selector = 'h1.article-title'
    meta_selector = '.article-meta'
    category_code, category_name = 'mathematical-modeling', '数学建模'
    category_basis = '适配器分类：数维杯数学建模挑战赛'

    def accept_link(self, title, url):
        return bool(re.search(r'/News/\d+\.html$', urlsplit(url).path)
                    and re.match(r'20\d{2}年?第[一二三四五六七八九十百\d]+届数维杯', title)
                    and title.endswith('报名通知') and '集体' not in title)

    def edition(self, title, year):
        season = re.search(r'[（(](春季赛|秋季赛)[）)]', title)
        return year + (' ' + season.group(1) if season else '')

    def fields(self, data, body, root, soup, put):
        self.common_fields(data, body, put)
        eligibility = first_line(body, r'参赛对象[：:]')
        put('eligibility', eligibility, eligibility)
        if '全国' in eligibility:
            put('level', 'national', eligibility)
        team = re.search(r'每队\s*(\d+)\s*[–—\-至～~]\s*(\d+)\s*名?学生', eligibility)
        if team:
            put('team_size_min', int(team.group(1)), eligibility)
            put('team_size_max', int(team.group(2)), eligibility)
            put('participation_type', 'team', eligibility)
        tracks = first_line(body, r'赛题设置[：:]')
        put('tracks', tracks, tracks)
        registration = first_line(body, r'在线支付[：:]')
        put('registration_method', registration, registration)
        for anchor in root.select('a[href]'):
            url = urljoin(self.base_url, anchor['href'])
            if urlsplit(url).hostname == 'www.mojinghub.com' and '/competitions/swbmcm/' in urlsplit(url).path:
                put('registration_url', url, url)
                break


ADAPTERS = {adapter.key: adapter for adapter in (AicompAdapter(), NmmcmAdapter())}
