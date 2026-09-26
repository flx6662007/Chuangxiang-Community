"""公开接口字段白名单；内部操作者、下架原因及核验依据不输出。"""

from rest_framework import serializers

from .models import Competition, CompetitionSource, CompetitionTaxonomy


class TaxonomySerializer(serializers.ModelSerializer):
    class Meta:
        model = CompetitionTaxonomy
        fields = ('id', 'code', 'name')


class PublicSourceSerializer(serializers.ModelSerializer):
    class Meta:
        model = CompetitionSource
        fields = ('id', 'source_type', 'source_name', 'source_url', 'source_published_on')


class CompetitionListSerializer(serializers.ModelSerializer):
    category = TaxonomySerializer(read_only=True)
    tags = TaxonomySerializer(many=True, read_only=True)
    primary_source = serializers.SerializerMethodField()
    is_recruitment_open = serializers.BooleanField(read_only=True)

    def get_primary_source(self, obj):
        source = next((source for source in obj.public_sources if source.is_primary), None)
        return PublicSourceSerializer(source).data if source else None

    class Meta:
        model = Competition
        fields = (
            'id', 'code', 'title', 'edition', 'summary', 'category', 'tags', 'level',
            'participation_type', 'organizer', 'registration_deadline',
            'registration_deadline_at', 'registration_deadline_timezone',
            'submission_deadline', 'submission_deadline_at', 'submission_deadline_timezone',
            'published_at', 'updated_at', 'last_verified_at', 'is_recruitment_open',
            'primary_source',
        )


class CompetitionDetailSerializer(CompetitionListSerializer):
    sources = PublicSourceSerializer(source='public_sources', many=True, read_only=True)

    class Meta(CompetitionListSerializer.Meta):
        fields = CompetitionListSerializer.Meta.fields + (
            'description', 'tracks', 'eligibility', 'team_size_min', 'team_size_max',
            'registration_method', 'registration_url', 'campus_arrangements',
            'campus_deadline', 'campus_deadline_at', 'campus_deadline_timezone',
            'deadline_notes', 'recruitment_deadline', 'sources',
        )
