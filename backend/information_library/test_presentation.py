"""阅读文案处理不能吞掉具体比赛规则、适用范围和费用。"""
from django.test import SimpleTestCase

from .presentation import reading_text, resource_presentation


class PresentationTests(SimpleTestCase):
    def test_rules_survive_editorial_cleanup_and_mapping(self):
        original = '''审核：草稿，待审核
使用2026年视频，3—6分钟、MP4、700MB以内；不得后期配音。
其他学校校内选拔：2025年9月21日。
字段映射（未知留空）：
{"team_size_min": 2, "team_size_max": 20, "participation_type": "both", "registration_deadline_timezone": "Asia/Shanghai"}
缺口：
附件目录仍需整理。'''
        result = reading_text(original, gaps=['附件目录仍需整理。'])
        self.assertNotIn('待审核', result)
        self.assertNotIn('字段映射', result)
        self.assertIn('不得后期配音', result)
        self.assertIn('2025年9月21日', result)
        self.assertIn('最少人数：2', result)
        self.assertIn('最多人数：20', result)
        self.assertIn('报名时区：Asia/Shanghai', result)

    def test_resources_expose_learning_facts_without_duplicate_intro(self):
        result = resource_presentation('''2026033 机器人大赛
类型：示例代码；难度：入门；访问：免费公开
核验程度：已确认索引或入口，资料正文待核对
适用：2020版开发板C型
用途：学习硬件驱动。
学习硬件驱动。
参赛报名收费500元。''')
        self.assertEqual(result['summary'], '学习硬件驱动。')
        self.assertEqual(result['content'].count('学习硬件驱动。'), 1)
        self.assertEqual(result['facts']['audience'], '2020版开发板C型')
        self.assertEqual(result['facts']['access'], '免费公开')
        self.assertIn('参赛报名收费500元', result['content'])

    def test_unknown_mapping_and_plain_content_are_preserved(self):
        text = '字段映射（未知留空）：\n{"new_field": "重要规则"}'
        self.assertEqual(reading_text(text), text)
        text = '公开资料\n赛道A禁止使用模型生成参赛作品。'
        self.assertEqual(reading_text(text), text)
