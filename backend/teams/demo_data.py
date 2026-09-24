"""第二轮虚构数据装配；仅由 DEBUG 管理命令调用，不是业务写入服务。"""
from datetime import timedelta
import json

from django.contrib.auth import get_user_model
from django.core.management.base import CommandError
from django.core.serializers.json import DjangoJSONEncoder
from common.snapshots import PUBLIC_SNAPSHOT_KEYS

from accounts.models import UserRestriction
from competitions.models import Competition, CompetitionSource, CompetitionTaxonomy
from favorites.models import Favorite
from governance.models import AdminAction
from ingestion.models import AICall, FetchRun, ProcessingInput, ProcessingResult, SourceConfig, SourceVersion
from ingestion.validation import source_hash
from newsletters.models import Newsletter, NewsletterRevision, NewsletterItem
from notifications.models import BusinessEvent, Notification
from research.models import ResearchOpportunity, ResearchSource, ResearchRevision, ResearchTaxonomy, ResearchTag, ResearchDirection
from resources.models import Resource, ResourceTaxonomy, ResourceRevision, ResourceTag, ResourceDirection, ResourceCompetition, ResourceResearchOpportunity
from .models import (Team, Recruitment, RecruitmentRevision, RecruitmentBaselineMember,
                     RecruitmentOption, RecruitmentCurrentSkill, RecruitmentRequiredRole,
                     RecruitmentRequiredSkill, RecruitmentCampus, Application,
                     ApplicationRevision, ApplicationDesiredRole, ApplicationSkill,
                     Membership, DepartureRequest, DissolutionRequest, DissolutionResponse)


MARKER='【虚构样例】'
PREFIX='demo-r2-'
SOURCE_CODE=PREFIX+'source'


def saved(obj):
    obj.full_clean()
    obj.save()
    return obj


def public_snapshot(obj):
    result={f.name:getattr(obj,f.attname) for f in obj._meta.concrete_fields if f.name in PUBLIC_SNAPSHOT_KEYS}
    if obj.category_id:
        result['category']={'code':obj.category.code,'name':obj.category.name}
    for name in ['tags','directions']:
        result[name]=list(getattr(obj,name).order_by('code').values('code','name'))
    for name in ['competitions','research_opportunities']:
        if hasattr(obj,name):result[name]=list(getattr(obj,name).order_by('code').values_list('code',flat=True))
    return json.loads(json.dumps(result,cls=DjangoJSONEncoder,ensure_ascii=False))


class DemoBuilder:
    def __init__(self, now):
        self.now=now
        self.start=now-timedelta(days=2)

    def build(self):
        self.users=[]
        for number in range(1,13):
            email=f'cxdemo-r2-{number:03d}@tongji.edu.cn'
            if get_user_model().objects.filter(email=email).exists():
                raise CommandError('第二轮样例邮箱已占用，整批回滚；不覆盖原记录。')
            self.users.append(get_user_model().objects.create_user(email,password=None,is_active=False))
        self.owner,self.member,self.waiting,self.withdrawn,self.departed,self.pending=self.users[:6]
        self.actor=self.users[9]
        self.source=saved(SourceConfig(code=SOURCE_CODE,name=MARKER+'离线模拟官方来源',base_url='https://example.org/demo-r2/',content_kind='mixed',adapter_key='demo_disabled',maintained_by=self.actor,is_active=False))
        self.build_content()
        self.build_teams()
        self.build_newsletter()
        self.build_governance()
        self.build_ingestion()

    def build_content(self):
        category=saved(CompetitionTaxonomy(code=PREFIX+'category',kind='category',name=MARKER+'组队情景赛事'))
        self.competition=saved(Competition(code=PREFIX+'edition',title=MARKER+'跨学科创意挑战',edition='演示届次',summary='第二轮关系数据样例',description='完全虚构，仅用于本地数据库和接口开发。',category=category,participation_type='team',team_size_max=8,last_verified_at=self.now))
        saved(CompetitionSource(competition=self.competition,source_type='official',source_name=MARKER+'来源',source_url='https://example.org/demo-r2/competition',is_primary=True,last_verified_at=self.now))
        self.competition.publication_status='published';self.competition.published_at=self.start
        self.competition.recruitment_enabled=True;self.competition.recruitment_deadline=self.now+timedelta(days=20);self.competition.recruitment_note='虚构招募期限'
        saved(self.competition)
        research_options={kind:saved(ResearchTaxonomy(code=PREFIX+'research-'+kind,kind=kind,name=MARKER+'科研'+kind)) for kind in ['category','tag','direction']}
        self.research=[]
        for number,status in enumerate(['published','published','draft','withdrawn'],1):
            data=dict(code=PREFIX+f'research-{number}',title=MARKER+f'科研招募 {number}',description='可以直接保留非结构化的导师招募原文。',recruiting_entity=MARKER+'课题组',official_url=f'https://example.org/demo-r2/research/{number}',publication_status=status,created_by=self.actor,updated_by=self.actor)
            if status!='draft':data['published_at']=self.now-timedelta(days=40 if number==1 else 2)
            if number==2:data.update(deadline_mode='fixed',deadline_on=(self.now-timedelta(days=1)).date())
            if status=='withdrawn':data['withdrawal_reason']='虚构下架情景'
            obj=saved(ResearchOpportunity(**data));self.research.append(obj)
        # 第一条保持最少必填；补充分类、来源及多选放在第二条。
        obj=self.research[1];obj.category=research_options['category'];saved(obj)
        saved(ResearchTag(opportunity=obj,taxonomy=research_options['tag']))
        saved(ResearchDirection(opportunity=obj,taxonomy=research_options['direction']))
        saved(ResearchSource(opportunity=obj,source_url='https://example.org/demo-r2/research/supplement',source_type='campus'))
        for obj in self.research:
            snapshot=public_snapshot(obj)
            snapshot['sources']=list(ResearchSource.objects.filter(opportunity=obj).values('source_url','source_name','source_type'))
            saved(ResearchRevision(opportunity=obj,version=1,snapshot=snapshot,created_by=self.actor))
        resource_options={kind:saved(ResourceTaxonomy(code=PREFIX+'resource-'+kind,kind=kind,name=MARKER+'资源'+kind)) for kind in ['category','tag','direction']}
        self.resources=[]
        for number,status in enumerate(['published','published','draft','withdrawn'],1):
            obj=Resource(code=PREFIX+f'resource-{number}',title=MARKER+f'外链资源 {number}',description='虚构教程与资料介绍，不托管文件。',category=resource_options['category'],access_url=f'https://example.org/demo-r2/resource/{number}',publication_status=status,created_by=self.actor,updated_by=self.actor)
            if status!='draft':obj.published_at=self.start
            if number==2:obj.availability='unavailable'
            if status=='withdrawn':obj.withdrawal_reason='虚构下架情景'
            saved(obj);self.resources.append(obj)
        saved(ResourceTag(resource=self.resources[0],taxonomy=resource_options['tag']))
        saved(ResourceDirection(resource=self.resources[0],taxonomy=resource_options['direction']))
        saved(ResourceCompetition(resource=self.resources[0],competition=self.competition))
        saved(ResourceResearchOpportunity(resource=self.resources[0],opportunity=self.research[0]))
        for obj in self.resources:
            saved(ResourceRevision(resource=obj,version=1,snapshot=public_snapshot(obj),created_by=self.actor))
        saved(Favorite(user=self.waiting,competition=self.competition))
        saved(Favorite(user=self.waiting,research=self.research[0]))
        saved(Favorite(user=self.waiting,resource=self.resources[3]))

    def make_team(self, number, owner):
        team=saved(Team(code=PREFIX+f'team-{number}',competition=self.competition,recruiter=owner,created_at=self.start))
        member=saved(Membership(team=team,competition=self.competition,user=owner,join_source='recruiter',joined_at=self.start))
        card=saved(Recruitment(code=PREFIX+f'card-{number}',team=team,duration_days=7,created_at=self.start))
        rev=self.card_revision(card,member,1)
        card.current_revision=rev;card.publication_status='published';card.published_at=self.start;card.expires_at=self.start+timedelta(days=7);saved(card)
        return team,member,card

    def card_revision(self, card, owner_member, version):
        rev=saved(RecruitmentRevision(recruitment=card,version=version,existing_member_count=1,recruitment_quota=3,foundation_requirement='beginner_ok',weekly_effort='over_2_to_5' if version==1 else 'over_5_to_10',collaboration_mode='hybrid',edited_by=card.team.recruiter,created_at=self.start if version==1 else self.now))
        saved(RecruitmentBaselineMember(revision=rev,membership=owner_member))
        saved(RecruitmentCurrentSkill(revision=rev,option=self.skill))
        saved(RecruitmentRequiredRole(revision=rev,option=self.role))
        saved(RecruitmentRequiredSkill(revision=rev,option=self.skill))
        saved(RecruitmentCampus(revision=rev,option=self.campus))
        return rev

    def make_application(self,card,user,outcome='pending',with_role=False):
        moment=self.start+timedelta(hours=8)
        obj=saved(Application(recruitment=card,applicant=user,submitted_at=moment))
        rev=saved(ApplicationRevision(application=obj,version=1,recruitment_revision=card.current_revision,weekly_effort='over_2_to_5',created_by=user,accepted_at=moment))
        if with_role:saved(ApplicationDesiredRole(revision=rev,option=self.role))
        saved(ApplicationSkill(revision=rev,option=self.skill))
        obj.current_revision=rev
        if outcome in ['contact_open','joined']:obj.contact_opened_at=moment+timedelta(minutes=1)
        if outcome=='joined':
            obj.applicant_confirmed_at=obj.recruiter_confirmed_at=moment+timedelta(hours=1)
            obj.applicant_confirmed_revision=obj.recruiter_confirmed_revision=rev
        if outcome in ['joined','withdrawn','rejected']:
            obj.end_reason=outcome;obj.resolved_at=moment+timedelta(hours=1)
        obj.status=outcome;saved(obj)
        if outcome=='joined':
            saved(Membership(team=card.team,competition=self.competition,user=user,join_source='application',application=obj,joined_at=obj.resolved_at))
        return obj

    def event(self,kind,target_field,target,recipients,payload=None):
        event=saved(BusinessEvent(kind=kind,actor=self.actor,payload=payload or {},**{target_field:target}))
        for user in {u.pk:u for u in recipients}.values():
            saved(Notification(event=event,recipient=user,title=MARKER+'系统通知',body=MARKER+f'演示事件：{kind}。查看详情时需要重新检查访问权限。'))
        return event

    def build_teams(self):
        self.role=saved(RecruitmentOption(code=PREFIX+'role',kind='role',name=MARKER+'编程'))
        self.skill=saved(RecruitmentOption(code=PREFIX+'skill',kind='skill',name=MARKER+'数据整理'))
        self.campus=saved(RecruitmentOption(code=PREFIX+'campus',kind='campus',name=MARKER+'演示校区'))
        self.team,self.owner_member,self.card=self.make_team(1,self.owner)
        self.make_application(self.card,self.member,'joined',with_role=True)
        self.make_application(self.card,self.waiting,'contact_open')
        self.make_application(self.card,self.withdrawn,'withdrawn')
        exited=self.make_application(self.card,self.departed,'joined')
        self.make_application(self.card,self.pending)
        member=Membership.objects.get(application=exited)
        created=self.now-timedelta(hours=25)
        req=saved(DepartureRequest(membership=member,kind='exit',initiator=self.departed,responder=self.owner,created_at=created,deadline_at=created+timedelta(hours=24),status='timed_out',resolved_at=created+timedelta(hours=24)))
        member.ended_at=req.resolved_at;member.end_reason='exit';saved(member)
        self.event('departure_completed','departure_request',req,[self.departed,self.owner],{'reason':'timed_out'})
        current=Membership.objects.get(user=self.member,team=self.team)
        req=saved(DepartureRequest(membership=current,kind='removal',initiator=self.owner,responder=self.member,created_at=self.now,deadline_at=self.now+timedelta(hours=24)))
        self.event('departure_requested','departure_request',req,[self.member])
        revision=self.card_revision(self.card,self.owner_member,2)
        self.card.current_revision=revision;self.card.last_edited_at=self.now;saved(self.card)
        self.event('recruitment_edited','recruitment',self.card,[self.owner,self.member,self.waiting,self.pending],{'from_version':1,'to_version':2,'changed_fields':['weekly_effort']})
        owner,other=self.users[6:8]
        team,owner_member,card=self.make_team(2,owner)
        app=self.make_application(card,other,'joined')
        req=saved(DissolutionRequest(team=team,initiator=owner,created_at=self.now,deadline_at=self.now+timedelta(hours=24)))
        saved(DissolutionResponse(request=req,membership=Membership.objects.get(application=app)))
        self.event('dissolution_requested','dissolution_request',req,[other])
        owner=self.users[8]
        team,owner_member,card=self.make_team(3,owner)
        req=saved(DissolutionRequest(team=team,initiator=owner,created_at=self.now,deadline_at=self.now+timedelta(hours=24),status='completed',completion_reason='no_other_members',resolved_at=self.now))
        owner_member.ended_at=self.now;owner_member.end_reason='dissolution';saved(owner_member)
        card.closed_at=self.now;card.close_reason='team_dissolved';saved(card)
        team.dissolved_at=self.now;saved(team)
        self.event('dissolution_completed','dissolution_request',req,[owner],{'reason':'no_other_members'})

    def build_newsletter(self):
        self.newsletter=saved(Newsletter(code=PREFIX+'newsletter',created_by=self.actor))
        rev=saved(NewsletterRevision(newsletter=self.newsletter,version=1,title=MARKER+'本期快讯',created_by=self.actor,updated_by=self.actor))
        for index,(kind,target) in enumerate([('competition',self.competition),('research',self.research[1]),('resource',self.resources[0]),('activity',None)],1):
            data=dict(revision=rev,position=index,kind=kind,title_snapshot=MARKER+'当期标题',summary_snapshot='完全虚构的当期摘要',source_url=f'https://example.org/demo-r2/news/{index}')
            if target:data[kind]=target
            if kind=='competition':data['source_updated_at']=target.updated_at
            if kind in ['research','resource']:data['source_version']=target.content_version
            if kind=='activity':data['activity_time_text']='时间待公布'
            saved(NewsletterItem(**data))
        rev.status='confirmed';rev.confirmed_at=self.now;rev.confirmed_by=self.actor;saved(rev)
        self.newsletter.current_revision=rev;self.newsletter.publication_status='published';self.newsletter.published_at=self.now;saved(self.newsletter)
        self.draft=saved(NewsletterRevision(newsletter=self.newsletter,version=2,title=MARKER+'待审核修订',created_by=self.actor,updated_by=self.actor))

    def build_governance(self):
        restriction=saved(UserRestriction(user=self.withdrawn,reason=MARKER+'演示 24 小时发布/申请限制',created_by=self.actor,starts_at=self.now,expires_at=self.now+timedelta(hours=24)))
        action=saved(AdminAction(action='restrict',target_user=self.withdrawn,restriction=restriction,actor=self.actor,reason=MARKER+'演示处理'))
        self.event('admin_action','admin_action',action,[self.withdrawn])

    def build_ingestion(self):
        run=saved(FetchRun(source=self.source,requested_url='https://example.org/demo-r2/research-source',trigger='manual',triggered_by=self.actor,started_at=self.now,finished_at=self.now+timedelta(seconds=1),status='succeeded',http_status=200))
        source=SourceVersion(source=self.source,first_fetch=run,source_url=run.requested_url,title=self.research[0].title,body_text=MARKER+'手工构造的原文，没有进行网络抓取。',first_seen_at=self.now,last_seen_at=self.now)
        source.content_hash=source_hash(source);saved(source)
        saved(FetchRun(source=self.source,requested_url=run.requested_url,trigger='scheduled',started_at=self.now,finished_at=self.now+timedelta(seconds=1),status='unchanged',http_status=200))
        call=saved(AICall(provider='demo',model_name='fictional-offline',prompt_version='demo-r2',started_at=self.now,finished_at=self.now+timedelta(seconds=1),duration_ms=1000,status='succeeded'))
        saved(ProcessingResult(task_type='research_extract',source_version=source,ai_call=call,candidate={'title':self.research[0].title},evidence={'title':source.title},status='accepted',decision_mode='human',reviewed_by=self.actor,reviewed_at=self.now,research=self.research[0]))
        result=saved(ProcessingResult(task_type='newsletter_draft',candidate={'title':MARKER+'待生成草稿'}))
        for index,(kind,target) in enumerate([('competition',self.competition),('research',self.research[1]),('resource',self.resources[0])],1):
            saved(ProcessingInput(result=result,position=index,snapshot={'title':target.title,'body':target.description,'source_url':f'https://example.org/demo-r2/input/{index}'},**{kind:target}))
