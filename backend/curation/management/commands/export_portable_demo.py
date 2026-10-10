"""Export public demo content without writing to the configured source database."""
import json
from pathlib import Path
import os
import tempfile

from django.conf import settings
from django.core.management.base import BaseCommand
from django.core.serializers.json import DjangoJSONEncoder

from common.portable_export import build_public_fixture, fixture_report, readonly_snapshot


def atomic_write(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=path.name + '.', suffix='.tmp', delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(payload)
        os.replace(temporary, path)
    finally:
        if temporary and temporary.exists():
            temporary.unlink()


class Command(BaseCommand):
    help = 'Read-only export of sanitized public content; never exports real users or operational history.'
    requires_system_checks = []

    def add_arguments(self, parser):
        parser.add_argument('--output', type=Path, default=settings.BASE_DIR.parent / '.local' / 'portable-demo' / 'public-fixture.json')
        parser.add_argument('--database', default='default')
        parser.add_argument('--demo-actor-id', type=int, default=1)

    def handle(self, *args, **options):
        database, actor = options['database'], options['demo_actor_id']
        with readonly_snapshot(database):
            fixture = build_public_fixture(database=database, demo_actor_id=actor)
        payload = (json.dumps(fixture, cls=DjangoJSONEncoder, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
        report = fixture_report(fixture, payload, demo_actor_id=actor, database=database)
        output = options['output'].resolve()
        atomic_write(output, payload)
        atomic_write(output.with_suffix('.manifest.json'), (json.dumps(report, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
        self.stdout.write(json.dumps(report, ensure_ascii=False, indent=2))
