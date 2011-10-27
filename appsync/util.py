from decimal import Decimal, InvalidOperation
import time
import os


def resolve_name(name):
    parts = name.split('.')
    cursor = len(parts)
    module_name = parts[:cursor]
    last_error = None
    last_error_module_path = None
    while cursor > 0:
        try:
            ret = __import__('.'.join(module_name))
            break
        except ImportError, ext:
            last_error = ext
            args = []
            args += module_name
            last_error_module_path = '%s.py' % os.path.join(*args)
            if cursor == 0:
                raise
            cursor -= 1
            module_name = parts[:cursor]
            ret = ''
        else:
            last_error = None
            last_error_module_path = None

    for part in parts[1:]:
        try:
            ret = getattr(ret, part)
        except AttributeError as exc:
            if last_error is not None \
                    and os.path.isfile(last_error_module_path):
                raise last_error
            raise ImportError(exc)

    return ret


def round_time(value=None, precision=2):
    """Transforms a timestamp into a two digits Decimal.

    Arg:
        value: timestamps representation - float or str.
        If None, uses time.time()

        precision: number of digits to keep. defaults to 2.

    Return:
        A Decimal two-digits instance.
    """
    if value is None:
        value = time.time()
    if not isinstance(value, str):
        value = str(value)
    try:
        digits = '0' * precision
        return Decimal(value).quantize(Decimal('1.' + digits))
    except InvalidOperation:
        raise ValueError(value)


def get_storage(request):
    return request.registry['storage']
