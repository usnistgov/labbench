import pytest
from paramattr_tooling import eval_access, eval_set_then_get, loop_closed_loop_set_gets

import labbench as lb
from labbench import paramattr as attr
from labbench.testing import store_backend


@attr.method_kwarg.int('registered_channel', min=1, max=4)
@store_backend.key_adapter(
    defaults={'str_or_none': None, 'str_cached': 'cached string'}
)
class StoreTestDevice(store_backend.StoreTestDevice):
    LOOP_TEST_VALUES = {
        # make sure all test values conform to these general test values
        int: 5,
        float: 3.14,
        str: 'hi',
        bool: True,
        object: None,
    }

    ARGUMENTS = {'channel': [1, 2]}

    # test both getting and setting
    bool_keyed = attr.method.bool(key='bool_keyed')
    int_keyed_unbounded = attr.method.int(key='int_keyed_unbounded')

    @attr.method.int(min=0, sets=False)
    def int_decorated_low_bound_getonly(self):
        ret = self.backend.get('int_decorated_low_bound_getonly', 0)
        return ret

    @attr.method.int(min=10, gets=False).setter
    def int_decorated_low_bound_setonly(self, new_value=lb.Undefined, *, channel=1):
        self.backend.set('int_decorated_high_bound_setonly', new_value)

    # test "get_on_set" keyword
    int_keyed_get_on_set = attr.method.int(key='int_keyed_unbounded', get_on_set=True)

    @attr.method.int(get_on_set=True)
    def int_decorated_get_on_set(self):
        return self.backend.get('int_decorated_get_on_set', 0)

    @int_decorated_get_on_set.setter
    def _(self, new_value):
        self.backend.set('int_decorated_get_on_set', int(new_value))

    # @attr.method.int(get_on_set=True)
    # def int_decorated_get_on_set(self):
    #     return self.backend.get('int_decorated_get_on_set', 0)

    # def int_decorated_get_on_set(self, new_value: int):
    #     self.backend.set('int_decorated_get_on_set', int(new_value))

    str_or_none = attr.method.str(key='str_or_none', allow_none=True)
    str_cached = attr.method.str(key='str_cached', cache=True)
    any = attr.method.any(key='any', allow_none=True)


def set_param(device, attr_name, value, arguments={}):
    param_method = getattr(device, attr_name)
    param_method(value, **arguments)


def get_param(device, attr_name, arguments={}):
    param_method = getattr(device, attr_name)
    return param_method(**arguments)


def set_then_get(device, attr_name, value_in, arguments={}):
    set_param(device, attr_name, value_in, arguments)
    return get_param(device, attr_name, arguments)


def kwargs(locals_: dict) -> dict:
    # kwargs from locals()
    locals_.pop('self', None)
    locals_.pop('set_value', None)
    return locals_


#
# Fixtures convert to arguments in test functions
#
@pytest.fixture(autouse=True, scope='module')
def labbench_fixture():
    lb.visa_default_resource_manager('@sim')
    lb.show_messages('info')
    lb.util.force_full_traceback(True)


@pytest.fixture
def role_type():
    return lb.paramattr.method.Method


@pytest.fixture
def opened_device():
    device = StoreTestDevice()
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
def test_cache(opened_device: StoreTestDevice):
    # repeat to set->get to ensure proper caching
    result = eval_set_then_get(opened_device, 'str_cached', set_then_get)

    assert (
        result['get_count'] == 0
    ), f"cache test - first 'get' operation count (got {result['get_count']})"
    assert (
        result['set_count'] == 1
    ), f"cache test - first 'set' operation count (got {result['set_count']})"

    result = eval_set_then_get(opened_device, 'str_cached', set_then_get)
    assert (
        result['get_count'] == 0
    ), f"cache test - second 'get' operation count (got {result['get_count']})"
    assert (
        result['set_count'] == 2
    ), f"cache test - second 'set' operation count (got {result['set_count']})"


def test_get_on_set_keyed(opened_device: StoreTestDevice):
    attr_name = 'int_keyed_get_on_set'
    arguments = {'registered_channel': 1}
    bound_method = getattr(opened_device, attr_name)
    bound_method(5, **arguments)
    access = eval_access(opened_device, attr_name, arguments)

    assert access['get_count'] == 1, 'verify 1 get operation triggered by set'
    assert access['set_count'] == 1, 'verify 1 set operation'


def test_get_on_set_decorated(opened_device: StoreTestDevice):
    attr_name = 'int_decorated_get_on_set'
    bound_method = getattr(opened_device, attr_name)
    bound_method(5)

    # assert bound_method() == 5.5, 'verify get operation retrieves the expected value'

    access = eval_access(opened_device, attr_name)
    assert access['get_count'] == 1, 'verify 1 get operation triggered by set'
    assert access['set_count'] == 1, 'verify 1 set operation'


def test_disabled_get(opened_device: StoreTestDevice):
    opened_device.int_decorated_low_bound_setonly(10)

    with pytest.raises(AttributeError):
        opened_device.int_decorated_low_bound_setonly()


def test_disabled_get(opened_device: StoreTestDevice):
    # the decorated function does not include a new_value, so we don't test it
    opened_device.int_decorated_low_bound_getonly()


def test_keyed_argument_bounds():
    @attr.method_kwarg.int('channel', min=1, max=4)
    class Device(store_backend.StoreTestDevice):
        method = attr.method.str(key='command_{channel}')

    device = Device()
    device.open()

    # bounds checking on keyword arguments
    with pytest.raises(ValueError):
        # channel too small
        device.method('value', channel=0)

    # normal set/get behavior
    TEST_VALUE = 'text'
    TEST_KWS = {'channel': 1}
    EXPECT_KEY = (Device.method.key, frozenset(TEST_KWS.items()))

    device.method(TEST_VALUE, **TEST_KWS)
    assert device.backend.values[EXPECT_KEY] == TEST_VALUE


def test_decorated_argument_bounds():
    class Device(store_backend.StoreTestDevice):
        @attr.method.str(allow_none=True)
        @attr.method_kwarg.int(name='channel', min=1, max=4)
        @attr.method_kwarg.float(name='bandwidth', min=10e3, max=100e6)
        def method(self, *, channel, bandwidth):
            key = self.backend.get_backend_key(
                self, type(self).method, kwargs(locals())
            )
            return self.backend.get(key, None)

        @method.setter
        def _(self, set_value, /, *, channel, bandwidth):
            key = self.backend.get_backend_key(
                self, type(self).method, kwargs(locals())
            )
            return self.backend.set(key, set_value)

    device = Device()
    device.open()

    TEST_VALUE = 'text'

    with pytest.raises(ValueError):
        # channel too small
        device.method(TEST_VALUE, channel=0, bandwidth=50e6)

    with pytest.raises(ValueError):
        # bandwidth too small
        device.method(TEST_VALUE, channel=1, bandwidth=0)

    # valid channel and bandwidth
    TEST_KWS = dict(channel=1, bandwidth=51e6)
    EXPECT_KEY = ('method', frozenset(TEST_KWS.items()))

    device.method(TEST_VALUE, **TEST_KWS)
    assert device.backend.values[EXPECT_KEY] == TEST_VALUE


def test_decorated_argument_with_default():
    # the 'default' argument is only allowed on registering key arguments,
    # not for decorators

    with pytest.raises(TypeError):

        class _(store_backend.StoreTestDevice):
            @attr.method_kwarg.float(name='bandwidth', default=10e3)
            def method(self, *, bandwidth):
                pass


def test_kwarg_decorator_above_method():
    # the 'default' argument is only allowed on registering key arguments,
    # not for decorators
    with pytest.raises(TypeError):

        class _(store_backend.StoreTestDevice):
            @attr.method_kwarg.float(name='bandwidth')
            @attr.method.str()
            def method(self, *, bandwidth):
                pass


def test_all_get_sets(opened_device, role_type):
    loop_closed_loop_set_gets(opened_device, role_type, set_then_get)
