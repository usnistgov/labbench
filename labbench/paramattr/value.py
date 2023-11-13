# This software was developed by employees of the National Institute of
# Standards and Technology (NIST), an agency of the Federal Government.
# Pursuant to title 17 United States Code Section 105, works of NIST employees
# are not subject to copyright protection in the United States and are
# considered to be in the public domain. Permission to freely use, copy,
# modify, and distribute this software and its documentation without fee is
# hereby granted, provided that this notice and disclaimer of warranty appears
# in all copies.
#
# THE SOFTWARE IS PROVIDED 'AS IS' WITHOUT ANY WARRANTY OF ANY KIND, EITHER
# EXPRESSED, IMPLIED, OR STATUTORY, INCLUDING, BUT NOT LIMITED TO, ANY WARRANTY
# THAT THE SOFTWARE WILL CONFORM TO SPECIFICATIONS, ANY IMPLIED WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE, AND FREEDOM FROM
# INFRINGEMENT, AND ANY WARRANTY THAT THE DOCUMENTATION WILL CONFORM TO THE
# SOFTWARE, OR ANY WARRANTY THAT THE SOFTWARE WILL BE ERROR FREE. IN NO EVENT
# SHALL NIST BE LIABLE FOR ANY DAMAGES, INCLUDING, BUT NOT LIMITED TO, DIRECT,
# INDIRECT, SPECIAL OR CONSEQUENTIAL DAMAGES, ARISING OUT OF, RESULTING FROM,
# OR IN ANY WAY CONNECTED WITH THIS SOFTWARE, WHETHER OR NOT BASED UPON
# WARRANTY, CONTRACT, TORT, OR OTHERWISE, WHETHER OR NOT INJURY WAS SUSTAINED
# BY PERSONS OR PROPERTY OR OTHERWISE, AND WHETHER OR NOT LOSS WAS SUSTAINED
# FROM, OR AROSE OUT OF THE RESULTS OF, OR USE OF, THE SOFTWARE OR SERVICES
# PROVIDED HEREUNDER. Distributions of NIST software should also include
# copyright and licensing statements of any third-party software that are
# legally bundled with the code in compliance with the conditions of those
# licenses.

from . import _types
from ._bases import Value
import typing as _typing


class any(Value, _types.Any):
    default: _typing.Any = None


class bool(Value, _types.Bool):
    default: _typing.Union[bool,None] = None


class float(Value, _types.Float):
    default: _typing.Union[float,None] = None


class int(Value, _types.Int):
    default: _typing.Union[int,None] = None


class complex(Value, _types.Complex):
    default: _typing.Union[_types.Complex._type,None] = None


class str(Value, _types.Unicode):
    default: _typing.Union[str,None] = ""


class bytes(Value, _types.Bytes):
    default: _typing.Union[bytes,None] = b""


class list(Value, _types.List):
    default: _typing.Union[list,None] = None


class tuple(Value, _types.Tuple):
    default: _typing.Union[tuple,None] = None


class dict(Value, _types.Dict):
    default: _typing.Union[dict,None] = None


class Path(Value, _types.Path):
    default: _typing.Union[_types.Path._type,None] = None


class NetworkAddress(Value, _types.NetworkAddress):
    default: _typing.Union[_types.NetworkAddress._type,None] = None

# used to set up hints for static type checking
_ALL_TYPES = any, bool, float, int, complex, str, bytes, list, tuple, dict, Path, NetworkAddress