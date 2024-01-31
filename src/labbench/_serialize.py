"""functions and CLI tools for mapping labbench objects onto config directories"""

import inspect
import os
from numbers import Number
from pathlib import Path

from . import paramattr as attr
from . import util
from ._rack import Rack, import_as_rack, update_parameter_dict

# some packages install ruamel_yaml, others ruamel.yaml. fall back to ruamel_yaml in case ruamel.yaml fails
# using ruamel yaml instead of pyyaml because it allows us to place comments for human readability

try:
    import ruamel.yaml as ruamel_yaml
except ModuleNotFoundError:
    import ruamel_yaml

_yaml = ruamel_yaml.YAML()
_yaml.indent(mapping=4, sequence=4)

RACK_CONFIG_FILENAME = 'config.yaml'
EMPTY = inspect.Parameter.empty

# csv files that define sequences for function execution
INDEX_COLUMN_NAME = 'step_name'

_FIELD_SOURCE = 'source'
_FIELD_DEVICES = 'devices'
_FIELD_KEYWORD_DEFAULTS = 'default_arguments'


def _yaml_comment_out(cm, key):
    """comment out the line containing the item with the specified key"""

    from ruamel_yaml.error import CommentMark
    from ruamel_yaml.tokens import CommentToken

    cm.ca.items.setdefault(key, [None, [], None, None])
    cm.ca.items[key][1] = [CommentToken('# ', CommentMark(0), None)]


def _quote_strings_recursive(cm):
    """apply quotes to dict values that have str type"""

    from ruamel_yaml.scalarstring import DoubleQuotedScalarString as quote

    ret = dict()

    for k, v in cm.items():
        if isinstance(v, str):
            ret[k] = quote(v)
        elif isinstance(v, dict):
            ret[k] = _quote_strings_recursive(v)

    return ret


def _search_method_parameters(rack_cls_or_obj):
    """finds parameters of methods in rack_cls and its children recursively.

    Arguments:
        A subclass of Rack

    Returns:
        {<name (str)>: <(inspect.Parameter)>}, {<name (str)>: {<short_name (str)>: <callable method>>}}
    """

    parameters = {}
    methods = {}

    for rack in rack_cls_or_obj._owners.values():
        # recurse into child racks
        if not isinstance(rack, Rack):
            continue

        p, m = _search_method_parameters(rack)

        update_parameter_dict(parameters, p)

        for name, callables in m.items():
            methods.setdefault(name, {}).update(callables)

    if inspect.isclass(rack_cls_or_obj):
        rack = rack_cls_or_obj()
    else:
        rack = rack_cls_or_obj

    for method in rack._methods.values():
        p = dict(list(method.extended_signature().parameters.items()))  # skip 'self'

        update_parameter_dict(parameters, p)

        short_names = list(method.__call__.__signature__.parameters.keys())[
            1:
        ]  # skip 'self'
        long_names = list(p.keys())  # extended_signature() does not include 'self'
        for short_name, long_name in zip(short_names, long_names):
            methods.setdefault(long_name, {})[short_name] = method

    return parameters, methods


def _adjust_sequence_defaults(rack_cls: type, defaults_in: dict, **override_defaults):
    """adjusts the method argument parameters in the Rack subclass `cls` according to config file"""
    params, methods = _search_method_parameters(rack_cls)

    defaults_in = dict(defaults_in, **override_defaults)

    # sequences = [
    #     obj for obj in rack_cls._ownables.values() if isinstance(obj, Sequence)
    # ]

    for name, default in dict(defaults_in).items():
        if default == params[name].default:
            del defaults_in[name]
            continue

        annot = params[name].annotation
        if name not in methods:
            clsname = rack_cls.__qualname__
            raise KeyError(
                f"'{name}' is not a keyword argument of any method of '{clsname}'"
            )

        elif annot is not EMPTY and not isinstance(default, annot):
            if isinstance(default, Number) and issubclass(annot, Number):
                # allow casting for numbers
                default = annot(default)

            else:
                raise TypeError(
                    f"the keyword default configuration at key '{name}' with value "
                    f"'{default}' conflicts with annotated type '{annot.__qualname__}'"
                )

        # update the call signature
        for short_name, method in methods[name].items():
            method.set_kwdefault(short_name, default)

    if len(defaults_in) > 0:
        util.logger.debug(f'applied defaults {defaults_in}')


def write_table_stub(rack: Rack, name: str, path: Path, with_defaults: bool = False):
    """forms an empty DataFrame containing the headers needed for Sequence
    csv files.

    Arguments:
        rack: the Rack instance containing the sequence
        path: base directory where the csv should be saved
        with_defaults: whether to include columns when method parameters have defaults

    """

    import pandas as pd

    func = getattr(rack, name)
    if not callable(func):
        raise TypeError(f'{func} is not callable')
    try:
        sig = inspect.signature(func)
    except ValueError:
        sig = inspect.signature(func.__call__)

    # pick out the desired column names based on with_defaults
    params = sig.parameters
    columns = [
        name
        for name, param in list(params.items())[1:]
        if with_defaults or param.default is EMPTY
    ]

    if with_defaults:
        defaults = [
            [
                None if params[name].default is EMPTY else params[name].default
                for name in columns
            ]
        ]
    else:
        defaults = []

    df = pd.DataFrame(defaults, columns=columns)
    df.index.name = INDEX_COLUMN_NAME
    df.to_csv(path)
    util.logger.debug(f'writing csv template to {path!r}')


def _map_method_defaults(rack_cls):
    params, _ = _search_method_parameters(rack_cls)
    cm = ruamel_yaml.comments.CommentedMap(
        {
            k: (None if param.default is EMPTY else param.default)
            for k, param in params.items()
        }
    )

    for i, k in enumerate(list(cm.keys())[::-1]):
        if params[k].default is EMPTY:
            # comment out lines with no default to distinguish
            # from None value (which is an empty line in yaml)
            _yaml_comment_out(cm, k)

        if params[k].annotation is not EMPTY:
            # comment the type
            cm.yaml_add_eol_comment(key=k, comment=str(params[k].annotation.__name__))

    return cm


def _map_devices(cls):
    cm = ruamel_yaml.comments.CommentedMap()

    for dev_name, dev in cls._devices.items():
        cm[dev_name] = ruamel_yaml.comments.CommentedMap()
        cm.yaml_set_comment_before_after_key(
            dev_name,
            before='\n',
        )

        for value_name in attr.list_value_attrs(dev):
            if not attr.get_class_attrs(dev)[value_name].sets:
                # only show settable traits
                continue

            cm[dev_name][value_name] = getattr(dev, value_name)
            trait = getattr(type(dev), value_name)

            if trait.help:
                comment = '\n' + trait.help
            else:
                comment = '\n(define this value with help to autogenerate this comment)'

            cm[dev_name].yaml_set_comment_before_after_key(
                value_name, before=comment, indent=8
            )

            if trait.type is not None:
                comment = trait.type.__name__
                if trait.label:
                    comment = f'{comment} ({trait.label})'

                cm[dev_name].yaml_add_eol_comment(key=value_name, comment=comment)

    return cm


def dump_rack(
    rack: Rack,
    output_path: Path,
    sourcepath: Path,
    pythonpath: Path = None,
    exist_ok: bool = False,
    with_defaults: bool = False,
    skip_tables: bool = False,
):
    if not isinstance(rack, Rack):
        raise TypeError("'rack' argument must be an instance of labbench.Rack")

    cls = type(rack)

    output_path = Path(output_path)
    output_path.mkdir(exist_ok=exist_ok, parents=True)

    with open(output_path / RACK_CONFIG_FILENAME, 'w') as stream:
        cm = ruamel_yaml.comments.CommentedMap(
            {
                _FIELD_SOURCE: dict(
                    import_string=str(sourcepath),
                    class_name=None if cls.__name__ == '_as_rack' else cls.__name__,
                    python_path=str(pythonpath),
                ),
                _FIELD_KEYWORD_DEFAULTS: _map_method_defaults(rack),
                _FIELD_DEVICES: _map_devices(cls),
            }
        )

        cm.yaml_set_comment_before_after_key(
            _FIELD_SOURCE,
            before='orient the python interpreter to the source',
        )

        cm.yaml_set_comment_before_after_key(
            _FIELD_KEYWORD_DEFAULTS,
            before='\nparameter defaults for sequences in rack:'
            '\nthese parameters can be omitted from sequence table columns',
        )

        cm.yaml_set_comment_before_after_key(
            _FIELD_DEVICES, before='\ndevice settings: initial values for value traits'
        )

        # cm = _quote_strings_recursive(cm)

        _yaml.dump(cm, stream)

    if not skip_tables:
        for name, obj in rack.__dict__.items():
            if not callable(obj):
                continue

            table_path = getattr(obj, '_tags', {}).get('table_path', None)

            if table_path is None and not hasattr(Rack, name):
                table_path = name + '.csv'

            if table_path is not None:
                # write_csv_template(obj, output_path/table_path)
                # obj.to_template(output_path / f"{obj.__name__}.csv")
                write_table_stub(
                    rack, name, output_path / table_path, with_defaults=with_defaults
                )


def read_yaml_config(config_path: str):
    with open(config_path) as f:
        config = _yaml.load(f)
        util.logger.debug(f'loaded configuration from "{config_path!s}"')
    return config


def load_rack(output_path: str, defaults: dict = {}, apply: bool = True) -> Rack:
    """instantiates a Rack object from a config directory created by dump_rack.

    After instantiation, the current working directory is changed to output_path.
    """

    config_path = Path(output_path) / RACK_CONFIG_FILENAME
    config = read_yaml_config(config_path)

    if 'import_string' not in config[_FIELD_SOURCE]:
        raise KeyError(f"import_string missing from '{config_path!s}'")

    append_path = config[_FIELD_SOURCE]['python_path']

    # synthesize a Rack class
    rack_cls = import_as_rack(
        import_string=config[_FIELD_SOURCE]['import_string'],
        cls_name=config[_FIELD_SOURCE]['class_name'],
        append_path=[] if append_path is None else [append_path],
        # TODO: support extensions to python path?
    )

    if apply:
        os.chdir(output_path)
        _adjust_sequence_defaults(rack_cls, config[_FIELD_KEYWORD_DEFAULTS], **defaults)

    rack_cls._propagate_ownership()

    obj = rack_cls()

    if apply:
        for name, params in config[_FIELD_DEVICES].items():
            try:
                owned_obj = getattr(obj, name)
            except AttributeError:
                objname = type(obj).__qualname__
                raise OSError(
                    f"{config_path} refers to a device '{name}' that does not exist in {objname}"
                )

            for param_name, param_value in params.items():
                setattr(owned_obj, param_name, param_value)

    return obj
