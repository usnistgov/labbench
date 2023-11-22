import typing
from pathlib import Path as _Path
import numbers
from . import _bases
from .. import util
import validators as _val


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

#    min: typing.Union[int, None] = None
#    max: typing.Union[int, None] = None


class Float(_bases.BoundedNumber[float], type=float):
    """accepts numerical, str, or bytes values, following normal python casting procedures (with bounds checking)"""

#    min: typing.Union[float, None] = None
#    max: typing.Union[float, None] = None
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


class Complex(_bases.ParamAttr[complex], type=complex):
    """accepts numerical or str values, following normal python casting procedures (with bounds checking)"""

    allow_none: bool = False


class Bool(_bases.ParamAttr[bool], type=bool):
    """accepts boolean or numeric values, or a case-insensitive match to one of ('true',b'true','false',b'false')"""

    allow_none: bool = False

    @util.hide_in_traceback
    def validate(self, value, owner=None):
        if isinstance(value, (bool, numbers.Number)):
            return value
        elif isinstance(value, (str, bytes)):
            lvalue = value.lower()
            if lvalue in ("true", b"true"):
                return True
            elif lvalue in ("false", b"false"):
                return False
        raise ValueError(
            f"'{self.__repr__(owner_inst=owner)}' accepts only boolean, numerical values,"
            "or one of ('true',b'true','false',b'false'), case-insensitive"
        )


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


class Unicode(String[str], type=str):
    """accepts strings or numeric values only; convert others explicitly before assignment"""

    @util.hide_in_traceback
    def validate(self, value, owner=None):
        if not isinstance(value, (str, numbers.Number)):
            raise ValueError(
                f"'{type(self).__qualname__}' attributes accept values of str or numerical type, not {type(value).__name__}"
            )
        return value


class Bytes(String[bytes], type=bytes):
    """accepts bytes objects only - encode str (unicode) explicitly before assignment"""


class Iterable(_bases.ParamAttr):
    """accepts any iterable"""

    @util.hide_in_traceback
    def validate(self, value, owner=None):
        if not hasattr(value, "__iter__"):
            raise ValueError(
                f"'{type(self).__qualname__}' attributes accept only iterable values"
            )
        return value


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
        path = self._type(value)

        if self.must_exist and not path.exists():
            raise IOError()

        return path


class NetworkAddress(Unicode):
    """a IDN-compatible network address string, such as an IP address or DNS hostname"""

    accept_port: bool = True

    @util.hide_in_traceback
    def validate(self, value, owner=None):
        """Rough IDN compatible domain validator"""

        host, *extra = value.split(":", 1)

        if len(extra) > 0:
            port = extra[0]
            try:
                int(port)
            except ValueError:
                raise ValueError(f'port {port} in "{value}" is invalid')

            if not self.accept_port:
                raise ValueError(
                    f"{self} does not accept a port number (accept_port=False)"
                )

        for validate in _val.ipv4, _val.ipv6, _val.domain, _val.slug:
            if validate(host):
                break
        else:
            raise ValueError("invalid host address")

        return value
