import hashlib
import json

from common.models import require
from common.snapshots import json_object


def source_hash(obj):
    values = [obj.title, obj.body_text, obj.source_published_on, obj.source_updated_on, obj.source_time_text]
    return hashlib.sha256(json.dumps(values, ensure_ascii=False, default=str, separators=(',', ':')).encode('utf-8')).hexdigest()


def validate_model(obj):
    name = type(obj).__name__
    if name == 'SourceVersion':
        require(obj.first_fetch.source_id == obj.source_id, '来源版本与首次抓取的配置不一致。')
        require(obj.content_hash == source_hash(obj), '内容哈希与来源文本不一致。')
    elif name == 'ProcessingResult':
        require(isinstance(obj.candidate,dict) and isinstance(obj.evidence,dict), '候选和证据必须为对象。')
        for key in ['missing_fields','validation_errors']:
            require(isinstance(getattr(obj,key),list) and all(isinstance(v,str) for v in getattr(obj,key)), '缺项/错误必须为文字列表。')
        require(len(json.dumps([obj.candidate,obj.evidence,obj.missing_fields,obj.validation_errors],ensure_ascii=False)) <= 200000, '处理结果超出长度限制。')
        if obj.status == 'accepted' and obj.task_type == 'newsletter_draft':
            require(obj.newsletter_revision.status == 'draft', '采纳快讯结果只能写入草稿。')
    elif name == 'ProcessingInput':
        require(obj.result.task_type == 'newsletter_draft', '输入引用只适用于快讯草稿任务。')
        json_object(obj.snapshot, {'title','body','source_url','version','updated_at'}, ('title','body','source_url'))
        require(all(isinstance(obj.snapshot[f],str) for f in ['title','body','source_url']), '快讯输入标题、正文、来源须为文字。')
        rows=list(type(obj).objects.filter(result_id=obj.result_id).exclude(pk=obj.pk).values_list('snapshot',flat=True))
        require(len(rows) < 10, '一次最多 10 条引用。')
        rows.append(obj.snapshot)
        require(sum(len(row.get('title',''))+len(row.get('body','')) for row in rows) <= 20000, '快讯输入超过 20000 字符。')
