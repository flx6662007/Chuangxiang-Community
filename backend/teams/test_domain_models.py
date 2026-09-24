"""业务关键数据形态及实际数据库约束；不把模型测试冒充接口联调。"""
from datetime import timedelta
from unittest import skipUnless

from django.apps import apps
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, transaction
from django.db.models.deletion import ProtectedError
from django.test import TestCase
from django.utils import timezone

from accounts.models import UserRestriction
from competitions.models import Competition, CompetitionSource, CompetitionTaxonomy
from favorites.models import Favorite
from governance.models import AdminAction
from ingestion.models import AICall, FetchRun, ProcessingInput, ProcessingResult, SourceConfig, SourceVersion
from ingestion.validation import source_hash
from newsletters.models import Newsletter, NewsletterItem, NewsletterRevision
from notifications.models import BusinessEvent, Notification
from research.models import ResearchOpportunity, ResearchRevision, ResearchTaxonomy
from resources.models import Resource, ResourceTaxonomy
from .models import (Application, ApplicationRevision, DepartureRequest, DissolutionRequest,
                     DissolutionResponse, Membership, Recruitment, RecruitmentBaselineMember,
                     RecruitmentOption, RecruitmentRequiredRole, RecruitmentRevision, Team,
                     ApplicationDesiredRole, RecruitmentCampus)


def saved(obj):
    obj.full_clean()
    obj.save()
    return obj


class DomainDataTests(TestCase):
    def setUp(self):
        self.now = timezone.now()
        self.owner = get_user_model().objects.create_user('domain-owner@tongji.edu.cn')
        self.student = get_user_model().objects.create_user('domain-student@tongji.edu.cn')
        self.third = get_user_model().objects.create_user('domain-third@tongji.edu.cn')
        cat=CompetitionTaxonomy.objects.create(code='domain-category',kind='category',name='测试分类')
        self.competition=Competition.objects.create(code='domain-event',title='测试赛事',edition='测试届次',category=cat,summary='简介',description='说明',last_verified_at=self.now)
        CompetitionSource.objects.create(competition=self.competition,source_type='official',source_name='虚构来源',source_url='https://example.org/competition',is_primary=True,last_verified_at=self.now)
        self.competition.publication_status='published'
        self.competition.published_at=self.now
        self.competition.recruitment_enabled=True
        self.competition.participation_type='team'
        self.competition.recruitment_deadline=self.now+timedelta(days=30)
        self.competition.recruitment_note='测试招募期限'
        saved(self.competition)
        self.team=saved(Team(competition=self.competition,recruiter=self.owner))
        self.owner_member=saved(Membership(team=self.team,competition=self.competition,user=self.owner,join_source='recruiter'))
        self.card=saved(Recruitment(team=self.team,duration_days=7))
        self.revision=self.new_card_revision()
        self.card.current_revision=self.revision
        self.card.publication_status='published'
        self.card.published_at=self.now
        self.card.expires_at=self.now+timedelta(days=7)
        saved(self.card)

    def new_card_revision(self, **changes):
        data=dict(recruitment=self.card,version=1,existing_member_count=1,recruitment_quota=2,
                  foundation_requirement='beginner_ok',weekly_effort='over_2_to_5',
                  collaboration_mode='online',edited_by=self.owner)
        data.update(changes)
        revision=saved(RecruitmentRevision(**data))
        for member in self.team.active_members().exclude(application__recruitment_id=self.card.pk):
            saved(RecruitmentBaselineMember(revision=revision,membership=member))
        return revision

    def application(self, user=None):
        user=user or self.student
        obj=saved(Application(recruitment=self.card,applicant=user))
        rev=saved(ApplicationRevision(application=obj,version=1,recruitment_revision=self.card.current_revision,weekly_effort='over_2_to_5',created_by=user))
        obj.current_revision=rev
        return saved(obj)

    def joined(self, user=None):
        obj=self.application(user)
        obj.status='joined'; obj.end_reason='joined'; obj.resolved_at=self.now
        obj.contact_opened_at=self.now
        obj.applicant_confirmed_at=obj.recruiter_confirmed_at=self.now
        obj.applicant_confirmed_revision=obj.recruiter_confirmed_revision=obj.current_revision
        saved(obj)
        return saved(Membership(team=self.team,competition=self.competition,user=obj.applicant,join_source='application',application=obj))

    def reject_update(self, obj, **changes):
        with self.assertRaises(IntegrityError), transaction.atomic():
            type(obj).objects.filter(pk=obj.pk).update(**changes)

    def test_recruiter_also_has_one_team_per_edition(self):
        other=saved(Team(competition=self.competition,recruiter=self.owner))
        with self.assertRaises(IntegrityError),transaction.atomic():
            Membership.objects.create(team=other,competition=self.competition,user=self.owner,join_source='recruiter')

    def test_same_card_cannot_be_reapplied_after_withdrawal(self):
        app=self.application(); app.status='withdrawn';app.end_reason='withdrawn';app.resolved_at=self.now;saved(app)
        with self.assertRaises(IntegrityError),transaction.atomic():
            Application.objects.create(recruitment=self.card,applicant=self.student)

    def test_full_card_still_occupies_one_card_slot(self):
        self.joined();self.joined(self.third)
        self.assertEqual(self.card.remaining_slots,0)
        other=Recruitment.objects.create(team=self.team,duration_days=3)
        self.reject_update(other,publication_status='published',published_at=self.now,expires_at=self.now+timedelta(days=3),current_revision=self.revision)

    def test_card_edit_pauses_existing_applicant_but_keeps_contact(self):
        app=self.application();app.contact_opened_at=self.now;app.status='contact_open';saved(app)
        rev=self.new_card_revision(version=2,weekly_effort='over_5_to_10')
        self.card.current_revision=rev;self.card.last_edited_at=self.now;saved(self.card)
        app.refresh_from_db()
        self.assertTrue(app.is_paused)
        self.assertTrue(app.can_view_contact(self.owner.pk))
        self.assertFalse(app.can_view_contact(self.third.pk))
        current=saved(ApplicationRevision(application=app,version=2,recruitment_revision=rev,weekly_effort='over_5_to_10',created_by=self.student))
        app.current_revision=current;saved(app)
        self.assertFalse(app.is_paused)

    def test_read_message_is_not_acceptance(self):
        app=self.application()
        rev=self.new_card_revision(version=2,weekly_effort='over_10');self.card.current_revision=rev;saved(self.card)
        event=saved(BusinessEvent(kind='recruitment_edited',recruitment=self.card,payload={'from_version':1,'to_version':2,'changed_fields':['weekly_effort']}))
        msg=saved(Notification(event=event,recipient=self.student,title='条件更新',body='每周投入已更新。'))
        msg.read_at=timezone.now();saved(msg)
        app.refresh_from_db();self.assertTrue(app.is_paused)

    def test_optional_roles_and_wrong_role_relationship(self):
        app=self.application();self.assertEqual(app.current_revision.desired_roles.count(),0)
        role=saved(RecruitmentOption(code='domain-role',kind='role',name='编程'))
        with self.assertRaises(ValidationError):
            saved(ApplicationDesiredRole(revision=app.current_revision,option=role))

    def test_lower_quota_rejected_after_join(self):
        self.joined()
        with self.assertRaises(ValidationError):
            self.new_card_revision(version=2,recruitment_quota=0)

    def test_new_member_exit_frees_source_card_slot(self):
        member=self.joined();self.assertEqual(self.card.remaining_slots,1)
        member.ended_at=timezone.now();member.end_reason='exit';saved(member)
        self.assertEqual(self.card.remaining_slots,2)
        self.assertEqual(self.card.current_existing_member_count,1)

    def test_old_round_exit_reduces_baseline_without_expanding_quota(self):
        member=self.joined()
        self.card.closed_at=timezone.now();self.card.close_reason='manual';saved(self.card)
        self.card=saved(Recruitment(team=self.team,duration_days=7))
        self.revision=self.new_card_revision(existing_member_count=4,recruitment_quota=1)
        self.card.current_revision=self.revision;self.card.publication_status='published';self.card.published_at=self.now;self.card.expires_at=self.now+timedelta(days=7);saved(self.card)
        member.ended_at=timezone.now();member.end_reason='exit';saved(member)
        self.assertEqual(self.card.current_existing_member_count,3)
        self.assertEqual(self.card.remaining_slots,1)

    def test_published_content_cannot_be_rewritten_or_extended(self):
        self.revision.weekly_effort='over_10'
        with self.assertRaises(ValidationError): self.revision.full_clean()
        self.card.expires_at+=timedelta(days=1)
        with self.assertRaises(ValidationError): self.card.full_clean()

    def test_offline_revision_requires_campus_at_publication(self):
        revision=self.new_card_revision(version=2,collaboration_mode='offline')
        with self.assertRaises(ValidationError):revision.validate_ready()
        campus=saved(RecruitmentOption(code='domain-campus',kind='campus',name='测试校区'))
        saved(RecruitmentCampus(revision=revision,option=campus));revision.validate_ready()

    def test_database_rejects_partial_confirmations_and_unconfirmed_join(self):
        app=self.application()
        self.reject_update(app,applicant_confirmed_at=self.now)
        self.reject_update(app,status='joined',end_reason='joined',resolved_at=self.now,contact_opened_at=self.now)
        self.reject_update(app,status='unexpected')

    def test_membership_relation_mismatch_is_model_error(self):
        app=self.application()
        with self.assertRaises(ValidationError):
            saved(Membership(team=self.team,competition=self.competition,user=self.third,join_source='application',application=app))

    def test_departure_deadline_response_and_terminal_history(self):
        member=self.joined()
        req=saved(DepartureRequest(membership=member,kind='exit',initiator=self.student,responder=self.owner,created_at=self.now,deadline_at=self.now+timedelta(hours=24)))
        self.reject_update(req,deadline_at=self.now+timedelta(hours=25))
        self.reject_update(req,status='approved',resolved_at=self.now)
        req.status='rejected';req.response='reject';req.responded_at=self.now;req.resolved_at=self.now;saved(req)
        req.status='timed_out';req.response='';req.responded_at=None;req.resolved_at=self.now+timedelta(hours=24)
        with self.assertRaises(ValidationError):req.full_clean()
        member.refresh_from_db();self.assertIsNone(member.ended_at)

    def test_departure_requires_correct_parties_and_one_pending(self):
        member=self.joined()
        kwargs=dict(membership=member,kind='exit',initiator=self.student,responder=self.owner,created_at=self.now,deadline_at=self.now+timedelta(hours=24))
        saved(DepartureRequest(**kwargs))
        with self.assertRaises(IntegrityError),transaction.atomic():DepartureRequest.objects.create(**kwargs)
        kwargs['responder']=self.third
        with self.assertRaises(ValidationError):DepartureRequest(**kwargs).full_clean()

    def test_dissolution_pause_and_response_membership(self):
        member=self.joined();app=self.application(self.third)
        req=saved(DissolutionRequest(team=self.team,initiator=self.owner,created_at=self.now,deadline_at=self.now+timedelta(hours=24)))
        self.assertTrue(app.is_paused);self.assertFalse(self.card.is_open)
        row=saved(DissolutionResponse(request=req,membership=member))
        row.response='reject';row.responded_at=self.now;saved(row)
        row.response='agree'
        with self.assertRaises(ValidationError):row.full_clean()
        with self.assertRaises(ValidationError):saved(DissolutionResponse(request=req,membership=self.owner_member))

    def test_research_minimal_unstructured_publication_and_reverification(self):
        obj=saved(ResearchOpportunity(title='【虚构】招募',description='未结构化原文',recruiting_entity='某课题组',official_url='https://example.org/research',publication_status='published',published_at=self.now-timedelta(days=31)))
        self.assertIsNone(obj.category_id);self.assertIsNone(obj.vacancies_min);self.assertTrue(obj.needs_reverification);self.assertFalse(obj.is_closed)
        self.reject_update(obj,recruiting_entity='  ')
        self.reject_update(obj,official_url='')
        self.reject_update(obj,deadline_mode='fixed')
        self.reject_update(obj,weekly_hours_min=20,weekly_hours_max=10)
        self.reject_update(obj,weekly_hours_min=169)

    def test_wrong_category_and_timezone_rejected(self):
        tag=saved(ResearchTaxonomy(code='research-tag',kind='tag',name='研究方向'))
        with self.assertRaises(ValidationError):saved(ResearchOpportunity(title='草稿',category=tag))
        obj=ResearchOpportunity(title='草稿',deadline_mode='fixed',deadline_on=self.now.date(),deadline_at=self.now+timedelta(days=2),deadline_timezone='Asia/Shanghai')
        with self.assertRaises(ValidationError):obj.full_clean()

    def test_snapshot_rejects_private_fields_and_is_immutable(self):
        obj=saved(ResearchOpportunity(title='草稿'))
        rev=ResearchRevision(opportunity=obj,version=1,snapshot={'title':'草稿','content_version':1,'phone_number':'private'})
        with self.assertRaises(ValidationError):rev.full_clean()
        rev.snapshot.pop('phone_number');saved(rev);rev.snapshot['title']='修改'
        with self.assertRaises(ValidationError):rev.full_clean()

    def test_resource_publication_requires_category_and_link(self):
        obj=saved(Resource(title='草稿'))
        self.reject_update(obj,publication_status='published',published_at=self.now)
        category=saved(ResourceTaxonomy(code='resource-tutorial',kind='category',name='教程'))
        obj.category=category;obj.description='内容';obj.access_url='https://example.org/resource';obj.publication_status='published';obj.published_at=self.now;saved(obj)
        obj.availability='unavailable';saved(obj)

    def test_favorite_exact_target_unique_and_hidden_placeholder(self):
        obj=saved(Favorite(user=self.student,competition=self.competition))
        self.assertTrue(obj.is_target_available)
        self.reject_update(obj,competition=None)
        research=saved(ResearchOpportunity(title='草稿'))
        self.reject_update(obj,research=research)
        with self.assertRaises(IntegrityError),transaction.atomic():Favorite.objects.create(user=self.student,competition=self.competition)
        self.competition.publication_status='withdrawn';self.competition.withdrawal_reason='下架';self.competition.recruitment_enabled=False;saved(self.competition)
        obj.refresh_from_db();self.assertFalse(obj.is_target_available)

    def test_newsletter_confirmation_and_source_withdrawal(self):
        news=saved(Newsletter(created_by=self.owner))
        rev=saved(NewsletterRevision(newsletter=news,version=1,title='快讯',created_by=self.owner,updated_by=self.owner))
        rev.status='confirmed';rev.confirmed_at=self.now;rev.confirmed_by=self.owner
        with self.assertRaises(ValidationError):rev.full_clean()
        rev.status='draft';rev.confirmed_at=None;rev.confirmed_by=None
        item=saved(NewsletterItem(revision=rev,position=1,kind='competition',competition=self.competition,title_snapshot='当期标题',summary_snapshot='当期摘要',source_url='https://example.org/source',source_updated_at=self.competition.updated_at))
        rev.status='confirmed';rev.confirmed_at=self.now;rev.confirmed_by=self.owner;saved(rev)
        news.current_revision=rev;news.publication_status='published';news.published_at=self.now;saved(news)
        item.refresh_from_db();self.assertTrue(item.is_publicly_visible)
        with self.assertRaises(ValidationError):item.full_clean()
        Competition.objects.filter(pk=self.competition.pk).update(publication_status='withdrawn',withdrawal_reason='下架',recruitment_enabled=False)
        item.refresh_from_db();self.assertFalse(item.is_publicly_visible)

    def test_activity_has_no_linked_object(self):
        news=saved(Newsletter(created_by=self.owner));rev=saved(NewsletterRevision(newsletter=news,version=1,created_by=self.owner,updated_by=self.owner))
        item=saved(NewsletterItem(revision=rev,position=1,kind='activity',title_snapshot='活动段落',source_url='https://example.org/activity'))
        self.reject_update(item,competition=self.competition)

    def test_restriction_fixed_duration_and_revocation_pair(self):
        row=saved(UserRestriction(user=self.student,reason='测试原因',created_by=self.owner,starts_at=self.now,expires_at=self.now+timedelta(hours=24)))
        self.assertTrue(row.is_effective)
        self.reject_update(row,expires_at=self.now+timedelta(hours=48))
        self.reject_update(row,revoked_at=self.now)
        row.revoked_at=timezone.now();row.revoked_by=self.owner;row.revoke_reason='提前解除';saved(row)
        self.assertFalse(row.is_effective)

    def test_admin_action_target_and_immutable_history(self):
        obj=saved(AdminAction(action='disable_account',target_user=self.student,actor=self.owner,reason='测试'))
        self.reject_update(obj,competition=self.competition)
        obj.reason='修改理由'
        with self.assertRaises(ValidationError):obj.full_clean()

    def test_notification_dedup_and_event_payload(self):
        app=self.application();event=saved(BusinessEvent(kind='application_submitted',application=app))
        msg=saved(Notification(event=event,recipient=self.owner,title='申请',body='收到申请'))
        self.reject_update(msg,read_at=self.now-timedelta(days=1))
        with self.assertRaises(IntegrityError),transaction.atomic():Notification.objects.create(event=event,recipient=self.owner,title='申请',body='收到申请')
        with self.assertRaises(ValidationError):saved(BusinessEvent(kind='application_submitted',application=app,payload={'email':'private'}))
        with self.assertRaises(ValidationError):saved(BusinessEvent(kind='recruitment_edited',application=app,payload={}))

    def test_source_version_hash_and_duplicate_content(self):
        src=saved(SourceConfig(code='source-test',name='虚构来源',base_url='https://example.org',content_kind='research',adapter_key='test',maintained_by=self.owner))
        run=saved(FetchRun(source=src,requested_url='https://example.org/research',trigger='manual',triggered_by=self.owner))
        version=SourceVersion(source=src,first_fetch=run,source_url=run.requested_url,title='研究招募',body_text='来源正文')
        version.content_hash=source_hash(version);saved(version)
        clone=SourceVersion(source=src,first_fetch=run,source_url=run.requested_url,title=version.title,body_text=version.body_text,content_hash=version.content_hash)
        with self.assertRaises(IntegrityError),transaction.atomic():clone.save()
        version.body_text='改变'
        with self.assertRaises(ValidationError):version.full_clean()
        self.reject_update(run,status='failed',finished_at=self.now+timedelta(seconds=5))

    def test_ai_failure_metadata_and_referenced_call_protection(self):
        call=saved(AICall(provider='test',model_name='fictional',prompt_version='test-v1'))
        self.reject_update(call,status='succeeded')
        result=saved(ProcessingResult(task_type='newsletter_draft',ai_call=call))
        with self.assertRaises(ProtectedError):call.delete()
        self.reject_update(result,status='accepted',decision_mode='rules',rule_version='r1',reviewed_at=self.now)

    def test_newsletter_input_limit_and_private_key_rejection(self):
        result=saved(ProcessingResult(task_type='newsletter_draft'))
        kwargs=dict(result=result,position=1,competition=self.competition,snapshot={'title':'标题','body':'内容','source_url':'https://example.org'})
        row=saved(ProcessingInput(**kwargs))
        row.snapshot['phone']='private'
        with self.assertRaises(ValidationError):row.full_clean()
        row.snapshot.pop('phone')
        for i in range(2,11):kwargs['position']=i;saved(ProcessingInput(**kwargs))
        kwargs['position']=11
        with self.assertRaises(ValidationError):ProcessingInput(**kwargs).full_clean()

    @skipUnless(connection.vendor == 'postgresql','PostgreSQL catalog verification')
    def test_all_domain_constraints_and_indexes_exist_in_postgresql(self):
        labels={'accounts','competitions','teams','research','resources','favorites','newsletters','governance','notifications','ingestion'}
        with connection.cursor() as cursor:
            for model in apps.get_models():
                if model._meta.app_label not in labels:continue
                actual=connection.introspection.get_constraints(cursor,model._meta.db_table)
                for constraint in model._meta.constraints:
                    self.assertIn(constraint.name,actual,model._meta.label)
                for index in model._meta.indexes:
                    self.assertTrue(actual[index.name]['index'])
            cursor.execute("SELECT indexdef FROM pg_indexes WHERE indexname = 'membership_one_active'")
            self.assertIn('WHERE (ended_at IS NULL)',cursor.fetchone()[0])
