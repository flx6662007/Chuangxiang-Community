"""有限官网监测：版本存档供后台处理，不把通用网页解析直接发布成赛事。"""
from datetime import date, timedelta
import hashlib
import ipaddress
import json
import re
import unicodedata
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup
from django.db import transaction
from django.utils import timezone

from ingestion.http import FetchError, OfficialClient, checked_url
from ingestion.locks import source_mutex
from .models import MonitorRun, OfficialNotice

NOTICE_WORDS = re.compile(r'报名|通知|章程|规程|赛程|竞赛规则|征集|参赛|启动|赛题|'
                          r'announcement|registration|rules|deadline|call for', re.I)
ATTACHMENT = re.compile(r'\.(?:pdf|docx?|zip|rar|xlsx?)(?:$|[?#])', re.I)


def normalize_name(value):
    value = unicodedata.normalize('NFKC', value).lower()
    value = re.sub(r'20\d{2}年?|第[一二三四五六七八九十百零\d]+届', '', value)
    return re.sub(r'[^a-z0-9\u4e00-\u9fff]', '', value)


def related_title(site, title):
    normalized = normalize_name(title)
    names = [normalize_name(site.entry.name), *(normalize_name(x) for x in site.entry.aliases)]
    return any(len(name) >= 4 and name in normalized for name in names)


def discover(site, page):
    """只跟随已核对域名，不根据正文自行扩大站点范围。"""
    urls = []
    priorities = {}
    for anchor in BeautifulSoup(page.text, 'html.parser').select('a[href]'):
        title = anchor.get_text(' ', strip=True)
        if not (related_title(site, title) or (site.dedicated and NOTICE_WORDS.search(title))):
            continue
        try:
            raw = urljoin(page.url, anchor['href'])
            if ATTACHMENT.search(raw):
                continue
            url = checked_url(raw, site.allowed_hosts, resolve=False)
        except (FetchError, ValueError):
            continue
        if url not in urls and url != page.url:
            urls.append(url)
            # New links with actual entry information precede result reports or old editions.
            # This only prioritizes fetching; publication still requires independent extraction.
            years = [int(value) for value in re.findall(r'20\d{2}', title)]
            current_year = timezone.localdate().year
            score = 0
            if current_year in years or current_year + 1 in years:
                score += 6
            elif years and max(years) < current_year:
                score -= 8
            if re.search(r'报名|参赛指南|参赛说明|征集|征稿|竞赛通知|大赛通知|竞赛规程', title):
                score += 4
            if re.search(r'获奖|名单|公示|颁奖|圆满|成功举办|闭幕|图集|观赛|住宿|研学', title):
                score -= 6
            priorities[url] = score
    return sorted(urls, key=lambda url: -priorities[url])


def discover_indexes(site, page):
    """从官方通知页自身的导航取得列表入口，不猜测网站路径。"""
    if site.dedicated:
        return []
    labels = ('竞赛通知', '赛事动态', '通知公告', '大赛通知', '通知通告', '新闻公告',
              '新闻动态', '新闻中心', '学生活动', 'Notices', 'Announcements', 'News')
    matches = []
    for anchor in BeautifulSoup(page.text, 'html.parser').select('a[href]'):
        label = anchor.get_text(' ', strip=True)
        if label not in labels:
            continue
        try:
            url = checked_url(urljoin(page.url, anchor['href']), site.allowed_hosts, resolve=False)
        except (FetchError, ValueError):
            continue
        if url != page.url:
            matches.append((labels.index(label), url))
    return list(dict.fromkeys(url for _, url in sorted(matches)))[:1]


def parse_page(site, page, *, index=False):
    soup = BeautifulSoup(page.text, 'html.parser')
    root = None
    for selector in ('.v_news_content', '.wp_articlecontent', '.TRS_Editor', '.TRS_UEDITOR',
                     '.article-content', '.news_details_content', '.article-body',
                     '.entry-content', '#zoom', 'article', 'main'):
        root = soup.select_one(selector)
        if root:
            break
    if root is None:
        root = soup.body or soup
    heading = root.select_one('h1, .newstitle, .article-title, .arti_title')
    title = (heading or soup.title).get_text(' ', strip=True) if heading or soup.title else site.entry.name
    for item in root.select('script,style,iframe,form,nav,header,footer,noscript,.cookie-banner'):
        item.decompose()
    attachments = []
    for anchor in root.select('a[href]'):
        try:
            url = urljoin(page.url, anchor['href'])
            if not ATTACHMENT.search(url) or urlsplit(url).scheme not in ('https', 'http'):
                continue
            host = urlsplit(url).hostname or ''
            url = checked_url(url, [host], resolve=False)
            try:
                if not ipaddress.ip_address(host).is_global:
                    continue
            except ValueError:
                if '.' not in host or host.endswith(('.local', '.internal', '.localhost')):
                    continue
            attachments.append({'title': anchor.get_text(' ', strip=True)[:200], 'url': url[:2048]})
        except (FetchError, ValueError):
            continue
    for br in root.select('br'):
        br.replace_with('\n')
    for item in root.select('p,h1,h2,h3,h4,li,tr'):
        item.append('\n')
    body = '\n'.join(re.sub(r'[ \t\xa0\u3000]+', ' ', line).strip()
                     for line in root.get_text('').splitlines() if line.strip())
    if len(body) < 80:
        raise FetchError('empty_or_javascript', '正文不足，可能为动态页面、登录入口或错误页；没有生成赛事。')
    if len(body) > 200000:
        raise FetchError('body_too_large', '正文超过保存上限。')
    if re.search(r'access denied|just a moment|checking your browser|访问验证|人机验证', title, re.I):
        raise FetchError('access_challenge', '来源要求访问验证，本轮跳过。')
    published = None
    meta = soup.select_one('meta[property="article:published_time"], meta[name="PubDate"], meta[name="publishdate"]')
    date_text = meta.get('content', '') if meta else ''
    if not date_text:
        explicit = re.search(r'(?:发布日期|发布时间|发表时间)\s*[：:]?\s*(20\d{2}[-年/]\d{1,2}[-月/]\d{1,2})', body)
        date_text = explicit[1] if explicit else ''
    match = re.search(r'(20\d{2})[-年/](\d{1,2})[-月/](\d{1,2})', date_text)
    if match:
        try:
            published = date(*map(int, match.groups()))
        except ValueError:
            pass
    is_notice = related_title(site, title) or (site.dedicated and bool(NOTICE_WORDS.search(title)))
    kind = 'notice' if is_notice and (not index or heading or root is not soup.body) else 'index'
    years = [int(value) for value in re.findall(r'20\d{2}', title)]
    historical = bool((years and max(years) < timezone.localdate().year)
                      or (not years and published and published.year < timezone.localdate().year))
    status = 'historical' if historical else ('attachment' if attachments and len(body) < 700 else 'pending')
    return dict(title=title[:500], body=body, attachments=attachments[:50], source_published_on=published,
                page_kind=kind, status=status)


@transaction.atomic
def save_page(site, page, parsed):
    content = {key: parsed[key] for key in ('title', 'body', 'attachments')}
    digest = hashlib.sha256(json.dumps({**content, 'source_published_on': str(parsed['source_published_on'])},
                                      ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    old = OfficialNotice.objects.filter(site=site, url=page.url, content_hash=digest).first()
    # A→B→A 仍保留两个不可变正文，只更改当前版本指针和最近成功时间。
    OfficialNotice.objects.filter(site=site, url=page.url, is_current_version=True).exclude(content_hash=digest).update(is_current_version=False)
    if old:
        old.last_seen_at, old.is_current_version = timezone.now(), True
        old.status, old.page_kind = parsed['status'], parsed['page_kind']
        old.save(update_fields=['last_seen_at', 'is_current_version', 'status', 'page_kind'])
        return False
    OfficialNotice.objects.create(site=site, url=page.url, content_hash=digest, **parsed)
    return True


class Session:
    """一轮共享域名客户端与成功响应，多个目录赛项不会重复请求同一通知。"""
    def __init__(self):
        self.clients, self.pages = {}, {}

    def get(self, site, url):
        key = tuple(sorted(site.allowed_hosts))
        checked_url(url, key, resolve=False)
        if (key, url) not in self.pages:
            if key not in self.clients:
                self.clients[key] = OfficialClient(key)
            self.pages[key, url] = self.clients[key].get(url)
        return self.pages[key, url]

    def close(self):
        for client in self.clients.values():
            client.close()


def sync_site(site, *, max_pages=3, session=None):
    owned = session is None
    session = session or Session()
    with source_mutex(f'catalog-{site.pk}') as acquired:
        if not acquired:
            return {'code': site.entry.code, 'status': 'locked', 'pages': 0}
        # 命令可提前取得一批对象；等待锁期间入口/目录可能已被管理员停用。
        # 按拿锁后的真实配置决定是否发出任何请求，清除缓存的 entry 关系。
        site.refresh_from_db()
        if not site.enabled or not site.entry.is_active:
            if owned:
                session.close()
            return {'code': site.entry.code, 'status': 'disabled', 'pages': 0}
        now = timezone.now()
        MonitorRun.objects.filter(site=site, status='running').update(status='interrupted', finished_at=now, error='上次进程已结束。')
        run = MonitorRun.objects.create(site=site)
        errors = []
        try:
            page = session.get(site, site.url)
            urls = discover(site, page)
            index_urls = discover_indexes(site, page)
            # 首先保存入口快照，版式改变/暂时没有新通知也能看见实际获取状态。
            try:
                parsed = parse_page(site, page, index=True)
                created = save_page(site, page, parsed)
                run.pages += 1
                run.created += int(created)
                run.unchanged += int(not created)
            except FetchError as exc:
                errors.append(f'{exc.code}: {exc}')
            observed = {row['url']: row['last_seen_at'] for row in
                        site.notices.filter(is_current_version=True).values('url', 'last_seen_at')}
            # 新通知优先，其余最久未读取先；历史链接仍可检查变更，但不会变成新届赛事。
            known = [url for url in observed if url != page.url and urlsplit(url).hostname in site.allowed_hosts
                     and not ATTACHMENT.search(url)]
            urls = list(dict.fromkeys(urls + known))
            attempts = dict(site.page_attempts)
            urls.sort(key=lambda url: attempts.get(url, observed[url].timestamp() if url in observed else 0))
            urls = list(dict.fromkeys(index_urls + urls))
            budget = max(0, max_pages - 1)
            position = 0
            while position < len(urls) and position < budget:
                url = urls[position]
                position += 1
                attempts[url] = timezone.now().timestamp()
                try:
                    detail = session.get(site, url)
                    parsed = parse_page(site, detail, index=url in index_urls)
                    created = save_page(site, detail, parsed)
                    run.pages += 1
                    run.created += int(created)
                    run.unchanged += int(not created)
                    if url in index_urls:
                        new_urls = [link for link in discover(site, detail) if link not in urls and link != page.url]
                        # 新旧详情共享轮换顺序：此前失败但没有存档的链接也必须排队，
                        # 不能因为每轮被列表“新发现”而一直抢占已成功通知的复查预算。
                        remainder = list(dict.fromkeys(urls[position:] + new_urls))
                        remainder.sort(key=lambda link: attempts.get(
                            link, observed[link].timestamp() if link in observed else 0))
                        urls[position:] = remainder
                except (FetchError, ValueError) as exc:
                    errors.append(f'{getattr(exc, "code", "parse_error")}: {str(exc)[:200]}')
            # Keep separate bounded histories so attachment parsing does not displace
            # normal HTML rotation, or vice versa. All writers share this site's lock.
            attachment_attempts = {key: value for key, value in attempts.items() if key.startswith('attachment')}
            html_attempts = {key: value for key, value in attempts.items() if not key.startswith('attachment')}
            site.page_attempts = {
                **dict(sorted(html_attempts.items(), key=lambda x: x[1], reverse=True)[:500]),
                **dict(sorted(attachment_attempts.items(), key=lambda x: x[1], reverse=True)[:500]),
            }
            if not run.pages:
                run.status = 'failed'
            elif errors:
                run.status = 'partial'
            elif not urls:
                run.status = 'snapshot_only'
            else:
                run.status = 'succeeded'
        except (FetchError, ValueError) as exc:
            run.status = 'failed'
            errors.append(f'{getattr(exc, "code", "parse_error")}: {str(exc)[:300]}')
        finally:
            run.finished_at = timezone.now()
            run.error = '；'.join(errors)[:1000]
            run.save()
            site.last_checked_at, site.last_status, site.last_error = run.finished_at, run.status, run.error
            if run.pages:
                site.last_success_at = run.finished_at
                site.consecutive_failures = 0
            else:
                site.consecutive_failures = min(site.consecutive_failures + 1, 100)
            site.next_check_at = run.finished_at + timedelta(hours=min(72, 6 * 2 ** min(site.consecutive_failures, 4)))
            site.save(update_fields=['last_checked_at', 'last_status', 'last_error', 'last_success_at', 'next_check_at', 'consecutive_failures', 'page_attempts'])
            if owned:
                session.close()
        return dict(code=site.entry.code, status=run.status, pages=run.pages, created=run.created,
                    unchanged=run.unchanged, error=run.error)
