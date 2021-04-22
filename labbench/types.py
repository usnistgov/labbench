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

""" Special type implementations for Device value, property, and datareturn calls.
"""

# TODO: Consider whether these should really be here
from builtins import bool, bytes, complex, dict, float, int, list, str, tuple
from pathlib import Path
from pandas import Series, DataFrame
from numpy import array

# underscore so that tab completion shows only valid types
from . import util as _util
from . import _traits
import validators as _val

@_util.autocomplete_init
class NetworkAddress(_traits.Unicode):
    """ accepts IDN-compatible network address, such as an IP address or DNS hostname """

    accept_port:bool = True

    @_util.hide_in_traceback
    def validate(self, value, owner=None):
        """Rough IDN compatible domain validator"""
        
        host,*extra = value.split(':',1)

        if len(extra) > 0:
            port = extra[0]
            try:
                int(port)
            except ValueError:
                raise ValueError(f'port {port} in "{value}" is invalid')

            if not self.accept_port:
                raise ValueError(f'{self} does not accept a port number (accept_port=False)')

        for validate in _val.ipv4, _val.ipv6, _val.domain:
            if validate(host):
                break
        else:
            raise ValueError('invalid host address')

        host = value.encode('idna').lower()
        pattern = re.compile(br'^([0-9a-z][-\w]*[0-9a-z]\.)+[a-z0-9\-]{2,15}$')
        m = pattern.match(host)

        if m is None:
            raise ValueError(f'"{value}" is an invalid host address')
        
        return value