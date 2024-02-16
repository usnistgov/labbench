import builtins
import string
from typing import Any, Union
from numbers import Number

from ._bases import HasParamAttrs, KeyAdapterBase, ParamAttr, T, BoundedNumber
from ._types import Bool

class message_keying(KeyAdapterBase):
    """Base class for decorators configure wrapper access to a backend API in of a
    :class:labbench.Device` class through string `key` arguments.

    Decorated classes connect traits that are defined with the `key` keyword to trigger
    backend API calls based on the key. The implementation of the `set` and `get` methods
    determines how the key is used to generate API calls.

    Example:

        A custom implementation::

            import labbench as lb
            from labbench import paramattr as attr


            class custom_keying(attr.message_keying):
                def get(self, device: lb.Device, scpi_key: str, trait_name=None):
                    if ' ' in scpi_key:
                        key = scpi_key.replace(' ', '? ', 1)
                    else:
                        key = scpi_key + '?'
                    return device.query(key)

                def set(self, device: lb.Device, scpi_key: str, value, trait_name=None):
                    if ' ' in scpi_key:
                        key = f'{scpi_key},{value}'
                    else:
                        key = f'{scpi_key} {value}'
                    return device.write(key.rstrip())


            @custom_keying(remap={True: 'ON', False: 'OFF'})
            class CustomDevice(lb.VISADevice):
                pass

    See Also:

        * :meth:`labbench.paramattr.visa_keying`
    """

    _formatter = string.Formatter()

    def __init__(
        self,
        *,
        query_fmt=None,
        write_fmt=None,
        write_func=None,
        query_func=None,
        remap={},
    ):
        super().__init__()

        self.query_fmt = query_fmt
        self.write_fmt = write_fmt
        self.write_func = write_func
        self.query_func = query_func

        if len(remap) == 0:
            self.value_map = {}
            self.message_map = {}
            return

        # ensure str type for messages; keys can be arbitrary python type
        if not all(isinstance(v, builtins.str) for v in remap.values()):
            raise TypeError('all values in remap dict must have type str')

        self.value_map = remap

        # create the reverse mapping
        self.message_map = builtins.dict(zip(remap.values(), remap.keys()))

        # and ensure all values are unique
        if len(self.message_map) != len(self.value_map):
            raise ValueError("'remap' has duplicate values")

    def get_kwarg_names(self, s: str) -> list[str]:
        """returns an argument list based on f-string style curly-brace formatting tokens.

        Example:

            ```python
            # input
            print(key_adapter.get_kwarg_names('CH{channel}:SV:CENTERFrequency'))
            ['channel']
            ```
        """
        return [tup[1] for tup in self._formatter.parse(s) if tup[1] is not None]

    def from_message(self, msg):
        return self.message_map.get(msg, msg)

    def to_message(self, value, attr_def: ParamAttr):
        matches = tuple({value} & self.value_map.keys())
        if len(matches) == 0:
            return value
                       
        # gymnastics caused by the python quirk that (True == 1) but not (True is 1):
        # we don't want to remap 1 using self.value_map[True]
        # TODO: change the definition of remap to fix this problem
        key_type = type(self.message_map[self.value_map[matches[0]]])
        if key_type is bool and isinstance(attr_def, BoundedNumber):
            return value
        elif issubclass(key_type, Number) and not key_type is not bool and isinstance(attr_def, Bool):
            return value
        
        return self.value_map[value]

    def get(
        self,
        owner: HasParamAttrs,
        scpi_key: str,
        paramattr: Union[ParamAttr[T], None],
        kwargs: dict[str, Any] = {},
    ) -> T:
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
            raise ValueError('query_fmt needs to be set for key get operations')
        if self.query_func is None:
            raise ValueError('query_func needs to be set for key get operations')
        query_func = getattr(owner, self.query_func)
        try:
            expanded_scpi_key = scpi_key.format(**kwargs)
        except KeyError:
            expected_kws = set(self.get_kwarg_names(scpi_key))
            missing_kws = expected_kws - set(kwargs.keys())
            raise TypeError(
                f'{paramattr._owned_name(owner)}() missing required positional argument(s) {str(missing_kws)[1:-1]}'
            )

        value_msg = query_func(self.query_fmt.format(key=expanded_scpi_key)).rstrip()
        return self.from_message(value_msg)

    def set(
        self,
        owner: HasParamAttrs,
        scpi_key: str,
        value: T,
        paramattr: Union[ParamAttr[T], None],
        kwargs: dict[str, Any] = {},
    ):
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
            raise ValueError('write_fmt needs to be set for key set operations')
        if self.write_func is None:
            raise ValueError('write_func needs to be set for key set operations')

        value_msg = self.to_message(value, paramattr)
        expanded_scpi_key = scpi_key.format(**kwargs)
        write_func = getattr(owner, self.write_func)
        write_func(self.write_fmt.format(key=expanded_scpi_key, value=value_msg))


class visa_keying(message_keying):
    """Decorates a :class:`labbench.VISADevice` (or subclass) to configure its use of the `key` argument
    in all :mod:`labbench.paramattr.property` or :mod:`labbench.paramattr.method` descriptors.

    Example:

        Configure `MyDevice` to format SCPI queries as `'{key}?'`, and SCPI writes as f'{key} {value}'::

            import labbench as lb


            @lb.visa_keying(query_fmt='{key}?', write_fmt='{key} {value}')
            class MyDevice(lb.VISADevice):
                pass

    """

    def __init__(
        self,
        *,
        query_fmt='{key}?',
        write_fmt='{key} {value}',
        remap={},
    ):
        super().__init__(
            query_fmt=query_fmt,
            write_fmt=write_fmt,
            remap=remap,
            write_func='write',
            query_func='query',
        )
