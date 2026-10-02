"""受控附件文本提取；不执行文档内容，不进行 OCR 或访问附件内链接。"""
from io import BytesIO
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import unquote, urlsplit
from xml.etree import ElementTree
from zipfile import BadZipFile, ZipFile

from ingestion.http import FetchError, MAX_DOCUMENT_BYTES, OfficialClient, checked_url

MAX_PDF_PAGES = 100
MAX_TEXT_CHARACTERS = 200_000
MAX_XML_BYTES = 8_000_000
MAX_ARCHIVE_BYTES = 32_000_000
MAX_ARCHIVE_ENTRIES = 512
MAX_PDF_STREAM_BYTES = 8_000_000
MAX_PDF_CONTENT_BYTES = 32_000_000
PARSE_TIMEOUT_SECONDS = 20
WORD_NAMESPACES = {
    'http://schemas.openxmlformats.org/wordprocessingml/2006/main',
    'http://purl.oclc.org/ooxml/wordprocessingml/main',
}
DOCX_MAIN_CONTENT_TYPE = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml'


def _limited_text(parts):
    text = '\n'.join(parts).replace('\x00', '').strip()
    if len(text) > MAX_TEXT_CHARACTERS:
        raise FetchError('document_text_limit', '附件文本超过 20 万字上限，需人工核验。')
    if not text:
        raise FetchError('document_no_text', '附件未提取到可用文本；可能为扫描件，需人工核验。')
    return text


def _pdf_text(content):
    from pypdf import PdfReader, apply_configuration
    from pypdf.errors import LimitReachedError

    try:
        # 配置只作用于本解析上下文；禁用可调用外部程序的 JBIG2 解码器。
        with apply_configuration(
            maximum_declared_stream_length=MAX_PDF_STREAM_BYTES,
            array_based_stream_maximum_output_length=MAX_PDF_STREAM_BYTES,
            zlib_maximum_output_length=MAX_PDF_STREAM_BYTES,
            zlib_maximum_recovery_input_length=1_000_000,
            lzw_maximum_output_length=MAX_PDF_STREAM_BYTES,
            run_length_maximum_output_length=MAX_PDF_STREAM_BYTES,
            jbig2_maximum_output_length=MAX_PDF_STREAM_BYTES,
            image_maximum_buffer_size=MAX_PDF_STREAM_BYTES,
            flate_maximum_columns=100_000,
            flate_maximum_row_length=1_000_000,
            page_tree_maximum_entries=2_000,
            page_tree_maximum_depth=30,
            xform_maximum_invocations_per_extraction=500,
            jbig2dec_binary=None,
            disable_legacy_handling=True,
        ):
            reader = PdfReader(BytesIO(content), strict=True)
            if reader.is_encrypted:
                raise FetchError('encrypted_document', '加密附件不自动解密，需提供公开可读版本。')
            pages = len(reader.pages)
            if pages > MAX_PDF_PAGES:
                raise FetchError('document_page_limit', 'PDF 超过 100 页上限，需人工核验。')
            parts, text_size, content_size = [], 0, 0
            for page in reader.pages:
                stream = page.get_contents()
                if stream is not None:
                    content_size += len(stream.get_data())
                    if content_size > MAX_PDF_CONTENT_BYTES:
                        raise FetchError('document_expansion_limit', 'PDF 展开后内容超过限制，需人工核验。')
                text = page.extract_text() or ''
                text_size += len(text) + 1
                if text_size > MAX_TEXT_CHARACTERS:
                    raise FetchError('document_text_limit', '附件文本超过 20 万字上限，需人工核验。')
                parts.append(text)
            return _limited_text(parts), pages
    except FetchError:
        raise
    except LimitReachedError as exc:
        raise FetchError('document_expansion_limit', 'PDF 结构或展开内容超过限制，需人工核验。') from exc
    except Exception as exc:
        # 不把解析器内部报错或文档内容写进运行日志。
        raise FetchError('invalid_document', 'PDF 无法安全解析，需人工核验。') from exc


def _xml(content):
    if len(content) > MAX_XML_BYTES:
        raise FetchError('document_expansion_limit', 'DOCX 单个 XML 文件超过展开限制。')
    # 处理 UTF-8/16/32 XML 的 DTD 标记，拒绝实体展开。
    compact = content.replace(b'\x00', b'')
    if re.search(br'<!\s*(?:DOCTYPE|ENTITY)\b', compact, re.I):
        raise FetchError('unsafe_document', 'DOCX 含不受支持的实体声明，需人工核验。')
    return ElementTree.fromstring(content)


def _word_text(root):
    parts = []
    size = 0
    for event, node in _walk(root):
        namespace, _, tag = node.tag[1:].partition('}') if node.tag.startswith('{') else ('', '', node.tag)
        if namespace not in WORD_NAMESPACES:
            continue
        value = ''
        if event == 'start' and tag == 't':
            value = node.text or ''
        elif event == 'start' and tag == 'tab':
            value = '\t'
        elif (event == 'start' and tag in ('br', 'cr')) or (event == 'end' and tag in ('p', 'tr')):
            value = '\n'
        size += len(value)
        if size > MAX_TEXT_CHARACTERS:
            raise FetchError('document_text_limit', '附件文本超过 20 万字上限，需人工核验。')
        parts.append(value)
    return ''.join(parts).strip()


def _walk(root):
    # 非递归遍历，深嵌套 XML 不消耗 Python 调用栈。
    stack = [('start', root)]
    while stack:
        event, node = stack.pop()
        yield event, node
        if event == 'start':
            stack.append(('end', node))
            stack.extend(('start', child) for child in reversed(node))


def _docx_text(content):
    try:
        with ZipFile(BytesIO(content)) as archive:
            infos = archive.infolist()
            names = [item.filename for item in infos]
            if len(infos) > MAX_ARCHIVE_ENTRIES or len(set(names)) != len(names):
                raise FetchError('document_archive_limit', 'DOCX 包含过多或重复文件，需人工核验。')
            if sum(item.file_size for item in infos) > MAX_ARCHIVE_BYTES:
                raise FetchError('document_expansion_limit', 'DOCX 展开大小超过 32 MB 上限。')
            for item in infos:
                # 仅内存读取确切文件名；仍拒绝路径穿越、加密 ZIP 和宏文件。
                normalized = item.filename.replace('\\', '/')
                if normalized.startswith('/') or '..' in normalized.split('/') or ':' in normalized:
                    raise FetchError('unsafe_document', 'DOCX 包含不安全文件路径。')
                if item.flag_bits & 1:
                    raise FetchError('encrypted_document', '加密附件不自动解密，需提供公开可读版本。')
                if 'vbaproject' in normalized.lower():
                    raise FetchError('unsupported_document', 'DOCX 含宏文件，需人工核验。')
            if '[Content_Types].xml' not in names or 'word/document.xml' not in names:
                raise FetchError('unsupported_document', '压缩包不是有效的 DOCX 文档。')

            def read_xml(name):
                if archive.getinfo(name).file_size > MAX_XML_BYTES:
                    raise FetchError('document_expansion_limit', 'DOCX 单个 XML 文件超过展开限制。')
                with archive.open(name) as member:
                    return _xml(member.read(MAX_XML_BYTES + 1))

            types = read_xml('[Content_Types].xml')
            if any('macroenabled' in node.attrib.get('ContentType', '').lower() for node in types):
                raise FetchError('unsupported_document', '不自动处理启用宏的 Office 文档。')
            if not any(node.attrib.get('PartName') == '/word/document.xml'
                       and node.attrib.get('ContentType') == DOCX_MAIN_CONTENT_TYPE for node in types):
                raise FetchError('unsupported_document', '附件不是标准的无宏 DOCX 文档。')
            # 正文包含表格；脚注/尾注可能包含规则。关系文件和嵌入附件一律不跟随。
            selected = ['word/document.xml'] + [name for name in (
                'word/footnotes.xml', 'word/endnotes.xml') if name in names]
            parts = [_word_text(read_xml(name)) for name in selected]
            return _limited_text(parts), None
    except FetchError:
        raise
    except (BadZipFile, ElementTree.ParseError, OSError, ValueError, RuntimeError, NotImplementedError) as exc:
        raise FetchError('invalid_document', 'DOCX 无法安全解析，需人工核验。') from exc


def _parse_document(content):
    if len(content) > MAX_DOCUMENT_BYTES:
        raise FetchError('document_too_large', '附件超过 8 MB 上限。')
    if content.startswith(b'%PDF-'):
        body, pages = _pdf_text(content)
        return {'body': body, 'document_format': 'pdf', 'page_count': pages}
    if content.startswith(b'PK\x03\x04'):
        body, pages = _docx_text(content)
        return {'body': body, 'document_format': 'docx', 'page_count': pages}
    if content.startswith(b'\xd0\xcf\x11\xe0'):
        raise FetchError('legacy_document', '旧版 DOC 或加密 Office 附件暂不支持，需人工核验。')
    raise FetchError('unsupported_document', '附件不是可解析的 PDF 或 DOCX；扫描图片需人工核验。')


def _parse_isolated(content):
    """解析子进程有时间上限，不加载 Django、不访问数据库或文档内 URL。"""
    try:
        result = subprocess.run(
            [sys.executable, '-m', 'competition_catalog.attachments', '--worker'],
            input=content, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            timeout=PARSE_TIMEOUT_SECONDS, check=False,
            cwd=str(Path(__file__).resolve().parents[1]),
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
        )
    except subprocess.TimeoutExpired as exc:
        raise FetchError('document_parse_timeout', '附件解析超过 20 秒，需人工核验。') from exc
    except OSError as exc:
        raise FetchError('document_parser_unavailable', '附件解析进程暂不可用。') from exc
    try:
        output = json.loads(result.stdout)
        if 'error' in output:
            raise FetchError(output['error']['code'], output['error']['message'])
        if result.returncode or not isinstance(output.get('body'), str):
            raise ValueError('worker failed')
        return output
    except (ValueError, KeyError, TypeError) as exc:
        raise FetchError('invalid_document', '附件解析未正常完成，需人工核验。') from exc


def fetch_attachment(site, attachment, *, client=None):
    """返回待核验正文；调用方负责版本存档与赛事归属，不从附件自动推断日期。"""
    hosts = set(site.allowed_hosts)
    try:
        url = checked_url(attachment.get('url', ''), hosts, resolve=False)
    except (ValueError, TypeError) as exc:
        raise FetchError('unsafe_url', '附件地址无效。') from exc
    own_client = client is None
    if own_client:
        client = OfficialClient(hosts)
    elif hasattr(client, 'hosts') and not set(client.hosts).issubset(hosts):
        raise FetchError('unsafe_client', '附件下载器白名单超出当前官网授权范围。')
    try:
        document = client.get_document(url)
        final_url = checked_url(document.url, hosts, resolve=False)
        parsed = _parse_isolated(document.content)
    finally:
        if own_client:
            client.close()
    title = attachment.get('title') or unquote(urlsplit(final_url).path.rsplit('/', 1)[-1]) or '官方附件'
    title = re.sub(r'\s+', ' ', str(title)).strip()[:500]
    return {
        'url': final_url, 'title': title, 'body': parsed['body'],
        'attachments': [], 'source_published_on': None,
        'page_kind': 'notice', 'status': 'pending',
        'document_format': parsed['document_format'], 'page_count': parsed['page_count'],
    }


def _worker():
    try:
        output = _parse_document(sys.stdin.buffer.read(MAX_DOCUMENT_BYTES + 1))
    except FetchError as exc:
        output = {'error': {'code': exc.code, 'message': str(exc)}}
    except Exception:
        output = {'error': {'code': 'invalid_document', 'message': '附件无法安全解析，需人工核验。'}}
    sys.stdout.buffer.write(json.dumps(output, ensure_ascii=False).encode('utf-8'))


if __name__ == '__main__' and sys.argv[1:] == ['--worker']:
    _worker()
