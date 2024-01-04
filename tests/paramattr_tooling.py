import labbench as lb
from labbench import paramattr as attr


def has_steps(attr: attr.ParamAttr):
    return getattr(attr, "step", None) is not None

def eval_access(device: lb.Device, attr_name, arguments: dict = {}) -> dict:
    attr_def = getattr(type(device), attr_name)
    backend_key = device.backend.get_backend_key(device, attr_def, arguments)
    notifications = [n for n in device.backend.notifications if n["name"] == attr_name]

    return {
        "get_count": device.backend.get_count[backend_key],
        "set_count": device.backend.set_count[backend_key],
        "notifications": notifications,
    }

def eval_set_then_get(
    device, attr_name, single_set_get: callable, value_in=lb.Undefined, arguments={}
):
    attr_def = getattr(type(device), attr_name)

    if value_in is lb.Undefined:
        value_in = device.LOOP_TEST_VALUES[attr_def._type]

    value_out = single_set_get(device, attr_name, value_in, arguments)
    access = eval_access(device, attr_name, arguments)

    return dict(
        value_in=value_in,
        value_out=value_out,
        **access
    )


def loop_closed_loop_set_gets(
    device: lb.Device, role_type: type[lb.paramattr.ParamAttr], single_set_get: callable
):
    def want_to_set_get(attr_def):
        return (
            isinstance(attr_def, role_type)
            and attr_def.sets
            and attr_def.gets
            and not hasattr(lb.Device, attr_def.name)
            and not has_steps(attr_def)  # steps can make set != get
        )

    attrs = {
        name: attr_def
        for name, attr_def in device.get_attr_defs().items()
        if want_to_set_get(attr_def)
    }

    for attr_name, attr_def in attrs.items():
        if isinstance(attr_def, attr.method.Method):
            # skip methods with arguments for now
            if len(attr_def.get_key_arguments(type(device))) > 0:
                continue
        test_name = f'{attr_def.ROLE} "{attr_name}"'
        has_reduced_access_count = attr_def.cache or isinstance(attr_def, attr.value.Value)

        device.backend.clear_counts()

        result = eval_set_then_get(device, attr_name, single_set_get)

        assert (
            result["value_in"] == result["value_out"]
        ), f"{test_name} - set-get input and output values"

        assert (
            len(result["notifications"]) == 1 if has_reduced_access_count else 2
        ), f"{test_name} - callback notification count"

        if isinstance(attr_def, attr.value.Value):
            if len(result["notifications"]) > 1:
                assert (
                    result["notifications"][0]["old"] == attr_def.default
                ), f"{test_name} - callback notification prior value for 'set'"
        else:
            assert (
                result["notifications"][0]["old"] == lb.Undefined
            ), f"{test_name} - callback notification prior value for 'set'"

        if not attr_def.cache and len(result["notifications"]) > 1:
            assert (
                result["notifications"][1]["old"] == result["value_in"]
            ), f"{test_name} - callback notification prior value for 'get'"

        # make sure there weren't any unecessary extra 'get' operations
        assert (
            result["get_count"] == 0 if has_reduced_access_count else 1
        ), f'{test_name} - "get" notification count'
        assert (
            result["set_count"] == 0 if isinstance(attr_def, attr.value.Value) else 1
        ), f'{test_name} - "set" notification count'
