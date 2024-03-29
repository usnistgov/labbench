import inspect
from numbers import Number
from pathlib import Path

import pytest
from paramattr_tooling import eval_set_then_get, has_steps, loop_closed_loop_set_gets

import labbench as lb
from labbench import paramattr as attr
from labbench.testing import store_backend


@store_backend.key_adapter(
    defaults={'str_or_none': None, 'str_cached': 'cached string'}
)
class StoreTestDevice(store_backend.StoreTestDevice):
    LOOP_TEST_VALUES = {
        # make sure all test values conform to these general test values
        int: 5,
        float: 3.14,
        str: 'moose',
        bool: True,
        object: None,
        dict: dict(a=4, b=5, c=6),
        tuple: (4, 5, 6),
        list: [7, 8, 9],
        Path: Path('.'),
    }

    # test both getting and setting
    bool: bool = attr.value.bool(default=True)
    int_with_default = attr.value.int(default=47)
    int_no_default = attr.value.int(default=None, allow_none=True)

    # floats
    float_low_bounded = attr.value.float(default=2, min=1)
    float_high_bounded = attr.value.float(default=2, max=4)
    float_none_bounded = attr.value.float(default=3, allow_none=True, max=4, min=1)
    float_stepped = attr.value.float(default=0, step=3)

    # strings
    str_explicit_none = attr.value.str(default=None, allow_none=True)
    str_allow_none = attr.value.str(default=None, allow_none=True)
    str_cached = attr.value.str(default='47', cache=True)
    str = attr.value.str(default='squirrel')
    any = attr.value.any(default='empty', allow_none=True)
    str_with_only = attr.value.str(default='moose', only=('moose', 'squirrel'))
    str_no_case_with_only = attr.value.str(
        default='moose', only=('MOOSE', 'squirrel'), case=False
    )

    # iterables
    tuple = attr.value.tuple((1, 2, 3))
    dict = attr.value.dict(dict(a=1, b=2, c=3))
    list = attr.value.list([4, 5, 6])

    path_exists = attr.value.Path(__file__, must_exist=True)
    any_path = attr.value.Path('132512412424')

    # misc
    uri = attr.value.NetworkAddress('127.0.0.1', accept_port=False)
    uri_port = attr.value.NetworkAddress('127.0.0.1')

class MixIn(attr.HasParamAttrs):
    extra = attr.value.int(default=5)

class AdjustedTestDevice(StoreTestDevice):
    """adjusted values in inherited devices"""

    bool: bool = attr.value.bool(default=False)


class RequiredParametersTestDevice(lb.Device):
    required_str: str = attr.value.str(cache=True)
    required_str_allow_none: str = attr.value.str(cache=True, allow_none=True)


def change_case(s: str):
    alt = s.upper()
    if alt == s:
        alt = s.lower()
    return alt


def set_param(device, attr_name, value, arguments={}):
    if len(arguments) > 0:
        attr_def = attr.get_class_attrs(device)[attr_name]
        raise ValueError(f'{attr_def.ROLE} do not accept arguments')
    setattr(device, attr_name, value)


def get_param(device, attr_name, arguments={}):
    if len(arguments) > 0:
        attr_def = attr.get_class_attrs(device)[attr_name]
        raise ValueError(f'{attr_def.ROLE} properties do not accept arguments')
    return getattr(device, attr_name)


def set_then_get(device, attr_name, value_in, arguments={}):
    set_param(device, attr_name, value_in, arguments)
    return get_param(device, attr_name, arguments)


#
# Fixtures that convert to arguments in test functions
#
@pytest.fixture(autouse=True, scope='module')
def labbench_fixture():
    lb.visa_default_resource_manager('@sim')
    lb.show_messages('info')
    lb.util.force_full_traceback(True)


@pytest.fixture
def role_type():
    return lb.paramattr.value.Value


@pytest.fixture
def opened_device():
    device = StoreTestDevice()
    device.open()
    yield device
    device.close()

@pytest.fixture
def opened_mixin_device():
    class Device(StoreTestDevice, MixIn):
        pass
    device = Device()
    device.open()
    yield device
    device.close()

@pytest.fixture
def opened_adjusted_device():
    device = AdjustedTestDevice()
    device.open()
    yield device
    device.close()


@pytest.fixture
def instantiated_device():
    device = StoreTestDevice()
    device.open()
    yield device
    device.close()


#
# The tests
#
def test_basic_get(opened_device):
    get_param(opened_device, 'any')


def test_basic_set(opened_device):
    opened_device.any = 5
    assert opened_device.any == 5


def test_cache(opened_device):
    # repeat to set->get to ensure proper caching
    eval_set_then_get(opened_device, 'str_cached', set_then_get)
    result = eval_set_then_get(opened_device, 'str_cached', set_then_get)
    assert len(result['notifications']) == 2, 'notification count for cached string'


def test_paths(opened_device):
    with pytest.raises(OSError):
        opened_device.path_exists = '.../9815h1lk35jkl13j53'


def test_default_types(opened_device, role_type):
    for attr_def in opened_device.get_attr_defs().values():
        if not isinstance(attr_def, role_type):
            continue

        value = getattr(opened_device, attr_def.name)

        if attr_def.allow_none:
            allow_types = (type(None), attr_def._type)
        else:
            allow_types = (attr_def._type,)

        if issubclass(attr_def._type, Number):
            allow_types = allow_types + (Number,)

        assert issubclass(type(value), allow_types), f'pythonic type of {attr_def.name}'


def test_default_values(opened_device, role_type):
    for attr_def in opened_device.get_attr_defs().values():
        if not isinstance(attr_def, role_type):
            continue

        value = getattr(opened_device, attr_def.name)
        if value is None:
            assert value == attr_def.default, f'default None value of {attr_def.name}'
        else:
            assert (
                attr_def.validate(attr_def.default) == value
            ), f'initial value type of {attr_def.name}'

def test_mixin_default_types(opened_mixin_device, role_type):
    for attr_def in opened_mixin_device.get_attr_defs().values():
        if not isinstance(attr_def, role_type):
            continue

        value = getattr(opened_mixin_device, attr_def.name)

        if attr_def.allow_none:
            allow_types = (type(None), attr_def._type)
        else:
            allow_types = (attr_def._type,)

        if issubclass(attr_def._type, Number):
            allow_types = allow_types + (Number,)

        assert issubclass(type(value), allow_types), f'pythonic type of {attr_def.name}'


def test_mixin_default_values(opened_mixin_device, role_type):
    for attr_def in opened_mixin_device.get_attr_defs().values():
        if not isinstance(attr_def, role_type):
            continue

        value = getattr(opened_mixin_device, attr_def.name)
        if value is None:
            assert value == attr_def.default, f'default None value of {attr_def.name}'
        else:
            assert (
                attr_def.validate(attr_def.default) == value
            ), f'initial value type of {attr_def.name}'

def test_constructor():
    DEFAULT_VALUE = 4

    class Device(lb.Device):
        number: int = attr.value.int(default=DEFAULT_VALUE)

    # check Device signature
    params = inspect.signature(Device).parameters

    assert tuple(params.keys()) == ('number',), 'constructor keyword argument names'

    defaults = [p.default for p in params.values()]
    assert tuple(defaults) == (DEFAULT_VALUE,)


def test_adjusted_constructor():
    OLD_DEFAULT = 0
    NEW_DEFAULT = 1

    class Parent(lb.Device):
        number: int = attr.value.int(OLD_DEFAULT)

    class Child(Parent):
        number: int = attr.value.int(default=NEW_DEFAULT, inherit=True)

    #
    assert Parent.number.default == OLD_DEFAULT
    assert Child.number.default == NEW_DEFAULT

    # check Device signature
    params = inspect.signature(Child).parameters

    assert tuple(params.keys()) == ('number',), 'constructor keyword argument names'

    defaults = [p.default for p in params.values()]
    assert tuple(defaults) == (NEW_DEFAULT,)

    d = Child()
    assert d.number == NEW_DEFAULT


def test_adjusted_constructor_posarg():
    OLD_DEFAULT = 0
    NEW_DEFAULT = 1

    class Parent(lb.Device):
        number: int = attr.value.int(OLD_DEFAULT)

    class Child(Parent):
        number: int = attr.value.int(NEW_DEFAULT, inherit=True)

    #
    assert Parent.number.default == OLD_DEFAULT
    assert Child.number.default == NEW_DEFAULT

    # check Device signature
    params = inspect.signature(Child).parameters

    assert tuple(params.keys()) == ('number',), 'constructor keyword argument names'

    defaults = [p.default for p in params.values()]
    assert tuple(defaults) == (NEW_DEFAULT,)

    d = Child()
    assert d.number == NEW_DEFAULT


def test_inherited_constructor_without_default():
    OLD_DEFAULT = 0

    class Parent(lb.Device):
        number: int = attr.value.int(OLD_DEFAULT)

    with pytest.raises(TypeError):

        class Child(Parent):
            number: int = attr.value.int(inherit=True)


def test_inherited_defaults():
    HELP_MSG = 'parent help'

    class Parent(lb.Device):
        number: int = attr.value.int(0, help=HELP_MSG)

    class Child(Parent):
        number: int = attr.value.int(1, inherit=True)

    assert Child.number.help == HELP_MSG


def test_only(opened_device):
    # low bound
    expected_valid = type(opened_device).str_with_only.only[0]
    alt_case = change_case(expected_valid)

    opened_device.str_with_only = expected_valid
    with pytest.raises(ValueError):
        opened_device.str_with_only = 'boris'

    with pytest.raises(ValueError):
        opened_device.str_with_only = alt_case

    # with string case
    expected_valid = type(opened_device).str_no_case_with_only.only[0]
    alt_case = change_case(expected_valid)

    opened_device.str_no_case_with_only = expected_valid
    with pytest.raises(ValueError):
        opened_device.str_no_case_with_only = 'boris'
    opened_device.str_no_case_with_only = alt_case


def test_numeric_bounds(opened_device):
    # float_low_bounded
    lo_bound = type(opened_device).float_low_bounded.min
    with pytest.raises(ValueError):
        opened_device.float_low_bounded = lo_bound - 1
    opened_device.float_low_bounded = lo_bound + 1

    # float_high_bounded
    hi_bound = type(opened_device).float_high_bounded.max
    with pytest.raises(ValueError):
        opened_device.float_high_bounded = hi_bound + 1
    opened_device.float_high_bounded = hi_bound - 1

    # float_none_bounded
    opened_device.float_none_bounded = None


def test_iterables(opened_device):
    with pytest.raises(AttributeError):
        opened_device.tuple = 4


def test_numeric_casting(opened_device):
    # float
    value_in = '3.91'
    expected_out = float(value_in)
    opened_device.float_low_bounded = value_in
    value_out = opened_device.float_low_bounded
    assert value_out == expected_out, 'string to float casting'

    # float
    value_in = '-48'
    expected_out = int(value_in)
    opened_device.int_no_default = value_in
    value_out = opened_device.int_no_default
    assert value_out == expected_out, 'string to float casting'


def test_str_casting(opened_device):
    # float
    value_in = -48
    expected_out = str(value_in)
    opened_device.str = value_in
    value_out = opened_device.str
    assert value_out == expected_out, 'string to float casting'


def test_network_address(opened_device):
    with pytest.raises(ValueError):
        opened_device.uri = '?!?!'

    with pytest.raises(ValueError):
        # expect an error on this one when port is supplied
        opened_device.uri = '127.0.0.1:5555'

    opened_device.uri_port = '127.0.0.1'  # ipv4
    opened_device.uri_port = 'nist.gov:1234'  # domain name with port

    with pytest.raises(ValueError):
        opened_device.uri_port = '127.0.0.1:hello'  # bad port number

    opened_device.uri = '::ffff:192.0.2.128'  # ipv6
    opened_device.uri_port = '[::ffff:192.0.2.128]:1234'


def test_numeric_step(opened_device):
    # rounding tests (step is not None)
    opened_device.float_stepped = 3
    assert opened_device.float_stepped == 3.0
    opened_device.float_stepped = 2
    assert opened_device.float_stepped == 3.0
    opened_device.float_stepped = 4
    assert opened_device.float_stepped == 3.0
    opened_device.float_stepped = 1.6
    assert opened_device.float_stepped == 3.0
    opened_device.float_stepped = -2
    assert opened_device.float_stepped == -3.0
    opened_device.float_stepped = -1
    assert opened_device.float_stepped == 0


def test_device_initialization(instantiated_device, role_type):
    def should_test_this_attr(attr_def: attr.ParamAttr):
        return (
            attr_def.name in type(instantiated_device).__annotations__
            and isinstance(attr_def, role_type)
            and attr_def.sets
            and not has_steps(attr_def)
        )

    cls = type(instantiated_device)

    for attr_def in instantiated_device.get_attr_defs().values():
        if not should_test_this_attr(attr_def):
            continue

        test_name = f'{attr_def.ROLE} "{attr_def.name}"'

        value_in = instantiated_device.LOOP_TEST_VALUES[attr_def._type]

        instantiated_device = cls(**{attr_def.name: value_in})

        with instantiated_device:
            value_out = getattr(instantiated_device, attr_def.name)
            assert (
                value_in == value_out
            ), f'{test_name} - initialize default values from Device constructor'


def test_doc_access(opened_device):
    attr_descs = attr.get_class_attrs(opened_device)

    for name, attr_desc in attr_descs.items():
        attr_desc.doc_params()
        attr_desc.doc_params(as_argument=True)


def test_all_get_sets(opened_device, role_type):
    loop_closed_loop_set_gets(opened_device, role_type, set_then_get)


def test_adjusted_value_paramattr(opened_adjusted_device):
    assert opened_adjusted_device.bool == False


def test_requried_parameter_instantiation():
    with pytest.raises(TypeError):
        RequiredParametersTestDevice()

    RequiredParametersTestDevice(required_str='hi', required_str_allow_none=None)
