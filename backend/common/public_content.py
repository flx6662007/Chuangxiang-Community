"""公共文本与来源链接清理；不依赖业务模型，不执行网络请求。"""
import html
import ipaddress
import re
from urllib.parse import parse_qsl, urlsplit, urlunsplit

from django.utils.html import strip_tags


def safe_source_url(value):
    """仅返回无凭据的公网 HTTP(S) 链接；不访问或解析远程地址。"""
    if not isinstance(value, str) or len(value) > 2048 or re.search(r'\s|[\x00-\x1f]', value):
        return ''
    try:
        parsed = urlsplit(value)
        host = (parsed.hostname or '').lower().rstrip('.')
        if (parsed.scheme not in ('http', 'https') or not host or parsed.username or parsed.password
                or parsed.port not in (None, 80, 443)):
            return ''
        if '.' not in host or host.endswith(('.localhost', '.local', '.internal', '.test', '.invalid')):
            return ''
        if not re.fullmatch(r'[a-z0-9.-]+', host):
            return ''
        if any(host == domain or host.endswith('.' + domain) for domain in ('example.com', 'example.org', 'example.net')):
            return ''
        try:
            if not ipaddress.ip_address(host).is_global:
                return ''
        except ValueError:
            if re.fullmatch(r'[0-9.]+', host):
                return ''  # 非标准点分地址（如 127.1）可能仍被浏览器解析为内网 IP。
        if any(key.lower() in ('password', 'token', 'secret', 'authorization', 'email', 'access_token')
               for key, _ in parse_qsl(parsed.query)):
            return ''
        return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, parsed.query, ''))
    except (ValueError, TypeError):
        return ''


def public_text(value):
    """结构化联系人字段不选取；公共自由文本中再剔除联系行、邮箱和电话号码。"""
    text = strip_tags(html.unescape(str(value or '')))
    lines = []
    for line in text.splitlines():
        if re.search(r'(?:联系方式|联系人|手机|电话|邮箱|微信|QQ|WeChat|E-?mail)\s*[：:]', line, re.I):
            continue
        line = re.sub(r'[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}', '[联系方式已省略]', line)
        line = re.sub(r'(?<!\d)(?:\+?86[ -]?)?1[3-9]\d{9}(?!\d)', '[联系方式已省略]', line)
        line = re.sub(r'(?<!\d)0\d{2,3}[- ]\d{7,8}(?!\d)', '[联系方式已省略]', line)
        lines.append(line.strip())
    return '\n'.join(line for line in lines if line)[:16000]
