"""Import research cards independently from competition releases."""
import json
import os
import re
from datetime import date
from pathlib import Path
from tempfile import NamedTemporaryFile
from django.core.management.base import BaseCommand, CommandError
from information_library import selectors

FIELDS = {'id','title','unit','summary','participation','evidenceNote','date','verifiedOn','sourceUrl'}

class Command(BaseCommand):
    help = '独立导入科研资料到科研内容文件；默认预演，导入不开放科研展示。'
    def add_arguments(self, parser):
        parser.add_argument('--source', type=Path, required=True)
        parser.add_argument('--apply', action='store_true')
    def handle(self, *args, **options):
        try:
            data = json.loads(options['source'].read_text(encoding='utf-8-sig'))
            rows = data['laboratories']
            if not isinstance(rows,list) or not 1 <= len(rows) <= 1000: raise ValueError('条目数须为 1—1000')
            ids = set()
            for row in rows:
                if not isinstance(row,dict) or set(row) != FIELDS or any(not isinstance(v,str) or len(v)>20000 for v in row.values()): raise ValueError('每条须为约定的九个文本字段')
                if not re.fullmatch(r'[a-zA-Z0-9_-]{1,100}',row['id']) or row['id'] in ids: raise ValueError('编号无效或重复')
                if not row['title'].strip() or not selectors.safe_source_url(row['sourceUrl']): raise ValueError('标题或来源无效')
                for field in ('date','verifiedOn'):
                    if row[field]: date.fromisoformat(row[field])
                ids.add(row['id'])
            current = json.loads(selectors.EDITORIAL_PATH.read_text(encoding='utf-8'))
            unchanged = current.get('laboratories') == rows
            if options['apply'] and not unchanged:
                current['laboratories'] = rows
                with NamedTemporaryFile(mode='w',encoding='utf-8',dir=selectors.EDITORIAL_PATH.parent,delete=False) as temp:
                    json.dump(current,temp,ensure_ascii=False,indent=2);temp.write('\n')
                os.replace(temp.name,selectors.EDITORIAL_PATH)
        except (ValueError,KeyError,TypeError,OSError) as exc:
            raise CommandError(str(exc)) from None
        self.stdout.write(json.dumps({'count':len(rows),'applied':options['apply'],'unchanged':unchanged},ensure_ascii=False))
