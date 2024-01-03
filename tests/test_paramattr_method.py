import labbench as lb
from labbench.testing import store_backend
from labbench import paramattr as attr
import pytest
from paramattr_tooling import eval_set_then_get, loop_closed_loop_set_gets, has_steps


@attr.register_key_argument(attr.kwarg.int("registered_channel", min=1, max=4))
@store_backend.key_store_adapter(defaults={"str_or_none": None, "str_cached": "cached string"})
class StoreTestDevice(store_backend.StoreTestDevice):
    LOOP_TEST_VALUES = {
        # make sure all test values conform to these general test values
        int: 5,
        float: 3.14,
        str: "hi",
        bool: True,
        object: None,
    }

    ARGUMENTS = {"channel": [1, 2]}

    # test both getting and setting
    bool_keyed = attr.method.bool(key="bool_keyed")
    int_keyed_unbounded = attr.method.int(key="int_keyed_unbounded")

    @attr.method.int(min=0, sets=False)
    def int_decorated_low_bound_getonly(self):
        return self.backend.setdefault("int_decorated_low_bound_getonly", 0)

    @attr.method.int(min=10, gets=False)
    def int_decorated_low_bound_setonly(self, set_value=lb.Undefined, *, channel=1):
        self.backend["int_decorated_high_bound_setonly"] = set_value

    str_or_none = attr.method.str(key="str_or_none", allow_none=True)
    str_cached = attr.method.str(key="str_cached", cache=True)
    any = attr.method.any(key="any", allow_none=True)

    str_keyed_with_arg = attr.method.str(key="str_with_arg_ch_{registered_channel}")

    @attr.kwarg.int(name="decorated_channel", min=1, max=4)
    @attr.method.str(allow_none=True)
    @attr.kwarg.float(name="bandwidth", min=10e3, max=100e6)
    def str_decorated_with_arg(self, set_value=lb.Undefined, *, decorated_channel, bandwidth):
        key = self.backend.get_backend_key(
            self,
            type(self).str_decorated_with_arg,
            {"decorated_channel": decorated_channel, "bandwidth": bandwidth},
        )

        if set_value is lb.Undefined:
            return self.backend.get(key, None)
        else:
            return self.backend.set(key, set_value)


def set_param(device, attr_name, value, arguments={}):
    param_method = getattr(device, attr_name)
    param_method(value, **arguments)


def get_param(device, attr_name, arguments={}):
    param_method = getattr(device, attr_name)
    return param_method(**arguments)


def set_then_get(device, attr_name, value_in, arguments={}):
    set_param(device, attr_name, value_in, arguments)
    return get_param(device, attr_name, arguments)


#
# Fixtures convert to arguments in test functions
#
@pytest.fixture(autouse=True, scope="module")
def labbench_fixture():
    lb.visa_default_resource_manager("@sim")
    lb.show_messages("info")
    lb.util.force_full_traceback(True)


@pytest.fixture()
def role_type():
    return lb.paramattr.method.Method


@pytest.fixture()
def opened_device():
    device = StoreTestDevice()
    device.open()
    yield device
    device.close()


@pytest.fixture()
def instantiated_device():
    device = StoreTestDevice()
    device.open()
    yield device
    device.close()


def test_cache(opened_device):
    # repeat to set->get to ensure proper caching
    eval_set_then_get(opened_device, "str_cached", set_then_get)
    result = eval_set_then_get(opened_device, "str_cached", set_then_get)

    assert result["get_count"] == 0, f'cache test - second "get" operation count'
    assert result["set_count"] == 2, f'cache test - second "get" operation count'


def test_keyed_argument_bounds(opened_device):
    TEST_VALUE = "text"

    with pytest.raises(ValueError):
        opened_device.str_keyed_with_arg(TEST_VALUE, registered_channel=0)

    opened_device.str_keyed_with_arg(TEST_VALUE, registered_channel=1)
    expected_key = (
        "str_with_arg_ch_{registered_channel}",
        frozenset({("registered_channel", 1)}),
    )
    assert opened_device.backend.values[expected_key] == TEST_VALUE


def test_decorated_argument_bounds(opened_device):
    TEST_VALUE = "text"
    with pytest.raises(ValueError):
        # channel too small
        opened_device.str_decorated_with_arg(TEST_VALUE, decorated_channel=0, bandwidth=50e6)

    with pytest.raises(ValueError):
        # bandwidth too small
        opened_device.str_decorated_with_arg(TEST_VALUE, decorated_channel=1, bandwidth=0)

    # valid channel and bandwidth
    test_kws = dict(decorated_channel=1, bandwidth=51e6)
    expected_key = ("str_decorated_with_arg", frozenset(test_kws.items()))

    opened_device.str_decorated_with_arg(TEST_VALUE, **test_kws)
    assert opened_device.backend.values[expected_key] == TEST_VALUE


def test_decorated_argument_with_default():
    with pytest.raises(TypeError):
        # the 'default' argument is only allowed on registering key arguments,
        # not for decorators
        class TestDevice(store_backend.StoreTestDevice):
            @attr.kwarg.float(name="bandwidth", default=10e3)
            def str_decorated_with_arg(self, set_value=lb.Undefined, *, bandwidth):
                pass


def test_all_get_sets(opened_device, role_type):
    loop_closed_loop_set_gets(opened_device, role_type, set_then_get)
