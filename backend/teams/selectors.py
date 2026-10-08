"""组队可见范围查询；不执行状态结算或写入。"""
from django.db.models import Q

from .models import Application, Membership, Recruitment, Team


def public_cards():
    return Recruitment.objects.filter(publication_status='published', team__competition__publication_status='published',
        current_revision__isnull=False).exclude((Q(team__competition__code__startswith='demo-r1-') |
            Q(team__competition__code__startswith='demo-r2-')) & Q(team__competition__title__contains='【虚构样例】')).select_related(
                'team__competition', 'team__recruiter', 'current_revision')


def own_applications(user):
    return Application.objects.filter(Q(applicant=user) | Q(recruitment__team__recruiter=user)).select_related(
        'applicant', 'recruitment__team__competition', 'recruitment__team__recruiter', 'recruitment__current_revision',
        'current_revision__recruitment_revision')


def own_teams(user):
    return Team.objects.filter(pk__in=Membership.objects.filter(user=user).values('team_id')).select_related('competition', 'recruiter')
