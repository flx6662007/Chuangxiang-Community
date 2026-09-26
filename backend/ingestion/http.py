"""只访问适配器白名单的公开 HTML；不接受来自普通用户的 URL。"""
import ipaddress
import re
import socket
import time
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser

import httpx

USER_AGENT = 'ChuangxiangCompetitionSync/1.0 (+https://github.com/flx6662007/Chuangxiang-Community)'


class FetchError(Exception):
    def __init__(self, code, message, status=None):
        self.code, self.status = code, status
        super().__init__(message)


def checked_url(url, hosts, *, resolve=True):
    parts = urlsplit(url)
    host = (parts.hostname or '').lower()
    if (parts.scheme not in ('http', 'https') or host not in hosts or parts.username
            or parts.password or parts.port not in (None, 80, 443) or len(url) > 2048):
        raise FetchError('unsafe_url', '地址不属于适配器获准的官方站点。')
    if resolve:
        try:
            addresses = socket.getaddrinfo(host, parts.port or (443 if parts.scheme == 'https' else 80), type=socket.SOCK_STREAM)
        except OSError as exc:
            raise FetchError('dns_failure', '官方域名暂时无法解析。') from exc
        if not addresses or any(not ipaddress.ip_address(row[4][0]).is_global for row in addresses):
            raise FetchError('unsafe_address', '拒绝访问非公网地址。')
    return urlunsplit((parts.scheme, parts.netloc, parts.path or '/', parts.query, ''))


@dataclass
class Page:
    url: str
    text: str
    status: int = 200


class OfficialClient:
    """每页最多三次请求、三跳重定向、2 MB 解压后正文，站点间隔一秒。"""
    def __init__(self, hosts, *, transport=None, resolve=True, interval=1):
        self.hosts, self.resolve, self.interval = set(hosts), resolve, interval
        self.client = httpx.Client(
            headers={'User-Agent': USER_AGENT, 'Accept': 'text/html,text/plain;q=0.8'},
            timeout=httpx.Timeout(15, connect=5), follow_redirects=False,
            transport=transport, trust_env=False,
            limits=httpx.Limits(max_keepalive_connections=0),
        )
        self.robots, self.last_request, self.addresses = {}, 0, {}

    def close(self):
        self.client.close()

    def _public_address(self, host):
        if host in self.addresses:
            return self.addresses[host]
        try:
            addresses = [row[4][0] for row in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)]
        except OSError:
            addresses = []
        if not addresses or any(not ipaddress.ip_address(address).is_global for address in addresses):
            # 本机 TUN 代理可返回 fake-IP；向固定公网 DoH 服务重新求真实地址。
            # 仍然只连接校验通过的公网 IP，不将 198.18/私网加入允许列表。
            try:
                with self.client.stream('GET', 'https://1.1.1.1/dns-query',
                        params={'name': host, 'type': 'A'}, headers={'Accept': 'application/dns-json'}) as response:
                    if response.status_code != 200:
                        raise FetchError('dns_failure', '公共 DNS 解析暂时不可用。')
                    chunks, size = [], 0
                    for chunk in response.iter_bytes():
                        size += len(chunk)
                        if size > 65536:
                            raise FetchError('dns_failure', 'DNS 响应超过限制。')
                        chunks.append(chunk)
                    import json
                    answer = json.loads(b''.join(chunks))
                addresses = [row['data'] for row in answer.get('Answer', []) if row.get('type') == 1]
            except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
                raise FetchError('dns_failure', '无法取得官方域名的可信公网地址。') from exc
        if not addresses or any(not ipaddress.ip_address(address).is_global for address in addresses):
            raise FetchError('unsafe_address', '拒绝连接非公网地址。')
        self.addresses[host] = sorted(addresses, key=lambda address: ':' in address)[0]
        return self.addresses[host]

    def _get(self, url, *, robots=False):
        for attempt in range(3):
            current = url
            try:
                for hop in range(4):
                    current = checked_url(current, self.hosts, resolve=False)
                    if not robots:
                        self._check_robots(current)
                    time.sleep(max(0, self.interval - (time.monotonic() - self.last_request)))
                    self.last_request = time.monotonic()
                    parts = urlsplit(current)
                    request_url, request_options = current, {}
                    if self.resolve:
                        # 固定已核验 IP，防止校验后第二次解析发生 DNS 重绑定；TLS 仍核验原域名。
                        request_url = httpx.URL(current).copy_with(host=self._public_address(parts.hostname))
                        request_options = {'headers': {'Host': parts.netloc}, 'extensions': {'sni_hostname': parts.hostname}}
                    with self.client.stream('GET', request_url, **request_options) as response:
                        if response.status_code in (301, 302, 303, 307, 308):
                            if hop == 3 or not response.headers.get('location'):
                                raise FetchError('redirect_limit', '官方页面重定向过多。', response.status_code)
                            current = urljoin(current, response.headers['location'])
                            continue
                        if response.status_code != 200:
                            raise FetchError('http_error', f'官方页面返回 HTTP {response.status_code}。', response.status_code)
                        kind = response.headers.get('content-type', '').lower()
                        if kind and not any(v in kind for v in ('text/html', 'text/plain', 'application/xhtml')):
                            raise FetchError('unsupported_content', '当前适配器仅解析 HTML/纯文本；附件须另行核验。', response.status_code)
                        chunks, size = [], 0
                        for chunk in response.iter_bytes():
                            size += len(chunk)
                            if size > 2_000_000:
                                raise FetchError('page_too_large', '页面超过 2 MB 上限。')
                            chunks.append(chunk)
                        content = b''.join(chunks)
                        encoding = re.search(br'charset=["\s]*([\w-]+)', content[:4096], re.I)
                        charset = encoding.group(1).decode('ascii') if encoding else 'utf-8'
                        if charset.lower() not in ('utf-8', 'utf8', 'gbk', 'gb2312', 'gb18030'):
                            charset = 'utf-8'
                        return Page(current, content.decode(charset, errors='replace'), response.status_code)
            except httpx.TimeoutException as exc:
                error = FetchError('timeout', '获取官方页面超时，已有限次重试。')
            except httpx.RequestError as exc:
                error = FetchError('network_error', '获取官方页面失败，已有限次重试。')
            except FetchError as exc:
                error = exc
                if exc.status not in (408, 429, 500, 502, 503, 504):
                    raise
            if attempt < 2:
                time.sleep(attempt + 1)
        raise error

    def _check_robots(self, url):
        parts = urlsplit(url)
        origin = f'{parts.scheme}://{parts.netloc}'
        if origin not in self.robots:
            try:
                page = self._get(origin + '/robots.txt', robots=True)
                policy = RobotFileParser()
                policy.parse(page.text.splitlines())
            except FetchError as exc:
                if exc.status not in (404, 410):
                    raise FetchError('robots_unavailable', '无法确认站点 robots 规则，本轮跳过。', exc.status) from exc
                policy = None
            self.robots[origin] = policy
        policy = self.robots[origin]
        if policy and not policy.can_fetch(USER_AGENT, url):
            raise FetchError('robots_disallowed', '站点 robots 规则不允许采集此地址。')

    def get(self, url):
        return self._get(url)
