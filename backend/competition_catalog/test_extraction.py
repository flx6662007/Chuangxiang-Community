"""Pure tests: no database, network, real accounts or local snapshots required."""

from datetime import date
import unittest

from competition_catalog.extraction import extract_notice


TODAY = date(2026, 9, 29)


def notice(title='关于举办2026年全国大学生智能工程竞赛的通知', body=None, **overrides):
    row = {
        'id': 1, 'entry_code': '2026001', 'entry_name': '全国大学生智能工程竞赛',
        'aliases': [], 'title': title, 'page_kind': 'notice', 'published_on': '2026-09-20',
        'body': body or '\n'.join([
            '一、组织机构', '主办单位：中国工程学会', '二、参赛对象',
            '参赛学生为全国普通高校在校本科生、研究生。', '三、参赛团队',
            '每个参赛团队的学生人数不超过三人，每支团队可设置两名指导教师。',
            '四、报名时间', '报名时间：2026年9月1日至10月15日。',
            '五、报名流程', '参赛团队通过https://www.ccf.org.cn/报名。',
            '六、比赛时间', '比赛时间：2026年11月30日。',
        ]),
    }
    row.update(overrides)
    return row


class ExtractionTests(unittest.TestCase):
    def extract(self, row):
        return extract_notice(row, today=TODAY)

    def test_complete_notice_uses_range_end_not_event_date(self):
        result = self.extract(notice())
        self.assertEqual(result['disposition'], 'ready')
        self.assertEqual(result['candidate']['registration_deadline'], '2026-10-15')
        self.assertEqual(result['candidate']['team_size_max'], 3)
        self.assertIsNone(result['candidate']['team_size_min'])

    def test_guidance_teachers_are_not_student_count(self):
        row = notice()
        row['body'] = row['body'].replace('每个参赛团队的学生人数不超过三人，每支团队可设置两名指导教师。', '每支团队最多两名指导教师。')
        result = self.extract(row)
        self.assertIsNone(result['candidate']['team_size_max'])

    def test_same_actual_event_has_stable_code_across_notice_wrappers(self):
        first = self.extract(notice())
        second = self.extract(notice('2026年全国大学生智能工程竞赛参赛说明'))
        self.assertEqual(first['candidate']['code'], second['candidate']['code'])
        track = self.extract(notice('2026年全国大学生智能工程竞赛机器视觉专项赛报名通知'))
        self.assertNotEqual(first['candidate']['code'], track['candidate']['code'])

    def test_news_results_and_unrelated_catalog_are_not_signup(self):
        for title in ('2026年全国大学生智能工程竞赛获奖名单', '2026年全国大学生智能工程竞赛圆满落幕'):
            self.assertEqual(self.extract(notice(title))['disposition'], 'irrelevant')
        row = notice(entry_name='中国青年科技创新“揭榜挂帅”擂台赛')
        row['body'] += '\n另设中国青年科技创新“揭榜挂帅”擂台赛专项赛。'
        self.assertEqual(self.extract(row)['disposition'], 'irrelevant')

    def test_unknown_year_not_filled_from_publication_or_fetch_date(self):
        row = notice('关于举办第十五届全国大学生智能工程竞赛的通知')
        row['body'] = row['body'].replace('2026年', '')
        row['last_seen_at'] = '2026-09-29T12:00:00+08:00'
        result = self.extract(row)
        self.assertEqual(result['disposition'], 'review')
        self.assertEqual(result['candidate']['edition'], '')
        self.assertIsNone(result['candidate']['registration_deadline'])

    def test_explicit_opening_edition_is_usable_but_tail_is_not(self):
        row = notice('关于举办第十五届全国大学生智能工程竞赛的通知')
        row['body'] = '现决定于2026年举办全国大学生智能工程竞赛。\n' + row['body']
        self.assertEqual(self.extract(row)['candidate']['edition'], '2026')
        row['body'] = row['body'].split('\n', 1)[1] + '\n热门动态\n现决定于2027年举办全国大学生智能工程竞赛。'
        self.assertEqual(self.extract(row)['candidate']['edition'], '')

    def test_registration_start_and_end_same_sentence(self):
        row = notice()
        row['body'] = row['body'].replace('报名时间：2026年9月1日至10月15日。', '报名于2026年9月1日开始，报名截止：2026年10月15日。')
        self.assertEqual(self.extract(row)['candidate']['registration_deadline'], '2026-10-15')

    def test_start_alone_and_competition_date_are_not_deadlines(self):
        row = notice()
        row['body'] = row['body'].replace('报名时间：2026年9月1日至10月15日。', '2026年9月1日起开始报名。')
        result = self.extract(row)
        self.assertIsNone(result['candidate']['registration_deadline'])
        self.assertEqual(result['disposition'], 'review')

    def test_ambiguous_extensions_require_review(self):
        row = notice()
        row['body'] = row['body'].replace('报名时间：2026年9月1日至10月15日。', '报名截止由2026年9月30日延期至2026年10月15日。')
        result = self.extract(row)
        self.assertEqual(result['disposition'], 'review')
        self.assertTrue(any('延期' in message for message in result['errors']))

    def test_stage_or_domestic_foreign_deadlines_conflict(self):
        row = notice()
        row['body'] += '\n境内车队报名截止时间：2026年3月8日13：30\n境外车队报名截止时间：2026年4月30日'
        result = self.extract(row)
        self.assertIsNone(result['candidate']['registration_deadline'])
        self.assertEqual(result['disposition'], 'review')

    def test_removing_email_never_hides_second_deadline(self):
        row = notice()
        row['body'] += '\n作品赛参赛者发送至邮箱private@school.edu.cn，报名截止时间：2026年10月20日。'
        result = self.extract(row)
        self.assertEqual(result['disposition'], 'review')
        self.assertIsNone(result['candidate']['registration_deadline'])
        self.assertNotIn('private@', str(result['candidate']))

    def test_joint_registration_submission_heading(self):
        row = notice()
        row['body'] = row['body'].replace('四、报名时间\n报名时间：2026年9月1日至10月15日。', '四、赛程安排\n（一）报名及作品提交\n赛程时间：截至2026年10月23日23:59:59\n（二）校级初赛\n赛程时间：2026年10月24日—10月28日')
        result = self.extract(row)
        self.assertEqual(result['candidate']['registration_deadline'], '2026-10-23')
        self.assertEqual(result['candidate']['submission_deadline'], '2026-10-23')
        self.assertNotIn('registration_deadline_at', result['candidate'])
        self.assertIn('23:59:59', result['candidate']['deadline_notes'])

    def test_submission_does_not_reopen_registration(self):
        row = notice()
        row['body'] = row['body'].replace('10月15日', '9月28日') + '\n作品提交截止时间：2026年10月30日'
        result = self.extract(row)
        self.assertEqual(result['disposition'], 'historical')

    def test_date_only_today_remains_current(self):
        row = notice()
        row['body'] = row['body'].replace('10月15日', '9月29日')
        self.assertEqual(self.extract(row)['disposition'], 'ready')

    def test_no_registration_date_can_use_explicit_submission_date(self):
        row = notice()
        row['body'] = row['body'].replace('报名时间：2026年9月1日至10月15日。', '作品提交截止：2026年10月15日。')
        result = self.extract(row)
        self.assertIsNone(result['candidate']['registration_deadline'])
        self.assertEqual(result['candidate']['submission_deadline'], '2026-10-15')
        self.assertEqual(result['disposition'], 'ready')

    def test_open_registration_then_submission_is_not_registration_deadline(self):
        row = notice()
        row['body'] = row['body'].replace('报名时间：2026年9月1日至10月15日。', '即日起开放报名，参赛团队需于2026年10月28日前提交全部参赛文件。')
        result = self.extract(row)
        self.assertIsNone(result['candidate']['registration_deadline'])
        self.assertEqual(result['candidate']['submission_deadline'], '2026-10-28')

    def test_month_only_range_start_still_gets_actual_end(self):
        row = notice()
        row['body'] = row['body'].replace('报名时间：2026年9月1日至10月15日。', '（一）大赛报名（2026年4月-7月31日）')
        result = self.extract(row)
        self.assertEqual(result['candidate']['registration_deadline'], '2026-07-31')
        self.assertEqual(result['disposition'], 'historical')

    def test_source_evidence_lines_are_verbatim_and_contacts_removed(self):
        row = notice()
        row['body'] += '\n七、联系方式\n联系人：测试老师\n手机号码：13800000000\n邮箱：private@school.edu.cn'
        result = self.extract(row)
        source = re_compact(row['title'] + '\n' + row['body'])
        for field, value in result['evidence'].items():
            for line in value.splitlines():
                self.assertIn(re_compact(line), source, field)
        public = str(result['candidate'])
        self.assertNotIn('13800000000', public)
        self.assertNotIn('private@school.edu.cn', public)
        self.assertNotIn('测试老师', public)

    def test_homepage_does_not_borrow_embedded_notice(self):
        row = notice('2026年全国大学生智能工程竞赛', page_kind='index')
        self.assertEqual(self.extract(row)['disposition'], 'irrelevant')

    def test_article_marked_index_with_explicit_notice_still_works(self):
        self.assertEqual(self.extract(notice(page_kind='index'))['disposition'], 'ready')

    def test_ccsp_dedicated_alias_and_footer_years(self):
        row = notice('2026 CCF CCSP竞赛将于10月21~22日举办，9月9日开启报名 - 通知公告 - 中国计算机学会', entry_name='CCF大学生计算机系统与程序设计竞赛（CCSP）', aliases=['CCSP'])
        row['body'] = '\n'.join([
            '首页', '联系我们', row['title'].split(' - ')[0], '2026-09-09',
            '2026 CCF CCSP竞赛将于10月21~22日在四川成都举办，报名时间为2026年9月9日-10月11日。',
            '一、组织机构', '主办单位：中国计算机学会', '二、参赛资格',
            '面向全国高校在校生，以CSP成绩200分及以上为依据。',
            '三、报名流程', '团报类型：由学校统一缴费。', '个人类型：提交报名信息。',
            '热门动态', '2027年12月30日报名截止',
        ])
        result = self.extract(row)
        self.assertEqual(result['disposition'], 'ready')
        self.assertEqual(result['candidate']['registration_deadline'], '2026-10-11')
        self.assertEqual(result['candidate']['participation_type'], 'unknown')

    def test_related_attachment_retains_notice_identity(self):
        row = notice('竞赛细则.pdf')
        row['body'] = '关联通知：关于举办2026年全国大学生智能工程竞赛的通知\n关联通知地址：https://www.ccf.org.cn/notice\n以下为附件正文：\n2026年全国大学生智能工程竞赛参赛指南\n' + row['body']
        result = self.extract(row)
        self.assertEqual(result['disposition'], 'ready')
        self.assertIn('智能工程竞赛', result['candidate']['title'])

    def test_attachment_other_contest_cannot_inherit_parent_identity(self):
        row = notice('关于举办2026年全国大学生智能工程竞赛的通知 / 2026中国青年科技创新“揭榜挂帅”擂台赛方案.pdf')
        row['body'] = '关联通知：关于举办2026年全国大学生智能工程竞赛的通知\n关联通知地址：https://www.ccf.org.cn/notice\n以下为附件正文：\n2026中国青年科技创新“揭榜挂帅”擂台赛方案\n' + row['body']
        self.assertEqual(self.extract(row)['disposition'], 'irrelevant')

    def test_attachment_without_own_identity_stays_review(self):
        row = notice('竞赛细则.pdf')
        row['body'] = '关联通知：关于举办2026年全国大学生智能工程竞赛的通知\n关联通知地址：https://www.ccf.org.cn/notice\n以下为附件正文：\n' + row['body']
        self.assertEqual(self.extract(row)['disposition'], 'review')

    def test_attachment_conflicting_year_is_not_current(self):
        row = notice('关于举办2026年全国大学生智能工程竞赛的通知 / 2025年全国大学生智能工程竞赛参赛指南.pdf')
        row['body'] = '关联通知：关于举办2026年全国大学生智能工程竞赛的通知\n关联通知地址：https://www.ccf.org.cn/notice\n以下为附件正文：\n2025年全国大学生智能工程竞赛参赛指南\n' + row['body']
        self.assertEqual(self.extract(row)['disposition'], 'review')

    def test_small_group_range_and_teacher_quota(self):
        row = notice()
        row['body'] = row['body'].replace('每个参赛团队的学生人数不超过三人，每支团队可设置两名指导教师。', '所有组别均须以小组形式报名参加方案征集，小组人数限于3-7人（含3人与7人），每个小组须确定1名指导教师。')
        result = self.extract(row)
        self.assertEqual(result['candidate']['participation_type'], 'team')
        self.assertEqual(result['candidate']['team_size_min'], 3)
        self.assertEqual(result['candidate']['team_size_max'], 7)

    def test_awards_word_team_does_not_prove_team_participation(self):
        row = notice()
        row['body'] = row['body'].replace('每个参赛团队的学生人数不超过三人，每支团队可设置两名指导教师。', '为获奖团队颁发证书。')
        self.assertEqual(self.extract(row)['candidate']['participation_type'], 'unknown')

    def test_old_context_does_not_leak_into_other_table_dates(self):
        row = notice()
        row['body'] += '\n2）所有组别均须以小组形式报名参加方案征集\n06\n竞赛参与方式\n小组提交作品后由专家评审\n10月20日-10月28日'
        self.assertEqual(self.extract(row)['candidate']['registration_deadline'], '2026-10-15')

    def test_shared_site_wrong_challenge_cup_catalog_rejected(self):
        title = '挑战杯丨关于举办第十五届“挑战杯”建设银行中国大学生创业计划竞赛的通知'
        row = notice(title, entry_name='中国青年科技创新“揭榜挂帅”擂台赛')
        row['body'] += '\n专项赛事：“揭榜挂帅”专项赛（2026年度中国青年科技创新“揭榜挂帅”擂台赛）。'
        self.assertEqual(self.extract(row)['disposition'], 'irrelevant')

    def test_optional_audience_prefix_keeps_distinctive_identity(self):
        row = notice('2026年第23届信息安全与对抗技术竞赛通知', entry_name='全国大学生信息安全与对抗技术竞赛')
        result = self.extract(row)
        self.assertNotEqual(result['disposition'], 'irrelevant')

    def test_unsafe_registration_links_are_not_public(self):
        for url in ('http://127.0.0.1/secrets', 'https://user:password@ccf.org.cn/', 'http://secret.local/', 'https://sub.example.com/'):
            row = notice()
            row['body'] = row['body'].replace('https://www.ccf.org.cn/', url)
            candidate = self.extract(row)['candidate']
            self.assertEqual(candidate['registration_url'], '')
            self.assertNotIn(url, candidate['description'])

    def test_campus_deadline_is_not_national_registration(self):
        row = notice()
        row['body'] += '\n校内预报名截止：2026年10月5日。'
        # No guessing which applies: a distinct campus deadline requires review.
        self.assertEqual(self.extract(row)['disposition'], 'review')

    def test_conflicting_student_limits_require_review(self):
        row = notice()
        row['body'] += '\n另一赛道每支团队的学生人数不超过五人。'
        result = self.extract(row)
        self.assertEqual(result['disposition'], 'review')
        self.assertIsNone(result['candidate']['team_size_max'])

    def test_decimal_organizer_heading_after_contact_section(self):
        row = notice()
        row['body'] = row['body'].replace('一、组织机构\n主办单位：中国工程学会\n', '')
        row['body'] += '\n7 联系方式\n邮箱：private@school.edu.cn\n8 组织机构\n8.1 主办单位\n北京理工大学\n中国兵工学会\n8.2 承办单位\n某实验中心'
        result = self.extract(row)
        self.assertEqual(result['candidate']['organizer'], '北京理工大学\n中国兵工学会')
        self.assertNotIn('private@', str(result['candidate']))

    def test_updated_notice_same_code_as_earlier_notice(self):
        first = notice('2026年全国大学生智能工程竞赛通知–机器人赛')
        updated = notice('2026年全国大学生智能工程竞赛通知【更新版】–机器人赛')
        self.assertEqual(self.extract(first)['candidate']['code'], self.extract(updated)['candidate']['code'])

    def test_pdf_multiline_title_and_wrapped_deadline_keep_region(self):
        parent = '2026中国机器人大赛暨RoboCup机器人世界杯中国赛（中国机器人大赛赛区）新疆区域赛比赛通知'
        row = notice(parent + ' / 赛事通知·2026新疆区域赛·盖章.pdf', entry_name='中国机器人大赛暨RoboCup机器人世界杯中国赛')
        row['body'] = '\n'.join([
            '关联通知：' + parent, '关联通知地址：https://www.ccf.org.cn/notice', '以下为附件正文：',
            '—1—', '中国自动化学会', '2026 中国机器人大赛暨 RoboCup 机器人世界杯中国赛',
            '（中国机器人大赛赛区）新疆区域赛', '比赛通知', '一、组织机构', '主办单位：中国自动化学会',
            '二、参赛对象', '新疆维吾尔自治区、新疆生产建设兵团各高校研究生、本科生',
            '三、报名时间', '(1) 所有参加校赛队伍均须在报名系统中进行报名，系统报名截止日',
            '期为2026 年7 月30 日24 时；', '四、比赛安排', '比赛时间：2026年9月6日',
        ])
        result = self.extract(row)
        self.assertEqual(result['disposition'], 'historical')
        self.assertIn('新疆区域赛', result['candidate']['title'])
        self.assertIn('新疆维吾尔自治区', result['candidate']['eligibility'])
        self.assertEqual(result['candidate']['registration_deadline'], '2026-07-30')
        self.assertEqual(result['candidate']['level'], 'unknown')
        source = re_compact(row['body'])
        for value in result['evidence'].values():
            for line in value.splitlines():
                self.assertIn(re_compact(line), source)

    def test_contact_section_does_not_resume_at_nested_payment_step(self):
        row = notice()
        row['body'] += '\n七、缴费方式\n1、线上支付\n2、对公转账\n账 号：12345678901234567890\n户 名：测试账户\n八、其他事项\n报名截止时间维持不变。'
        result = self.extract(row)
        self.assertNotIn('12345678901234567890', str(result['candidate']))
        self.assertNotIn('测试账户', str(result['candidate']))

    def test_preregistration_requirements_populated_without_inventing_deadline(self):
        row = notice()
        row['body'] = '\n'.join([
            '8.1 主办单位', '北京理工大学', '8.2 承办单位', '某实验中心',
            '6 预报名要求', '参赛选手为高等学校中有正式学籍的全日制在校学生，以学校为单位组队，每队3人。',
            '同一学校的参赛队伍数量不超过3队。', '7 比赛时间', '具体时间另行通知。',
        ])
        result = self.extract(row)
        self.assertEqual(result['disposition'], 'review')
        self.assertIn('全日制在校学生', result['candidate']['eligibility'])
        self.assertEqual(result['candidate']['team_size_min'], 3)
        self.assertEqual(result['candidate']['team_size_max'], 3)
        self.assertIsNone(result['candidate']['registration_deadline'])

    def test_math_pdf_binds_edition_to_initial_round_not_other_years(self):
        row = notice('关于举办第十八届全国大学生数学竞赛的通知', entry_name='第十八届全国大学生数学竞赛', url='https://www.cms.org.cn/notice.pdf')
        row['body'] = '\n'.join([
            '关于举办第十八届全国大学生数学竞赛的通知',
            '为青年学子搭建展示数学思维能力和学习成果的平台，中国数学会决定举办第',
            '十八届全国大学生数学竞赛。本届竞赛由大连理工大学承办。',
            '目前，该赛事已入选2025—2026年全国青少年科技创新大赛青年组关联赛事名单。',
            '1、参赛对象：', '所有全日制在校大学生。', '2、竞赛时间：',
            '本届竞赛初赛定于2026年11月14日（星期六）上午9：00—11：30举行，',
            '如有变动另行通知；决赛预计于2027年4月在大连理工大学举行。',
            '3、竞赛分类及内容：', '竞赛分为数学专业类、非数学专业类和高职高专类。',
            '4、报名办法', '2026年10月19日前，按所在省、自治区、直辖市数学会的要求报名；',
            '各赛区在2026年10月30日前向中国数学会汇款。',
        ])
        result = self.extract(row)
        self.assertEqual(result['disposition'], 'ready')
        self.assertEqual(result['candidate']['edition'], '2026')
        self.assertEqual(result['candidate']['organizer'], '中国数学会')
        self.assertEqual(result['candidate']['registration_deadline'], '2026-10-19')
        self.assertIn('高职高专类', result['candidate']['tracks'])


def re_compact(value):
    return ''.join(value.split())


if __name__ == '__main__':
    unittest.main()
