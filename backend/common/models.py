"""共用校验。full_clean 不替代数据库事务或批量写入的调用方责任。"""
from django.core.exceptions import ValidationError

from competitions.models import CleanFieldsModel


def require(condition, message):
    if not condition:
        raise ValidationError(message)


class DomainModel(CleanFieldsModel):
    immutable_fields = ()

    class Meta:
        abstract = True

    def clean(self):
        super().clean()
        old = None if self._state.adding else type(self).objects.filter(pk=self.pk).first()
        if old:
            fields = self.immutable_fields
            if fields == '*':
                fields = [f.attname for f in self._meta.concrete_fields]
            for name in fields:
                require(getattr(old, name) == getattr(self, name), f'{name} 属于已记录历史，不能原地修改。')
            if hasattr(self, 'published_at') and old.published_at:
                require(self.published_at == old.published_at, '不能重置首次发布时间。')
            if hasattr(self, 'ended_at') and old.ended_at:
                require(self.ended_at == old.ended_at and self.end_reason == old.end_reason, '已结束成员关系不能重开或改写。')
            if hasattr(self, 'dissolved_at') and old.dissolved_at:
                require(self.dissolved_at == old.dissolved_at, '已经解散的队伍不能恢复。')
            if hasattr(self, 'revoked_at') and old.revoked_at:
                require(all(getattr(self, f) == getattr(old, f) for f in ('revoked_at','revoked_by_id','revoke_reason')),
                        '提前解除记录不能改写或撤销。')
        if hasattr(self, 'category_id') and self.category_id:
            category = self.category
            require(category.kind == 'category', '主分类必须使用 category 词条。')
            if not old or old.category_id != self.category_id:
                require(category.is_active, '不能新增选择已停用词条。')
        if hasattr(self, 'relation_owner'):
            target = getattr(self, self.relation_target)
            owner = getattr(self, self.relation_owner)
            if self.relation_kind:
                require(target.kind == self.relation_kind, '关联词条用途不匹配。')
                if self._state.adding:
                    require(target.is_active, '不能新增选择已停用词条。')
            if owner._meta.model_name in ('recruitmentrevision', 'applicationrevision'):
                parent_field = 'recruitment' if owner._meta.model_name == 'recruitmentrevision' else 'application'
                parent = getattr(owner, parent_field)
                # 版本先装配关联，最后切换主表指针；生效后不再追加关联。
                if self._state.adding:
                    require(not parent.current_revision_id or parent.current_revision.version < owner.version,
                            '已生效版本不能增补多选关联，请建立下一版。')
            if self._meta.model_name == 'applicationdesiredrole':
                require(owner.recruitment_revision.required_roles.filter(pk=target.pk).exists(),
                        '意向角色必须来自所接受的卡片版本。')
