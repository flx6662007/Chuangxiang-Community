from rest_framework import serializers
from .models import User


class ContactSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('wechat_id', 'phone_number')

    def to_internal_value(self, data):
        if not isinstance(data, dict):
            raise serializers.ValidationError('请求必须为 JSON 对象。')
        extra = set(data) - set(self.fields)
        if extra:
            raise serializers.ValidationError({name: '此字段不允许修改。' for name in extra})
        return super().to_internal_value(data)
