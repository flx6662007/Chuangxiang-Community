"""后台信息库只读页面；不提供面向访客的内容检索接口。"""
from urllib.parse import urlencode

from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django.core.paginator import EmptyPage, Paginator
from django.http import Http404, HttpResponseBadRequest
from django.shortcuts import render
from django.views.decorators.http import require_GET

from .selectors import KINDS, STATUSES, admin_records, allowed_kinds

DATE_LABELS = {
    'registration_deadline': '报名截止日期', 'registration_deadline_at': '报名截止时刻',
    'registration_deadline_timezone': '报名截止来源时区',
    'submission_deadline': '作品提交截止日期', 'submission_deadline_at': '作品提交截止时刻',
    'submission_deadline_timezone': '作品提交来源时区',
    'campus_deadline': '校内截止日期', 'campus_deadline_at': '校内截止时刻',
    'campus_deadline_timezone': '校内截止来源时区',
    'deadline_on': '招募截止日期', 'deadline_at': '招募截止时刻', 'deadline_timezone': '招募截止来源时区',
}


@require_GET
def index(request):
    permitted = allowed_kinds(request.user)
    if not permitted:
        raise PermissionDenied
    query = request.GET.get('q', '').strip()
    kind = request.GET.get('kind', '')
    status = request.GET.get('status', '')
    page = request.GET.get('page', '1')
    if (len(query) > 200 or (kind and kind not in KINDS) or (status and status not in STATUSES)
            or not page.isascii() or not page.isdigit() or len(page) > 8 or int(page) < 1):
        return HttpResponseBadRequest('筛选参数无效。')
    rows = admin_records(request.user, query=query, kind=kind, status=status)
    try:
        page_obj = Paginator(rows, 20).page(int(page))
    except EmptyPage as exc:
        raise Http404('页码不存在。') from exc
    return render(request, 'information_library/index.html', {
        **admin.site.each_context(request), 'title': '信息库', 'page_obj': page_obj,
        'q': query, 'kind': kind, 'status': status,
        'kind_options': [(key, KINDS[key]) for key in permitted], 'status_options': STATUSES.items(),
        'filters': urlencode({'q': query, 'kind': kind, 'status': status}),
        'ai_count': sum(row['_ai_ready'] for row in rows),
    })


@require_GET
def detail(request, kind, identifier):
    if kind not in KINDS:
        raise Http404
    rows = admin_records(request.user, kind=kind)
    row = next((row for row in rows if row['id'] == identifier), None)
    if row is None:
        raise Http404
    # Django 模板不能读取下划线属性；明确传递后台专有展示字段。
    return render(request, 'information_library/detail.html', {
        **admin.site.each_context(request), 'title': row['title'], 'record': row,
        'ai_ready': row['_ai_ready'], 'maintenance': row['_maintenance'],
        'pending_sources': row.get('_pending_sources', []),
        'date_fields': [(DATE_LABELS.get(key, key), value) for key, value in row['dates'].items() if value],
    })
