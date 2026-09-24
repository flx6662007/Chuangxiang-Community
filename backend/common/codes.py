import uuid

from django.utils.deconstruct import deconstructible


@deconstructible
class new_code:
    """可被迁移序列化的稳定编码生成器。"""

    def __init__(self, prefix):
        self.prefix = prefix

    def __call__(self):
        return f'{self.prefix}-{uuid.uuid4().hex}'
