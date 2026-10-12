"""Remove organization and personal credits from the published October issue.

The confirmed snapshot is immutable in normal editing flows, so this one-time
correction updates the stored public revision without changing publish dates or
item snapshots. It is intentionally not reversed on rollback.
"""
from datetime import date

from django.db import migrations


ISSUE_CODE = 'newsletter-2026-10'
ISSUE_TITLE = '创享快讯 · 2026年10月'
ISSUE_CREDITS = '创享编辑部'


def anonymize_october_issue(apps, schema_editor):
    Newsletter = apps.get_model('newsletters', 'Newsletter')
    NewsletterRevision = apps.get_model('newsletters', 'NewsletterRevision')
    database = schema_editor.connection.alias

    # Match the previously published issue by its month and source date, while
    # avoiding any rewrite of unrelated newsletters or already corrected data.
    candidates = list(Newsletter.objects.using(database).filter(
        code__endswith=ISSUE_CODE,
        current_revision__source_published_on=date(2026, 10, 10),
        current_revision__title__endswith=ISSUE_TITLE,
    ).exclude(code=ISSUE_CODE).values_list('pk', flat=True))
    if not candidates:
        return
    if len(candidates) != 1 or Newsletter.objects.using(database).filter(code=ISSUE_CODE).exists():
        raise RuntimeError('October newsletter identity is ambiguous; review records before migrating.')

    issue_id = candidates[0]
    for revision in NewsletterRevision.objects.using(database).filter(newsletter_id=issue_id):
        updates = {'credits': ISSUE_CREDITS}
        if revision.title.endswith(ISSUE_TITLE):
            updates['title'] = ISSUE_TITLE
        NewsletterRevision.objects.using(database).filter(pk=revision.pk).update(**updates)
    Newsletter.objects.using(database).filter(pk=issue_id).update(code=ISSUE_CODE)


class Migration(migrations.Migration):
    dependencies = [('newsletters', '0003_newsletteritem_group_title_and_more')]

    operations = [migrations.RunPython(anonymize_october_issue, migrations.RunPython.noop)]
