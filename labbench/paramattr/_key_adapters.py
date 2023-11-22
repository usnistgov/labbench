from ._bases import KeyAdapterBase, HasParamAttrs, ParamAttr
import string
from typing import Dict, List, Any


class message_keying(KeyAdapterBase):
    """Device class decorator that implements automatic API that triggers API messages for labbench properties.

    Example usage:

    ```python
        import labbench as lb

        @lb.message_keying(query_fmt='{key}?', write_fmt='{key} {value}', query_func='get', write_func='set')
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

    _formatter = string.Formatter()

    def __init__(
        self,
        *,
        query_fmt=None,
        write_fmt=None,
        write_func=None,
        query_func=None,
        remap={},
        key_arguments: Dict[Any, ParamAttr] = {},
        strict_arguments: bool = False,
    ):
        super().__init__(key_arguments=key_arguments, strict_arguments=strict_arguments)

        self.query_fmt = query_fmt
        self.write_fmt = write_fmt
        self.write_func = write_func
        self.query_func = query_func

        if len(remap) == 0:
            self.value_map = {}
            self.message_map = {}
            return

        # ensure str type for messages; keys can be arbitrary python type
        if not all(isinstance(v, __builtins__["str"]) for v in remap.values()):
            raise TypeError("all values in remap dict must have type str")

        self.value_map = remap

        # create the reverse mapping
        self.message_map = __builtins__["dict"](zip(remap.values(), remap.keys()))

        # and ensure all values are unique
        if len(self.message_map) != len(self.value_map):
            raise ValueError("'remap' has duplicate values")

    def get_key_arguments(self, s: str) -> List[str]:
        """returns an argument list based on f-string style curly-brace formatting tokens.

        Example:

            ```python

            # input
            print(key_adapter.get_key_arguments('CH{channel}:SV:CENTERFrequency'))
            ['channel']
            ```
        """
        return [tup[1] for tup in self._formatter.parse(s) if tup[1] is not None]

    def from_message(self, msg):
        return self.message_map.get(msg, msg)

    def to_message(self, value):
        return self.value_map.get(value, value)

    def get(
        self,
        owner: HasParamAttrs,
        scpi_key: str,
        paramattr: ParamAttr = None,
        arguments: Dict[str, Any] = {},
    ):
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
        query_func = getattr(owner, self.query_func)
        try:
            expanded_scpi_key = scpi_key.format(**arguments)
        except KeyError:
            expected_kws = set(self.get_key_arguments(scpi_key))
            missing_kws = expected_kws - set(arguments.keys())
            raise TypeError(
                f"{paramattr._owned_name(owner)}() missing required positional argument(s) {str(missing_kws)[1:-1]}"
            )

        value_msg = query_func(self.query_fmt.format(key=expanded_scpi_key)).rstrip()
        return self.from_message(value_msg)

    def set(
        self,
        owner: HasParamAttrs,
        scpi_key: str,
        value,
        attr: ParamAttr = None,
        arguments: Dict[str, Any] = {},
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
            raise ValueError("write_fmt needs to be set for key set operations")
        if self.write_func is None:
            raise ValueError("write_func needs to be set for key set operations")

        value_msg = self.to_message(value)
        expanded_scpi_key = scpi_key.format(**arguments)
        write_func = getattr(owner, self.write_func)
        write_func(self.write_fmt.format(key=expanded_scpi_key, value=value_msg))


class visa_keying(message_keying):
    """Device class decorator that automates SCPI command string interactions for labbench properties.

    Example usage:

    ```python
        import labbench as lb

        @lb.visa_keying(query_fmt='{key}?', write_fmt='{key} {value}')
        class MyDevice(lb.VISADevice):
            pass
    ```

    This causes access to property traits defined with 'key=' to interact with the
    VISA instrument. By default, messages in VISADevice objects trigger queries
    with the `'{key}?'` format, and writes formatted as f'{key} {value}'.
    """

    def __init__(
        self,
        *,
        query_fmt="{key}?",
        write_fmt="{key} {value}",
        remap={},
        key_arguments: Dict[str, ParamAttr] = {},
    ):
        super().__init__(
            query_fmt=query_fmt,
            write_fmt=write_fmt,
            remap=remap,
            write_func="write",
            query_func="query",
            key_arguments=key_arguments,
        )
