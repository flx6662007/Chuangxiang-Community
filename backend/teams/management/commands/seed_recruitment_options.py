from django.core.management.base import BaseCommand
from django.db import transaction
from teams.models import RecruitmentOption
from teams.services import save


OPTIONS = {
    'role': [('development', '程序开发'), ('algorithm', '算法实现'), ('hardware', '硬件设计'),
             ('design', '界面与视觉设计'), ('research', '调研分析'), ('writing', '文案与报告'), ('presentation', '展示答辩')],
    'skill': [('python', 'Python'), ('cpp', 'C++'), ('javascript', 'JavaScript'), ('django', 'Django'),
              ('vue', 'Vue'), ('data-analysis', '数据分析'), ('machine-learning', '机器学习'), ('embedded', '嵌入式开发'),
              ('cad', 'CAD'), ('visual-design', '视觉设计'), ('academic-writing', '学术写作')],
    'campus': [('siping', '四平路校区'), ('jiading', '嘉定校区'), ('huxi', '沪西校区'), ('hubei', '沪北校区')],
}


class Command(BaseCommand):
    help = '补充通用招募词表；只新增缺失 code，不改名称、不重新启用已停用词条。'

    @transaction.atomic
    def handle(self, *args, **options):
        added = 0
        for kind, entries in OPTIONS.items():
            for index, (code, name) in enumerate(entries):
                stable_code = f'{kind}-{code}'
                if RecruitmentOption.objects.filter(code=stable_code).exists():
                    continue
                # 团队既有同用途同名词条沿用原 code，避免创建重复字典。
                if RecruitmentOption.objects.filter(kind=kind, name=name).exists():
                    continue
                save(RecruitmentOption(code=stable_code, kind=kind, name=name, sort_order=index))
                added += 1
        self.stdout.write(self.style.SUCCESS(f'新增 {added} 个词条；既有及停用词条保持不变。'))
