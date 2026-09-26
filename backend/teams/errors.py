from rest_framework.exceptions import APIException


class BusinessError(APIException):
    status_code = 409

    def __init__(self, code, detail, status=409, fields=None):
        self.status_code = status
        data = {'code': code, 'detail': detail}
        if fields:
            data['fields'] = fields
        super().__init__(data)


def check(condition, code, detail, status=409):
    if not condition:
        raise BusinessError(code, detail, status)
