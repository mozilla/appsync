import simplejson as json
from decimal import Decimal, InvalidOperation
import time


def json_renderer(helper):
    return _JsonRenderer()


class _JsonRenderer(object):
    def __call__(self, data, context):
        response = context['request'].response
        response.content_type = 'application/json'
        return json.dumps(data, use_decimal=True)


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
