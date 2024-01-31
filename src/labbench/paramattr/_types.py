import numbers
import typing
from pathlib import Path as _Path

import validators as _val

from .. import util
from . import _bases


class Any(_bases.ParamAttr[typing.Any], type=object):
    """allows any value"""

    @util.hide_in_traceback
    def validate(self, value, owner=None):
        return value

    @util.hide_in_traceback
    def to_pythonic(self, value):
        return value


class Int(_bases.BoundedNumber[int], type=int):
    """accepts numerical, str, or bytes values, following normal python casting procedures (with bounds checking)"""


class Float(_bases.BoundedNumber[float], type=float):
    """accepts numerical, str, or bytes values, following normal python casting procedures (with bounds checking)"""

    step: typing.Union[float, None] = None

    @util.hide_in_traceback
    def validate(self, value, owner=None):
        value = super().validate(value, owner)
        if self.step is not None:
            mod = value % self.step
            if mod < self.step / 2:
                return value - mod
            else:
                return value - (mod - self.step)
        return value

    def doc_params(
        self, skip: list[str] = ['help', 'label'], as_argument: bool = False
    ) -> str:
        if as_argument:
            return None

        else:
            # for text docs: allow subclasses to document their own params
            docs = []
            if self.step is not None:
                docs.append(f'* Step size: {self.step} {self.label}')

            return '\n'.join(docs) + '\n'


class Complex(_bases.ParamAttr[complex], type=complex):
    """accepts numerical or str values, following normal python casting procedures (with bounds checking)"""

    allow_none: bool = False


class Bool(_bases.ParamAttr[bool], type=bool):
    """accepts boolean or numeric values, or a case-insensitive match to one of ('true',b'true','false',b'false')"""

    allow_none: bool = False
    # because this becomes confusing with evaluating boolean trueness


class String(_bases.ParamAttr):
    """base class for string types, which adds support for case sensitivity arguments"""

    case: bool = True
    # allow_none: bool = True # let's not override this default

    @util.hide_in_traceback
    def contains(self, iterable, value):
        if not self.case:
            iterable = [v.lower() for v in iterable]
            value = value.lower()
        return value in iterable

    @util.hide_in_traceback
    def validate(self, value, owner=None):
        if isinstance(value, (self._type, numbers.Number)):
            return self._type(value)

        raise ValueError(
            f'cannot convert to {type(value).__qualname__} to {self._type.__qualname__}'
        )

    def doc_params(
        self, skip: list[str] = ['help', 'label'], as_argument: bool = False
    ) -> str:
        if as_argument:
            return None

        else:
            # for text docs: allow subclasses to document their own params
            if self.case:
                return '* Case sensitive'
            else:
                return '* Case insensitive'


class Unicode(String[str], type=str):
    """accepts strings or numeric values only; convert others explicitly before assignment"""


class Bytes(String[bytes], type=bytes):
    """accepts bytes objects only - encode str (unicode) explicitly before assignment"""


class Iterable(_bases.ParamAttr):
    """accepts any iterable"""

    @util.hide_in_traceback
    def validate(self, value, owner=None):
        if not hasattr(value, '__iter__'):
            raise ValueError(
                f"'{type(self).__qualname__}' attributes accept only iterable values"
            )
        return self._type(value)


class Dict(Iterable[dict], type=dict):
    """accepts any type of iterable value accepted by python `dict()`"""


class List(Iterable[list], type=list):
    """accepts any type of iterable value accepted by python `list()`"""


class Tuple(Iterable[tuple], type=tuple):
    """accepts any type of iterable value accepted by python `tuple()`"""

    sets: bool = False


class Path(_bases.ParamAttr[_Path], type=_Path):
    must_exist: bool = False
    """ does the path need to exist when set? """

    @util.hide_in_traceback
    def validate(self, value, owner=None):
        path = _Path(value)

        if self.must_exist and not path.exists():
            raise OSError('no file at path {value}')

        return path

    def doc_params(
        self, skip: list[str] = ['help', 'label'], as_argument: bool = False
    ) -> str:
        if as_argument:
            return None

        else:
            # for text docs: allow subclasses to document their own params
            if self.must_exist:
                return '* Path name must exist on the host'


class NetworkAddress(Unicode):
    """a IDN-compatible network address string, such as an IP address or DNS hostname"""

    accept_port: bool = True

    @util.hide_in_traceback
    def validate(self, value, owner=None):
        """roughly IDN-compatible address (not URL) validator"""

        def any_valid(s: str, validators: list[callable]):
            for validator in validators:
                if validator(s):
                    return True
            return False

        def validate_port_string(s):
            if not self.accept_port:
                raise ValueError(
                    f'{self} does not accept a port number (accept_port=False)'
                )

            try:
                int(s)
            except ValueError:
                return False

            return True

        if any_valid(value, (_val.ipv4, _val.ipv6, _val.domain, _val.slug)):
            return value

        if value[0] == '[':
            # maybe ipv6 with port number
            host, *port = value[1:].rsplit(']', 1)
            if len(port) > 0 and _val.ipv6(host):
                if validate_port_string(port[0][1:]):
                    return value

        # maybe an IP address with
        host, *extra = value.split(':', 1)
        if len(extra) > 0 and any_valid(host, (_val.ipv4, _val.domain, _val.slug)):
            if validate_port_string(extra[0]):
                return value

        raise ValueError('invalid host address')
