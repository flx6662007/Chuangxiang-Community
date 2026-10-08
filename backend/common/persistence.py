"""显式先校验后保存；不建立事务、不获取锁、不检查业务权限。"""


def clean_save(obj, **kwargs):
    obj.full_clean()
    obj.save(**kwargs)
    return obj
