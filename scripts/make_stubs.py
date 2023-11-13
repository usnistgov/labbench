import sys

sys.path.insert(0, ".")

import importlib
from pathlib import Path

from labbench import Device, Rack, util
from labbench.paramattr._bases import ParamAttr, Undefined, Any, ThisType, get_class_attrs, list_value_attrs, list_method_attrs, list_property_attrs
util._force_full_traceback(True)

VALID_PARENTS = Device, Rack, ParamAttr

import ast
import typing
from inspect import isclass

from ast_decompiler import decompile

from labbench import Device, Rack


def nameit(obj):
    if obj is Undefined:
        return "Undefined"
    if isinstance(obj, typing.GenericAlias):
        return repr(obj)
    elif hasattr(obj, "__name__"):
        return obj.__name__
    if hasattr(obj, "__qualname__"):
        return obj.__qualname__

    t = type(obj)
    if hasattr(t, "__name__"):
        return t.__name__
    elif hasattr(t, "__qualname__"):
        return t.__qualname__

    raise TypeError(f"couldn't name {obj}")


def ast_name(name):
    return ast.Name(id=name, kind=None)


def ast_arg(name, annotation=None):
    annotation = ast_name(annotation) if annotation is not None else None
    return ast.arg(arg=name, annotation=annotation, type_comment=None)


def ast_signature(args, defaults, annotations):
    annotations = {k: nameit(v) for k, v in annotations.items() if v is not Undefined}

    return ast.arguments(
        posonlyargs=[],
        kw_defaults=[],
        args=[ast_arg(a, annotations.get(a, None)) for a in args],
        vararg=None,
        kwarg=None,  # ast.arg(arg='values', annotation=ast.Name(id='Any', ctx=ast.Load())),
        defaults=[ast_name(repr(d)) for d in defaults],
    )


def ast_function_stub(name, args, defaults, annotations):
    return ast.FunctionDef(
        name=name,
        args=ast_signature(args, defaults, annotations),
        body=[ast.Expr(value=ast.Constant(value=..., kind=None))],
        decorator_list=[],
        returns=ast_name(nameit(annotations["return"]))
        if "return" in annotations
        else None,
        type_comment=ast_name(nameit(ret_annot["return"]))
        if "return" in annotations
        else None,
    )


def update_stubs(path, mod_name, sub_name):
    mod = importlib.import_module(f"{mod_name}")
    namespace = importlib.import_module(f"{mod_name}.{sub_name}")

    with open(path, "r") as f:
        ast_root = ast.parse(f.read())

    # identify classes in the root namespace that are one of the desired types
    method_name = "__init__"

    # use the interpreter to identify the names of classes with the desired type
    target_names = [
        name
        for name, obj in namespace.__dict__.items()
        if isclass(obj) and issubclass(obj, (ParamAttr, Rack, Device))
    ]

    if len(target_names) > 0:
        print(f"{namespace.__name__}: update {target_names}")
    else:
        return

    # find their definitions in the parsed ast tree
    target_cls_defs = [
        ast_obj
        for ast_obj in ast.iter_child_nodes(ast_root)
        if getattr(ast_obj, "name", None) in target_names
    ]

    for cls_def in target_cls_defs:
        # scrub any existing __init__ stub
        for child in list(cls_def.body):
            if getattr(child, "name", None) == method_name:
                # _prev = child
                cls_def.body.remove(child)
                break

        cls = getattr(namespace, cls_def.name)

        if issubclass(cls, Device):
            attrs = {
                name: get_class_attrs(cls)[name]
                for name in list_value_attrs(cls)
                if get_class_attrs(cls)[name].sets
            }

            args = ["self"] + list(attrs.keys())
            defaults = [nameit(trait.default) for trait in attrs.values()]
            annotations = {name: nameit(trait._type) for name, trait in attrs.items()}

        elif issubclass(cls, (ParamAttr, Rack)):
            annots = getattr(cls, "__annotations__", {})
            annots = {k: v for k, v in annots.items() if not k.startswith("_")}

            args = list(annots.keys())
            defaults = [getattr(cls, name) for name in annots.keys()]
            defaults = [None if d is Undefined else d for d in defaults]
            annotations = {
                name: cls._type if type_ is ThisType else type_
                for name, type_ in annots.items()
            }
            annotations = {
                name: type_
                for name, type_ in annotations.items()
                if type_ not in (Any, None, Undefined)
            }
        else:
            raise TypeError(f"{cls} is an unknown class type")

        cls_def.body.insert(
            0, ast_function_stub(method_name, args, defaults, annotations)
        )

    with open(path, "w") as f:
        f.write(decompile(ast_root))


if __name__ == "__main__":
    root = Path("labbench")
    mod_name = "labbench"

    # clear out previous files
    for path in root.rglob("*.pyi"):
        Path(path).unlink()

    # stubgen is the first stab
    from mypy import stubgen

    sys.argv = [sys.argv[0], str(root), "-o", str(root / ".."), "-v"]
    stubgen.main()

    # now step through to replace __init__ keyword arguments
    for path in root.rglob("*.pyi"):
        if str(path).endswith("notebook.py"):
            continue

        path = Path(path)

        # convert python path to an importable module name
        sub_name = ".".join(path.with_suffix("").parts[1:])

        update_stubs(path, mod_name=mod_name, sub_name=sub_name)
