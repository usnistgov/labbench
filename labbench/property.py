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

from . import _traits


class message_adapter(_traits.BackendPropertyAdapter):
    """Device class decorator that implements automatic API that triggers API messages for labbench properties.

    Example usage:

    ```python
        import labbench as lb

        @lb.message_adapter(query_fmt='{key}?', write_fmt='{key} {value}', query_func='get', write_func='set')
        class MyDevice(lb.Device):
            def set(self, set_msg: str):
                # do set
                pass

            def get(self, get_msg: str):
                # do get
                pass
    ```

    Decorated classes connect traits that are defined with the `key` keyword to trigger
    backend API calls based on the key. The implementation of the `set` and `get` methods
    in subclasses of MessagePropertyAdapter determines how the key is used to generate API calls.
    """

    def __init__(
        self, query_fmt=None, write_fmt=None, write_func=None, query_func=None, remap={}
    ):
        super().__init__()

        self.query_fmt = query_fmt
        self.write_fmt = write_fmt
        self.write_func = write_func
        self.query_func = query_func

        # ensure str type for messages; keys can be arbitrary python type
        if not all(isinstance(v, str) for v in remap.values()):
            raise TypeError("all values in remap dict must have type str")
        self.value_map = remap

        if len(remap) > 0:
            # create the reverse mapping and ensure all values are unique
            self.message_map = __builtins__["dict"](zip(remap.values(), remap.keys()))
        else:
            self.message_map = {}
        if len(self.message_map) != len(self.value_map):
            raise ValueError("'remap' has duplicate values")

    def get(self, device: _traits.HasTraits, scpi_key: str, trait=None):
        """queries a parameter named `scpi_key` by sending an SCPI message string.

        The command message string is formatted as f'{scpi_key}?'.
        This is automatically called in wrapper objects on accesses to property traits that
        defined with 'key=' (which then also cast to a pythonic type).

        Arguments:
            key (str): the name of the parameter to set
            name (str, None): name of the trait setting the key (or None to indicate no trait) (ignored)

        Returns:
            response (str)
        """
        if self.query_fmt is None:
            raise ValueError("query_fmt needs to be set for key get operations")
        if self.query_func is None:
            raise ValueError("query_func needs to be set for key get operations")
        query_func = getattr(device, self.query_func)
        value_str = query_func(self.query_fmt.format(key=scpi_key)).rstrip()
        return self.message_map.get(value_str, value_str)

    def set(self, device: _traits.HasTraits, scpi_key: str, value, trait=None):
        """writes an SCPI message to set a parameter with a name key
        to `value`.

        The command message string is formatted as f'{scpi_key} {value}'. This
        This is automatically called on assignment to property traits that
        are defined with 'key='.

        Arguments:
            scpi_key (str): the name of the parameter to set
            value (str): value to assign
            name (str, None): name of the trait setting the key (or None to indicate no trait) (ignored)
        """
        if self.write_fmt is None:
            raise ValueError("write_fmt needs to be set for key set operations")
        if self.write_func is None:
            raise ValueError("write_func needs to be set for key set operations")

        value_str = self.value_map.get(value, value)
        write_func = getattr(device, self.write_func)
        write_func(self.write_fmt.format(key=scpi_key, value=value_str))


class visa_adapter(message_adapter):
    """Device class decorator that automates SCPI command string interactions for labbench properties.

    Example usage:

    ```python
        import labbench as lb

        @lb.property.visa_adapter(query_fmt='{key}?', write_fmt='{key} {value}')
        class MyDevice(lb.VISADevice):
            pass
    ```

    This causes access to property traits defined with 'key=' to interact with the
    VISA instrument. By default, messages in VISADevice objects trigger queries
    with the `'{key}?'` format, and writes formatted as f'{key} {value}'.
    """

    def __init__(
        self,
        query_fmt="{key}?",
        write_fmt="{key} {value}",
        write_func="write",
        query_func="query",
        remap={},
    ):
        super().__init__(
            query_fmt=query_fmt,
            write_fmt=write_fmt,
            remap=remap,
            write_func="write",
            query_func="query",
        )


class bool(_traits.Bool):
    pass


class float(_traits.Float):
    pass


class int(_traits.Int):
    pass


class complex(_traits.Complex):
    pass


class str(_traits.Unicode):
    pass


class bytes(_traits.Bytes):
    pass


class list(_traits.List):
    pass


class tuple(_traits.Tuple):
    pass


class dict(_traits.Dict):
    pass


class Path(_traits.Path):
    pass


# class DataFrame(_traits.PandasDataFrame):
#     pass


# class Series(_traits.PandasSeries):
#     pass


# class ndarray(_traits.NumpyArray):
#     pass


class NetworkAddress(_traits.NetworkAddress):
    pass


# mutate these traits into the right role
_traits.subclass_namespace_traits(
    locals(), role=_traits.Trait.ROLE_PROPERTY, omit_trait_attrs=["default", "func"]
)
