import importlib
import sys
import typing
from pathlib import Path

import astor

from labbench import Device, Rack, util
from labbench.paramattr._bases import (
    Any,
    Method,
    ParamAttr,
    T,
    Undefined,
    get_class_attrs,
    list_value_attrs,
)

util.force_full_traceback(True)

VALID_PARENTS = Device, Rack, ParamAttr

import ast
import typing
from inspect import isclass

from ast_decompiler import decompile

import labbench as lb
from labbench import Device, Rack


def nameit(obj):
    if obj is Undefined:
        return 'Undefined'
    if isinstance(obj, typing.GenericAlias):
        return repr(obj)
    elif hasattr(obj, '__name__'):
        return obj.__name__
    if hasattr(obj, '__qualname__'):
        return obj.__qualname__

    t = type(obj)
    if hasattr(t, '__name__'):
        return t.__name__
    elif hasattr(t, '__qualname__'):
        return t.__qualname__

    raise TypeError(f"couldn't name {obj}")


def parse_literal(s: str):
    obj = ast.parse(s).body[0].value
    # obj.ctx = context_source
    return obj


def ast_name(name):
    return ast.Name(id=name, kind=None)


def ast_arg(name, annotation=lb.Undefined):
    annotation = ast_name(annotation) if annotation is not None else None
    return ast.arg(arg=name, annotation=annotation, type_comment=None)


def ast_typehint_optional(t, remap={}):
    remap[type(None)] = None
    args = ','.join(
        [
            getattr(remap.get(sub, sub), '__name__', sub.__class__.__name__)
            for sub in typing.get_args(t)
        ]
    )
    print('***', f'_typing.Optional[{args}]')
    return parse_literal(f'_typing.Optional[{args}]')


def ast_signature(args, defaults, annotations):
    annotations = {k: nameit(v) for k, v in annotations.items() if v is not Undefined}

    return ast.arguments(
        posonlyargs=[],
        kw_defaults=[],
        args=[ast_arg(a, annotations.get(a, None)) for a in args],
        vararg=None,
        kwarg=None,  # ast.arg(arg='values', annotation=ast.Name(id='Any', ctx=ast.Load())),
        defaults=[ast_name(repr(d)) for d in defaults if d is not lb.Undefined],
    )


def ast_function_stub(name, args, defaults, annotations, decorator_list=[]):
    if 'return' in annotations:
        if isinstance(annotations['return'], (ast.Attribute, ast.Subscript)):
            type_comment = returns = annotations['return']
        else:
            type_comment = returns = ast_name(nameit(annotations['return']))
    else:
        type_comment = returns = None

    return ast.FunctionDef(
        name=name,
        args=ast_signature(args, defaults, annotations),
        body=[ast.Expr(value=ast.Constant(value=..., kind=None))],
        decorator_list=decorator_list,
        returns=returns,
        type_comment=type_comment,
    )


def update_stubs(path, mod_name, sub_name):
    mod = importlib.import_module(f'{mod_name}')
    namespace = importlib.import_module(f'{mod_name}.{sub_name}')

    ast_root = astor.code_to_ast(namespace)
    # with open(path, "r") as f:
    #     ast_root = ast.parse(f.read())

    # identify classes in the root namespace that are one of the desired types
    target_method_names = '__init__'

    # use the interpreter to identify the names of classes with the desired type
    target_names = [
        name
        for name, obj in namespace.__dict__.items()
        if isclass(obj) and issubclass(obj, (ParamAttr, Rack, Device))
    ]

    if len(target_names) > 0:
        print(f'{namespace.__name__}: update {target_names}')
    else:
        return

    # find their definitions in the parsed ast tree
    target_cls_defs = [
        ast_obj
        for ast_obj in ast.iter_child_nodes(ast_root)
        if getattr(ast_obj, 'name', None) in target_names
    ]

    for cls_def in target_cls_defs:
        # scrub any existing __init__ stub
        for child in list(cls_def.body):
            if getattr(child, 'name', None) == target_method_names:
                # _prev = child
                cls_def.body.remove(child)
                break

        cls = getattr(namespace, cls_def.name)

        if issubclass(cls, Device):
            attrs = {}

            if 'key' in get_class_attrs(cls):
                attrs['key'] = get_class_attrs(cls)['key']
            attrs.update(
                {
                    name: get_class_attrs(cls)[name]
                    for name in list_value_attrs(cls)
                    if get_class_attrs(cls)[name].sets and name != 'key'
                }
            )

            args = list(attrs.keys())
            defaults = {trait.name: nameit(trait.default) for trait in attrs.values()}
            annotations = {name: nameit(trait._type) for name, trait in attrs.items()}

        elif issubclass(cls, (ParamAttr, Rack)):

            def transform_annot(cls, a):
                if a is T:
                    return cls._type
                else:
                    return a

            raw_annots = getattr(cls, '__annotations__', {})
            raw_annots = {k: v for k, v in raw_annots.items() if not k.startswith('_')}

            if issubclass(cls, Method):
                defaults = dict(key=None)
                annotations = dict(key=None)
                args = list(raw_annots.keys())[::-1]
                args.remove('key')
                args = ['key'] + args
            else:
                defaults = {}
                annotations = {}
                args = list(raw_annots.keys())

            defaults.update({name: getattr(cls, name) for name in args})
            defaults = {
                name: (None if d is Undefined else d) for name, d in defaults.items()
            }
            annotations.update(
                {
                    name: transform_annot(cls, type_)
                    for name, type_ in raw_annots.items()
                }
            )
            annotations = {
                name: type_
                for name, type_ in annotations.items()
                if type_ not in (Any, None, Undefined)
            }
        else:
            raise TypeError(f'{cls} is an unknown class type')

        if issubclass(cls, Method) and cls is not Method:
            decorators = [parse_literal('_typing.overload')]

            # for the keyed method determined by setting the 'key' keyword
            annotations['return'] = parse_literal('_bases.TKeyedMethod')
            del defaults['key']
            cls_def.body.insert(
                0,
                ast_function_stub(
                    '__new__',
                    ['cls'] + args,
                    list(defaults.values()),
                    annotations,
                    decorator_list=decorators,
                ),
            )

            # for unkeyed (decorator) method
            annotations['return'] = parse_literal('_bases.TDecoratedMethod')
            annotations.pop('key', None)
            args.remove('key')
            cls_def.body.insert(
                0,
                ast_function_stub(
                    '__new__',
                    ['cls'] + args,
                    list(defaults.values()),
                    annotations,
                    decorator_list=decorators,
                ),
            )
        else:
            cls_def.body.insert(
                0,
                ast_function_stub(
                    target_method_names,
                    ['self'] + args,
                    list(defaults.values()),
                    annotations,
                ),
            )

    with open(path, 'w') as f:
        f.write(decompile(ast_root))


if __name__ == '__main__':
    root = Path('labbench')
    mod_name = 'labbench'

    # clear out previous files
    for path in root.rglob('*.pyi'):
        Path(path).unlink()

    # stubgen is the first stab
    from mypy import stubgen

    sys.argv = [sys.argv[0], str(root), '-o', str(root / '..'), '-v']
    stubgen.main()

    # now step through to replace __init__ keyword arguments
    for path in root.rglob('*.pyi'):
        if str(path).endswith('notebook.py'):
            continue

        path = Path(path)

        # convert python path to an importable module name
        sub_name = '.'.join(path.with_suffix('').parts[1:])

        update_stubs(path, mod_name=mod_name, sub_name=sub_name)
