import labbench as lb
from labbench.testing import store_backend
from labbench import paramattr as attr
import pytest
from paramattr_tooling import eval_set_then_get, loop_closed_loop_set_gets, has_steps


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

    # test both getting and setting
    bool_keyed = attr.property.bool(key="bool_keyed")
    int_keyed_unbounded = attr.property.int(key="int_keyed_unbounded")

    @attr.property.int(min=0, sets=False)
    def int_decorated_low_bound_getonly(self):
        return self.backend.setdefault("int_decorated_low_bound_getonly", 0)

    @attr.property.int(min=10, gets=False)
    def int_decorated_low_bound_setonly(self, set_value=lb.Undefined, *, channel=1):
        self.backend["int_decorated_high_bound_setonly"] = set_value

    str_or_none = attr.property.str(key="str_or_none", allow_none=True)
    str_cached = attr.property.str(key="str_cached", cache=True)
    any = attr.property.any(key="any", allow_none=True)


def set_param(device, attr_name, value, arguments={}):
    if len(arguments) > 0:
        raise ValueError("properties do not accept arguments")
    setattr(device, attr_name, value)


def get_param(device, attr_name, arguments={}):
    if len(arguments) > 0:
        raise ValueError("properties do not accept arguments")
    return getattr(device, attr_name)


def set_then_get(device, attr_name, value_in, arguments={}):
    set_param(device, attr_name, value_in, arguments)
    return get_param(device, attr_name, arguments)


#
# Fixtures that convert to arguments in test functions
#
@pytest.fixture(autouse=True, scope="module")
def labbench_fixture():
    lb.visa_default_resource_manager("@sim")
    lb.show_messages("info")
    lb.util.force_full_traceback(True)


@pytest.fixture()
def role_type():
    return lb.paramattr.property.Property


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


#
# The tests
#
def test_basic_get(opened_device):
    _ = opened_device.any


def test_basic_set(opened_device):
    opened_device.any = 5
    assert opened_device.any == 5


def test_cache(opened_device):
    # repeat to set->get to ensure proper caching
    eval_set_then_get(opened_device, "str_cached", set_then_get)
    result = eval_set_then_get(opened_device, "str_cached", set_then_get)

    assert result["get_count"] == 0, f'cache test - second "get" operation count'

    assert result["set_count"] == 2, f'cache test - second "get" operation count'


def test_all_get_sets(opened_device, role_type):
    loop_closed_loop_set_gets(opened_device, role_type, set_then_get)
