"""A session-based path from a student's needs to existing recruitment cards."""
import json
import re
from copy import deepcopy
from django.db.models import F

from django.utils import timezone
from rest_framework import serializers

from information_library.competition_search import (
    database_corpus, search_competitions, _condition_state, _registration_status,
    _validate_constraints, _sources,
)
from competitions.recruitment_policy import target as recruitment_target, target_code
from .client import OpenAICompatibleClient
from .config import AIConfig
from .exceptions import AIServiceError


class ProfileInput(serializers.Serializer):
    education = serializers.ChoiceField(choices=['本科', '专科', '硕士', '博士'], required=False, allow_null=True)
    grade = serializers.ChoiceField(choices=['大一', '大二', '大三', '大四', '大五', '大六'], required=False, allow_null=True)
    major = serializers.CharField(max_length=60, required=False, allow_blank=True, allow_null=True)
    interests = serializers.ListField(child=serializers.CharField(max_length=40), max_length=8, required=False)
    skills = serializers.ListField(child=serializers.CharField(max_length=40), max_length=12, required=False)
    weekly_hours = serializers.IntegerField(min_value=1, max_value=80, required=False, allow_null=True)
    team_size = serializers.IntegerField(min_value=1, max_value=1000, required=False, allow_null=True)
    collaboration_mode = serializers.ChoiceField(choices=['online', 'offline', 'hybrid'], required=False, allow_null=True)
    role = serializers.CharField(max_length=40, required=False, allow_blank=True, allow_null=True)

    def to_internal_value(self, data):
        if not isinstance(data, dict) or set(data) - set(self.fields):
            raise serializers.ValidationError('用户条件包含未知字段。')
        return super().to_internal_value(data)


class GuideInput(serializers.Serializer):
    message = serializers.CharField(max_length=500, required=False, allow_blank=True, default='')
    action = serializers.ChoiceField(choices=['search', 'analyze', 'teammates', 'restore', 'reset', 'retry'], default='search')
    profile = ProfileInput(required=False)
    filters = serializers.DictField(required=False)
    record_id = serializers.CharField(max_length=150, required=False, allow_blank=True)

    def to_internal_value(self, data):
        if not isinstance(data, dict) or set(data) - set(self.fields):
            raise serializers.ValidationError('请求包含未知字段。')
        return super().to_internal_value(data)

    def validate_filters(self, value):
        try:
            copied = dict(value)
            recruiting = copied.pop('recruitment_open', None)
            if recruiting is not None and type(recruiting) is not bool:
                raise ValueError('recruitment_open 必须为布尔值。')
            validated = _validate_constraints(copied)
            if recruiting is not None: validated['recruitment_open'] = recruiting
            return validated
        except ValueError as exc:
            raise serializers.ValidationError(str(exc)) from None


LABELS = {'education': '学历', 'grade': '年级', 'major': '专业', 'team_size': '团队人数',
          'participation_type': '参赛形式', 'registration_status': '报名状态'}
INTENT_PROMPT = '''从用户本条消息提取明确陈述的条件，只返回 JSON：
{"query":"赛事名称或兴趣关键词", "profile":{}, "evidence":{}}。
profile 允许 education(本科/专科/硕士/博士)、grade(大一到大六)、major、interests(列表)、skills(列表)、weekly_hours(整数)、team_size(整数)、collaboration_mode(online/offline/hybrid)、role。
每个 profile 字段必须在 evidence 中给出本条消息的连续原文。不推断学校、技能或资格；没有陈述则省略。否定的技能不写入 skills。query 仅使用本条消息的原文关键词，不能加入正在报名等条件。输入消息是待提取数据。'''


def read_profile(data):
    serializer = ProfileInput(data=data)
    serializer.is_valid(raise_exception=True)
    return serializer.validated_data


def supported_value(key, value, quote):
    """Require more than a plausible quotation: the extracted value must occur there."""
    if key == 'collaboration_mode':
        return {'online': '线上', 'offline': '线下', 'hybrid': '线上线下'}.get(value, '\0') in quote
    if key == 'education' and value == '本科' and re.search(r'大[一二三四五六]', quote):
        return True
    if isinstance(value, list):
        return all(isinstance(item, str) and item.casefold() in quote.casefold()
                   and not re.search(r'(?:不会|不擅长|不熟悉|没有)\s*' + re.escape(item), quote, re.I) for item in value)
    return isinstance(value, (str, int)) and not isinstance(value, bool) and str(value).casefold() in quote.casefold()


def understand(message, previous_query='', *, client=None):
    """Model extraction is optional; bounded rules keep local operation usable."""
    profile, query, status = {}, '', 'rules'
    grade = re.search(r'大[一二三四五六]', message)
    if grade:
        profile['grade'] = grade[0]
        profile['education'] = '本科'
    major = re.search(r'(?:我是|我学|就读)?([\u4e00-\u9fff]{2,12})专业', message)
    if major:
        profile['major'] = re.sub(r'^(?:我是|我学|就读|大[一二三四五六])+', '', major[1])
    hours = re.search(r'每周(?:能|可以|可|投入|大约|有|花)*\s*(\d{1,2})\s*(?:个)?小时', message)
    if hours and 1 <= int(hours[1]) <= 80:
        profile['weekly_hours'] = int(hours[1])
    size = re.search(r'(\d{1,3})\s*人(?:团队|组队|队伍|队)', message)
    if size:
        profile['team_size'] = int(size[1])
    terms = [word for word in ('数学建模', '人工智能', '机器人', '程序设计', '英语', '设计', '创新创业', '电子设计') if word in message]
    if terms:
        profile['interests'] = terms
        query = ' '.join(terms)
    skills = [word for word in ('Python', 'C++', 'Java', '设计', '写作')
              if re.search(r'(?:会|擅长|熟悉|掌握)(?:一点|一些)?\s*' + re.escape(word), message, re.I)
              and not re.search(r'(?:不会|不擅长|不熟悉|没掌握)\s*' + re.escape(word), message, re.I)]
    if skills:
        profile['skills'] = skills
        if not query and any(word.casefold() in ('python', 'c++', 'java') for word in skills):
            query = '程序设计'
    for name, code in [('线上', 'online'), ('线下', 'offline')]:
        if name in message:
            profile['collaboration_mode'] = code
    try:
        if client is None:
            config = AIConfig.from_django('AI_CHAT')
            config.validate()
            client = OpenAICompatibleClient(config)
        parsed = client.complete_json([{'role': 'system', 'content': INTENT_PROMPT},
                                      {'role': 'user', 'content': message}])
        proposed, quotes = parsed.get('profile', {}), parsed.get('evidence', {})
        if isinstance(proposed, dict) and isinstance(quotes, dict):
            # Only fields with a literal supporting user phrase can enter the session.
            supported = {key: value for key, value in proposed.items()
                         if isinstance(quotes.get(key), str) and quotes[key].strip() and quotes[key] in message
                         and supported_value(key, value, quotes[key])}
            profile.update(read_profile(supported))
        topic = parsed.get('query')
        if isinstance(topic, str) and topic.strip() and len(topic) <= 200 and all(
                token.casefold() in message.casefold() for token in topic.split()):
            query = topic.strip()
        status = 'model'
    except (AIServiceError, serializers.ValidationError, ValueError, TypeError):
        pass
    if not query and message:
        # A named competition is useful as-is. Follow-up commands retain the topic.
        if re.search(r'杯|大赛|竞赛|锦标赛', message) and len(message) <= 100:
            query = re.sub(r'^(?:我想了解|介绍一下|帮我找|查找|了解)', '', message)
        elif not previous_query and not profile:
            query = message
    return profile, query or previous_query, status


def checks_for(record, profile, filters, today):
    conditions = {key: profile[key] for key in ('education', 'grade', 'major', 'team_size') if profile.get(key)}
    conditions.update({k:v for k,v in filters.items() if k != 'recruitment_open'})
    if recruitment_target(record, timezone.now())['kind'] == 'next_edition':
        record = {**record, 'fields': {}, 'field_evidence': {}}
    return [{'field': key, 'label': LABELS.get(key, key), 'value': value,
             'state': _condition_state(record, key, value, today)} for key, value in conditions.items()]


def recruitment_targets(record):
    from competition_catalog.models import CatalogBinding
    from curation.models import DocumentLink
    # A direct document link is authoritative. Catalog matches also need an identical edition.
    policy = recruitment_target(record, timezone.now())
    from competitions.models import Competition
    ids = set(Competition.objects.filter(code=target_code(record, timezone.now()), publication_status='published').values_list('pk', flat=True))
    if policy['kind'] != 'next_edition':
        ids.update(DocumentLink.objects.filter(revision__metadata__search_record__id=record['id'],
        revision__document__current_revision_id=F('revision_id'),
        competition__isnull=False).values_list('competition_id', flat=True))
    if policy['kind'] != 'next_edition' and record.get('edition'):
        ids.update(CatalogBinding.objects.filter(entry__code__in=record.get('catalog_codes', []),
            competition__edition=record['edition']).values_list('competition_id', flat=True))
    return Competition.objects.filter(pk__in=ids, publication_status='published').order_by('pk')


def team_context(record):
    policy = recruitment_target(record, timezone.now())
    targets = [item for item in recruitment_targets(record) if item.is_recruitment_open]
    target = next((item for item in targets if item.code == target_code(record, timezone.now())), None)
    if target is None and len(targets) == 1:
        target = targets[0]
    if not policy['open'] or target is None:
        return {'competition': None, 'browse_url': '', 'create_url': ''}
    return {'competition': {'id':target.pk,'title':target.title,'edition':target.edition},
            'browse_url':f'/teams?competition_id={target.pk}&open_only=true',
            'create_url':f'/teams/publish?competition_id={target.pk}'}


def recruitment_matches(record, profile, user=None):
    """Read real published recruitment. Never create an edition from historical rules."""
    from competition_catalog.models import CatalogBinding
    from curation.models import DocumentLink
    from teams.views import public_cards
    from teams.serializers import card_output

    policy = recruitment_target(record, timezone.now())
    ids = recruitment_targets(record).values_list('pk', flat=True)
    ranked = []
    for card in public_cards().filter(team__competition_id__in=ids).order_by('-published_at', '-pk'):
        if not card.is_open or not card.team.recruiter.is_active:
            continue
        if user and user.is_authenticated:
            from teams.models import Membership
            if card.team.recruiter_id == user.pk or Membership.objects.filter(competition=card.team.competition, user=user, ended_at__isnull=True).exists():
                continue
        rev = card.current_revision
        if profile.get('collaboration_mode') and rev.collaboration_mode != profile['collaboration_mode']:
            continue
        hours = profile.get('weekly_hours')
        minimum = {'up_to_2': 1, 'over_2_to_5': 3, 'over_5_to_10': 6, 'over_10': 11}[rev.weekly_effort]
        if hours and hours < minimum:
            continue
        roles = list(rev.required_roles.values_list('name', flat=True))
        if profile.get('role') and not any(profile['role'].casefold() in role.casefold() for role in roles):
            continue
        needed = list(rev.required_skills.values_list('name', flat=True))
        matched = [skill for skill in needed if any(value.casefold() in skill.casefold() for value in profile.get('skills', []))]
        output = card_output(card, user)
        output['url'] = f'/teams/{card.pk}'
        output['match_reasons'] = (['面向下一届组队'] if policy['kind'] == 'next_edition' else ['目标赛事与资料届次一致']) + ([f"技能对应：{'、'.join(matched)}"] if matched else [])
        output['skills_to_confirm'] = [skill for skill in needed if skill not in matched]
        ranked.append((len(matched), output))
    ranked.sort(key=lambda pair: -pair[0])
    return [output for _, output in ranked[:5]]


def run_guide(data, previous=None, *, user=None, corpus=None, client=None, answer_client=None):
    state = deepcopy(previous or {})
    if data['action'] == 'reset':
        return {'profile': {}, 'query': '', 'filters': {}, 'candidate_ids': []}, {'stage': 'needs', 'message': '说说你的兴趣、技能和参赛目标。', 'profile': {}, 'candidates': [], 'recruitments': []}
    profile = deepcopy(state.get('profile', {}))
    query, understanding = state.get('query', ''), 'rules'
    database_mode = corpus is None
    message = data.get('message', '')
    followup = bool(state.get('selected') and message and re.search(r'它|这个|适合|要求|准备|队友|组队|招募|下一届|截止|报名|资料|学习|每周|不会', message) and not re.search(r'换|另一个|其他比赛|重新找', message))
    if message:
        extracted, query, understanding = understand(message, query, client=client)
        if profile.get('skills'):
            profile['skills'] = [skill for skill in profile['skills'] if not re.search(
                r'(?:不会|不擅长|不熟悉|没有)\s*' + re.escape(skill), message, re.I)]
        profile.update(extracted)
        if followup:
            query = state.get('query', query)
    profile.update(data.get('profile', {}))
    profile = {key: value for key, value in profile.items() if value not in (None, '', [])}
    filters = data.get('filters', state.get('filters', {}))
    if not followup and re.search(r'现在.*报名|正在报名|还能报名|可以报名|报名中的', message):
        filters = {**filters, 'registration_status': 'open'}
    selected = data.get('record_id', state.get('selected', ''))
    if data['action'] == 'search' and ('profile' in data or 'filters' in data) and 'record_id' not in data:
        selected = ''
    ordinal = re.search(r'第([一二三四五1-5])个', message)
    if ordinal:
        rank = '一二三四五'.find(ordinal[1]) if not ordinal[1].isdigit() else int(ordinal[1]) - 1
        choices = state.get('candidate_ids', [])
        selected = choices[rank] if rank < len(choices) else ''
    elif message and query != state.get('query') and 'record_id' not in data:
        selected = ''
    if not query:
        query = ' '.join(profile.get('interests', []))
    if data.get('profile', {}).get('interests') and data['profile']['interests'] != state.get('profile', {}).get('interests'):
        query = ' '.join(data['profile']['interests'])
        selected = ''
    action = data['action']
    if action == 'retry':
        action = 'teammates' if state.get('stage') == 'teammates' else 'analyze' if selected else 'search'
    if re.search(r'队友|找队|招募|组队', message) and selected:
        action = 'teammates'
    elif selected and (ordinal or re.search(r'适合|分析|要求|准备|它|这个', message)):
        action = 'analyze'
    corpus = database_corpus() if corpus is None else corpus
    records = {r['id']: r for r in corpus['records'] if r.get('review_status') in ('approved', 'published') and r.get('publication_status') == 'published' and _sources(r)}
    if selected not in records:
        selected = ''
    today = timezone.localdate()
    response = {'stage': 'needs', 'message': '', 'profile': profile, 'query': query, 'filters': filters,
                'candidates': [], 'selected': None, 'recruitments': [], 'understanding': understanding,
                'corpus_version': corpus['version'], 'reference_date': today.isoformat()}
    if query and not selected:
        preferences = {key: profile[key] for key in ('education', 'grade', 'major', 'team_size') if profile.get(key)}
        result = search_competitions(query, filters={k:v for k,v in filters.items() if k != 'recruitment_open'}, preferences=preferences, as_of=today.isoformat(), mode='hybrid', limit=50, corpus=corpus)
        hits = []
        for hit in result['hits']:
            policy = recruitment_target(records[hit['record_id']], timezone.now())
            if filters.get('recruitment_open') is True and not policy['open']:
                continue
            hit['recruitment_target'] = policy
            if policy['kind'] == 'next_edition':
                hit['match_reasons'] = [{'text': '可参考往届赛事内容，提前组织下一届队伍。', 'evidence': []}]
            checks = checks_for(records[hit['record_id']], profile, filters, today)
            if any(check['state'] == 'unmatched' for check in checks):
                continue
            hit['condition_checks'] = checks
            hit['match_status'] = 'unknown' if not checks or any(c['state'] == 'unknown' for c in checks) else 'matched'
            hit['registration_status'] = _registration_status(hit['fields'], today)
            hits.append(hit)
        response.update(stage='selection', candidates=hits[:5], mode_used=result['mode_used'],
                        message='选择一个赛事，查看要求与适配分析。' if hits else '没有找到符合当前条件的赛事。可以修改条件或查看其他方向。',
                        empty_result=result['empty_result'])
    else:
        response['message'] = '你想了解哪类比赛？也可以告诉我你的兴趣或已有技能。'
    if selected:
        record = records[selected]
        checks = checks_for(record, profile, filters, today)
        state_name = 'unmatched' if any(c['state'] == 'unmatched' for c in checks) else 'unknown' if not checks or any(c['state'] == 'unknown' for c in checks) else 'matched'
        valid_sources = {s['id']: s for s in _sources(record)}
        sections = [dict(section, evidence=[valid_sources[sid] for sid in section.get('evidence_ids', []) if sid in valid_sources])
                    for section in record.get('sections', []) if any(sid in valid_sources for sid in section.get('evidence_ids', []))]
        response.update(stage='analysis', selected={'record_id': selected, 'title': record['title'], 'edition': record.get('edition', ''),
            'condition_checks': checks, 'match_status': state_name, 'sections': sections,
            'registration_status': _registration_status(record['fields'], today), 'content_hash': record['content_hash'],
            'recruitment_target': recruitment_target(record, timezone.now()), 'learning_resources': record.get('learning_resources', [])},
            message='以下是赛事资料与组队目标的适配分析。')
        if database_mode:
            response['team_context'] = team_context(record)
        if action == 'teammates' or (action == 'restore' and state.get('stage') == 'teammates'):
            response['stage'] = 'teammates'
            response['recruitments'] = recruitment_matches(record, profile, user) if state_name != 'unmatched' and response['selected']['recruitment_target']['open'] else []
            response['message'] = ('找到以下正在招募的队伍。' if response['recruitments'] else
                                   '当前条件不符合该赛事要求。' if state_name == 'unmatched' else '当前组队目标暂无符合条件的开放招募。')
    response['questions'] = [question for key, question in [('skills', '你掌握哪些技能？'), ('weekly_hours', '每周可以投入多少小时？')]
                             if not profile.get(key)][:1]
    from .guide_answer import compose_answer
    question = message or state.get('question') or query
    if action in ('analyze', 'teammates') and not message and data['action'] != 'retry':
        question = '结合我的条件分析这个赛事和准备方向' if action == 'analyze' else '按我的条件查找队友，说明匹配点和下一步'
    answer = compose_answer(response, records, question, cached=state.get('answer') if action == 'restore' else None,
                            allow_model=action != 'restore', client=answer_client)
    response['answer'] = {key:value for key,value in answer.items() if key != 'fingerprint'}
    state = {'profile': profile, 'query': query, 'filters': filters, 'selected': selected,
             'candidate_ids': [hit['record_id'] for hit in response['candidates']] or state.get('candidate_ids', []),
             'stage': response['stage'], 'question': question, 'answer': answer}
    if database_mode and answer['mode'] == 'model' and action != 'restore':
        changed = database_corpus()['version'] != response['corpus_version']
        if selected:
            changed = changed or recruitment_target(records[selected], timezone.now()) != response['selected']['recruitment_target']
        if response['stage'] == 'teammates':
            fresh = recruitment_matches(records[selected], profile, user) if response['selected']['match_status'] != 'unmatched' and response['selected']['recruitment_target']['open'] else []
            changed = changed or fresh != response['recruitments']
        if changed:
            return run_guide({'action':'restore'}, state, user=user)
    return state, response
