from io import BytesIO
import os
import subprocess
from types import SimpleNamespace
from unittest.mock import patch
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile

from django.test import SimpleTestCase
import httpx
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from ingestion.http import Document, FetchError, OfficialClient
from .attachments import (
    DOCX_MAIN_CONTENT_TYPE, _parse_document, _parse_isolated, fetch_attachment,
)

URL = 'https://contest.example/rules.pdf'
SITE = SimpleNamespace(allowed_hosts=['contest.example'])


def pdf_bytes(text='Rules: registration deadline 2030-10-15.', *, pages=1, encrypted=False):
    writer = PdfWriter()
    for _ in range(pages):
        page = writer.add_blank_page(width=600, height=800)
        if text:
            font = DictionaryObject({
                NameObject('/Type'): NameObject('/Font'),
                NameObject('/Subtype'): NameObject('/Type1'),
                NameObject('/BaseFont'): NameObject('/Helvetica'),
            })
            page[NameObject('/Resources')] = DictionaryObject({
                NameObject('/Font'): DictionaryObject({NameObject('/F1'): writer._add_object(font)}),
            })
            stream = DecodedStreamObject()
            escaped = text.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')
            stream.set_data(f'BT /F1 12 Tf 50 700 Td ({escaped}) Tj ET'.encode('ascii'))
            page[NameObject('/Contents')] = writer._add_object(stream.flate_encode())
    if encrypted:
        writer.encrypt('test-document-password')
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def docx_bytes(text='参赛学生不超过三人，报名截止以原文通知为准。', *, extra=None, xml=None):
    parts = {
        '[Content_Types].xml': (
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            f'<Override PartName="/word/document.xml" ContentType="{DOCX_MAIN_CONTENT_TYPE}"/>'
            '</Types>'
        ).encode(),
        'word/document.xml': (xml or (
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            f'<w:body><w:p><w:r><w:t>{escape(text)}</w:t></w:r></w:p></w:body></w:document>'
        )).encode(),
    }
    parts.update(extra or {})
    output = BytesIO()
    with ZipFile(output, 'w', ZIP_DEFLATED) as archive:
        for name, value in parts.items():
            archive.writestr(name, value)
    return output.getvalue()


class AttachmentParsingTests(SimpleTestCase):
    def assert_code(self, content, code):
        with self.assertRaises(FetchError) as caught:
            _parse_document(content)
        self.assertEqual(caught.exception.code, code)

    def test_pdf_text_preserves_rules_without_guessing_dates(self):
        parsed = _parse_document(pdf_bytes())
        self.assertEqual(parsed['document_format'], 'pdf')
        self.assertEqual(parsed['page_count'], 1)
        self.assertIn('2030-10-15', parsed['body'])
        self.assertNotIn('source_published_on', parsed)

    def test_scanned_or_blank_pdf_requires_manual_review(self):
        self.assert_code(pdf_bytes(text=''), 'document_no_text')

    def test_encrypted_pdf_is_not_decrypted(self):
        self.assert_code(pdf_bytes(encrypted=True), 'encrypted_document')

    def test_pdf_page_and_stream_expansion_limits(self):
        with patch('competition_catalog.attachments.MAX_PDF_PAGES', 1):
            self.assert_code(pdf_bytes(pages=2), 'document_page_limit')
        with patch('competition_catalog.attachments.MAX_PDF_STREAM_BYTES', 200):
            self.assert_code(pdf_bytes('A' * 2000), 'document_expansion_limit')

    def test_docx_reads_table_and_footnote_but_not_external_relationships(self):
        namespace = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
        xml = f'''<w:document xmlns:w="{namespace}"><w:body><w:tbl><w:tr><w:tc>
        <w:p><w:r><w:t>每队最多3名学生</w:t></w:r></w:p></w:tc></w:tr></w:tbl>
        <w:p><w:r><w:instrText>INCLUDETEXT https://private.example/secret</w:instrText></w:r>
        <w:hyperlink><w:r><w:t>官方报名链接</w:t></w:r></w:hyperlink></w:p></w:body></w:document>'''
        parsed = _parse_document(docx_bytes(xml=xml, extra={
            'word/footnotes.xml': f'<w:footnotes xmlns:w="{namespace}"><w:footnote><w:p><w:r><w:t>指导教师不计入学生人数。</w:t></w:r></w:p></w:footnote></w:footnotes>',
            'word/_rels/document.xml.rels': '<Relationships><Relationship Target="http://127.0.0.1/" TargetMode="External"/></Relationships>',
            'word/printerSettings/printerSettings1.bin': b'ignored settings',
        }))
        self.assertEqual(parsed['document_format'], 'docx')
        self.assertIsNone(parsed['page_count'])
        self.assertIn('每队最多3名学生', parsed['body'])
        self.assertIn('指导教师不计入学生人数', parsed['body'])
        self.assertNotIn('INCLUDETEXT', parsed['body'])
        self.assertNotIn('127.0.0.1', parsed['body'])

    def test_docx_rejects_macros_and_path_traversal(self):
        self.assert_code(docx_bytes(extra={'word/vbaProject.bin': b'macro'}), 'unsupported_document')
        self.assert_code(docx_bytes(extra={'../outside.txt': b'never written'}), 'unsafe_document')

    def test_docx_rejects_non_word_archive_and_xml_entities(self):
        content = docx_bytes(extra={'[Content_Types].xml': '<Types/>'})
        self.assert_code(content, 'unsupported_document')
        xml = '<!DOCTYPE a [<!ENTITY x "expanded">]><a>&x;</a>'
        self.assert_code(docx_bytes(xml=xml), 'unsafe_document')
        encoded = ('<?xml version="1.0" encoding="UTF-16"?>' + xml).encode('utf-16')
        self.assert_code(docx_bytes(extra={'word/document.xml': encoded}), 'unsafe_document')

    def test_docx_archive_and_text_limits_never_return_truncated_rules(self):
        with patch('competition_catalog.attachments.MAX_ARCHIVE_BYTES', 200):
            self.assert_code(docx_bytes('A' * 1000), 'document_expansion_limit')
        with patch('competition_catalog.attachments.MAX_ARCHIVE_ENTRIES', 1):
            self.assert_code(docx_bytes(), 'document_archive_limit')
        with patch('competition_catalog.attachments.MAX_TEXT_CHARACTERS', 10):
            self.assert_code(docx_bytes('A' * 100), 'document_text_limit')

    def test_invalid_pdf_old_doc_html_and_input_size_are_explicit(self):
        self.assert_code(b'%PDF-invalid', 'invalid_document')
        self.assert_code(b'\xd0\xcf\x11\xe0legacy doc', 'legacy_document')
        self.assert_code(b'<html>Please log in</html>', 'unsupported_document')
        with patch('competition_catalog.attachments.MAX_DOCUMENT_BYTES', 100):
            self.assert_code(docx_bytes(), 'document_too_large')

    def test_worker_runs_real_docx_parser_with_utf8_output(self):
        parsed = _parse_isolated(docx_bytes('中文规则可读，不推断日期。'))
        self.assertEqual(parsed['body'], '中文规则可读，不推断日期。')

    def test_worker_timeout_is_a_safe_fetch_error(self):
        with patch('competition_catalog.attachments.subprocess.run', side_effect=subprocess.TimeoutExpired('parser', 20)) as run:
            with self.assertRaises(FetchError) as caught:
                _parse_isolated(b'%PDF-')
        self.assertEqual(caught.exception.code, 'document_parse_timeout')
        self.assertEqual(run.call_args.kwargs['creationflags'], subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)

    def test_fetch_contract_keeps_original_source_and_does_not_follow_document_links(self):
        calls = []
        payload = docx_bytes('规则链接 https://elsewhere.example/rules 不自动请求。')
        def handle(request):
            calls.append(request.url.path)
            if request.url.path == '/robots.txt':
                return httpx.Response(404)
            return httpx.Response(200, content=payload, headers={'content-type': 'application/octet-stream'})
        client = OfficialClient(SITE.allowed_hosts, transport=httpx.MockTransport(handle), resolve=False, interval=0)
        self.addCleanup(client.close)
        parsed = fetch_attachment(SITE, {'url': URL, 'title': '官方竞赛章程'}, client=client)
        self.assertEqual(calls, ['/robots.txt', '/rules.pdf'])
        self.assertEqual(parsed['url'], URL)
        self.assertEqual(parsed['title'], '官方竞赛章程')
        self.assertEqual(parsed['status'], 'pending')
        self.assertIsNone(parsed['source_published_on'])
        self.assertEqual(parsed['attachments'], [])
        self.assertEqual(parsed['document_format'], 'docx')

    def test_fetch_rejects_initial_host_and_overbroad_client_without_download(self):
        client = SimpleNamespace(hosts={'contest.example', 'other.example'}, get_document=lambda url: self.fail('must not download'))
        with self.assertRaises(FetchError) as caught:
            fetch_attachment(SITE, {'url': 'https://other.example/doc.pdf'}, client=client)
        self.assertEqual(caught.exception.code, 'unsafe_url')
        with self.assertRaises(FetchError) as caught:
            fetch_attachment(SITE, {'url': URL}, client=client)
        self.assertEqual(caught.exception.code, 'unsafe_client')


class AttachmentDownloadTests(SimpleTestCase):
    def make_client(self, handler, *, resolve=False):
        client = OfficialClient(SITE.allowed_hosts, transport=httpx.MockTransport(handler), resolve=resolve, interval=0)
        self.addCleanup(client.close)
        return client

    def test_html_get_still_rejects_pdf_and_document_get_accepts_bytes(self):
        def handle(request):
            return httpx.Response(404) if request.url.path == '/robots.txt' else httpx.Response(
                200, content=b'%PDF-bytes', headers={'content-type': 'application/pdf'})
        client = self.make_client(handle)
        with self.assertRaises(FetchError) as caught:
            client.get(URL)
        self.assertEqual(caught.exception.code, 'unsupported_content')
        document = client.get_document(URL)
        self.assertIsInstance(document, Document)
        self.assertEqual(document.content, b'%PDF-bytes')

    def test_document_rejects_html_and_transport_compression(self):
        for headers, code in [({'content-type': 'text/html'}, 'unsupported_document'),
                              ({'content-type': 'application/pdf', 'content-encoding': 'gzip'}, 'unsupported_document_encoding')]:
            with self.subTest(headers=headers):
                client = self.make_client(lambda request: httpx.Response(404) if request.url.path == '/robots.txt' else httpx.Response(
                    200, headers=headers, stream=httpx.ByteStream(b'bytes')))
                with self.assertRaises(FetchError) as caught:
                    client.get_document(URL)
                self.assertEqual(caught.exception.code, code)

    def test_declared_and_streamed_size_limits(self):
        for declared in (True, False):
            with self.subTest(declared=declared):
                headers = {'content-type': 'application/pdf'}
                if declared:
                    headers['content-length'] = '101'
                client = self.make_client(lambda request: httpx.Response(404) if request.url.path == '/robots.txt' else httpx.Response(
                    200, headers=headers, stream=httpx.ByteStream(b'x' * 101)))
                with patch('ingestion.http.MAX_DOCUMENT_BYTES', 100), self.assertRaises(FetchError) as caught:
                    client.get_document(URL)
                self.assertEqual(caught.exception.code, 'document_too_large')

    def test_redirect_cannot_leave_authorized_hosts(self):
        seen = []
        def handle(request):
            seen.append(str(request.url))
            return httpx.Response(404) if request.url.path == '/robots.txt' else httpx.Response(
                302, headers={'location': 'http://127.0.0.1/internal'})
        client = self.make_client(handle)
        with self.assertRaises(FetchError) as caught:
            client.get_document(URL)
        self.assertEqual(caught.exception.code, 'unsafe_url')
        self.assertFalse(any('127.0.0.1' in url for url in seen))

    def test_robots_denial_and_unavailable_policy_prevent_document_request(self):
        for status in (200, 403):
            seen = []
            def handle(request):
                seen.append(request.url.path)
                return httpx.Response(status, text='User-agent: *\nDisallow: /rules.pdf')
            client = self.make_client(handle)
            with self.assertRaises(FetchError) as caught:
                client.get_document(URL)
            self.assertEqual(caught.exception.code, 'robots_disallowed' if status == 200 else 'robots_unavailable')
            self.assertEqual(seen, ['/robots.txt'])

    def test_document_pins_public_ip_retains_tls_and_robots_rate(self):
        seen = []
        def handle(request):
            seen.append((request.url.host, request.headers['host'], request.extensions.get('sni_hostname')))
            if request.url.path == '/robots.txt':
                return httpx.Response(200, text='User-agent: *\nCrawl-delay: 2')
            self.assertEqual(request.headers['accept-encoding'], 'identity')
            return httpx.Response(200, content=b'%PDF-', headers={'content-type': 'application/pdf'})
        client = self.make_client(handle, resolve=True)
        with patch.object(client, '_public_address', return_value='120.55.167.15'), patch('ingestion.http.time.sleep') as sleep:
            self.assertEqual(client.get_document(URL).url, URL)
        self.assertEqual(client.interval, 2)
        self.assertTrue(any(call.args[0] > 1 for call in sleep.call_args_list))
        self.assertEqual(seen, [('120.55.167.15', 'contest.example', 'contest.example')] * 2)

    def test_document_retries_remain_bounded(self):
        attempts = []
        def handle(request):
            if request.url.path == '/robots.txt':
                return httpx.Response(404)
            attempts.append(request.url.path)
            return httpx.Response(503)
        client = self.make_client(handle)
        with patch('ingestion.http.time.sleep'), self.assertRaises(FetchError):
            client.get_document(URL)
        self.assertEqual(len(attempts), 3)
