import sys
sys.path.insert(0,'.')

from pathlib import Path
import importlib
from glob import glob

import ast
from ast_decompiler import decompile
from inspect import isclass
import labbench as lb
import labbench._traits
from labbench._traits import Trait, Undefined, ThisType, Any
from labbench import Rack, Device
import typing

VALID_PARENTS = Device, Rack, Trait

def nameit(obj):
    if obj is Undefined:
        return 'Undefined'
    if isinstance(obj, typing._VariadicGenericAlias):
        return repr(obj)
    if hasattr(obj, '__qualname__'):
        return obj.__qualname__
    elif hasattr(obj, '__name__'):
        return obj.__name__
    
    t = type(obj)
    if hasattr(t, '__qualname__'):
        return t.__qualname__
    elif hasattr(t, '__name__'):
        return t.__name__
    
    raise TypeError(f"couldn't name {obj}")


def ast_name(name):
    return ast.Name(id=name, kind=None)

def ast_arg(name, annotation=None):
    annotation = ast_name(annotation) if annotation is not None else None
    return ast.arg(arg=name, annotation=annotation, type_comment=None)

def ast_signature(args, defaults, annotations):
    annotations = {k:nameit(v) for k,v in annotations.items() if v is not Undefined}
    if 'key' in annotations:
        print(annotations)

    return ast.arguments(
        args=[ast_arg(a, annotations.get(a, None)) for a in args],
        vararg=None,
        kwarg=None,#ast.arg(arg='values', annotation=ast.Name(id='Any', ctx=ast.Load())),
        defaults=[ast_name(repr(d)) for d in defaults],
    )

def ast_function_stub(name, args, defaults, annotations):
    return ast.FunctionDef(
        name=name,
        args=ast_signature(args, defaults, annotations),
        body=[ast.Expr(value=ast.Constant(value=..., kind=None))],
        decorator_list=[],
        returns=ast_name(nameit(annotations['return'])) if 'return' in annotations else None,
        type_comment=ast_name(nameit(ret_annot['return'])) if 'return' in annotations else None
    )

# target_inits = {parent.name: [child for child in ast.iter_child_nodes(parent) if getattr(child, 'name', None) == '__init__'][0] for parent in target_objs}
# target_inits

def update_stubs(path, mod_name, sub_name):
    mod = importlib.import_module(f'{mod_name}')
    sub = importlib.import_module(f'{mod_name}.{sub_name}')

    with open(path, 'r') as f:
        parsed = ast.parse(f.read())

    # identify classes in the root namespace that are one of the desired types
    method_name = '__init__'

    # use the interpreter to identify the names of classes with the desired type
    target_names = [
        name for name, obj in sub.__dict__.items()
        if isclass(obj) and issubclass(obj, (Trait, Rack, Device))
    ]

    print(f'{path}: update {target_names}')

    # find their definitions in the parsed ast tree
    target_cls_defs = [
        ast_obj for ast_obj in ast.iter_child_nodes(parsed)
        if getattr(ast_obj, 'name', None) in target_names
    ]

    for cls_def in target_cls_defs:
        # scrub any existing __init__ stub
        for child in list(cls_def.body):
            if getattr(child, 'name', None) == method_name:
                _prev = child
                cls_def.body.remove(child)
                break

        cls = getattr(sub, cls_def.name)

        if issubclass(cls, Device):
            traits = {name: cls._traits[name] for name in cls._value_attrs if cls._traits[name].settable}

            args = ['self']+list(traits.keys())
            defaults = [nameit(trait.default) for trait in traits.values()]
            annotations = {name: nameit(trait.type) for name, trait in traits.items()}

        elif issubclass(cls, (Trait, Rack)):
            annots = getattr(cls, '__annotations__', {})
            annots = {k:v for k,v in annots.items() if not k.startswith('_')}
            
            args = list(annots.keys())
            defaults = [getattr(cls, name) for name in annots.keys()]
            defaults = [None if d is Undefined else d for d in defaults]
            annotations = {name: cls.type if type_ is ThisType else type_ for name, type_ in annots.items()}
            annotations = {name: type_ for name, type_ in annotations.items() if type_ not in (Any, None, Undefined)}
        else:
            raise TypeError(f'{cls} is an unknown class type')

        cls_def.body.insert(0, ast_function_stub(method_name, args, defaults, annotations))


    with open(path, 'w') as f:
        f.write(decompile(parsed))


    # out, *therest = re.split(r'[\r\n]class ', txt)
    # out += '\n'

    # for class_block in therest:
    #     classtoken, *attr_lines = re.split(r'[ \t]*[\r\n]+', class_block)

    #     classname = re.split(r'[\(\:]', classtoken)[0]

    #     cls = getattr(sub, classname)

    #     if not issubclass(cls, VALID_PARENTS) or len(attr_lines) == 0 or '__init__' not in class_block:
    #         out += f'class {class_block}\n'
    #         continue

    #     print(mod_name, sub_name, classname)

    #     # drop the leading indent whitespace
    #     indent_len = len(re.split(r'[A-Za-z_]', attr_lines[0])[0])
        

    #     for i, full_line in enumerate(list(attr_lines)):
    #         """ weed out __init__
    #         """
    #         if len(full_line.strip()) == 0 or len(full_line) < indent_len:
    #             continue
    #         line = full_line[indent_len:]

    #         if not line.startswith('def'):
    #             continue
    #             # skip nested indents, and look for function definitions
            
    #         _def_token, attr_name, *tokens = re.findall(r'[A-Za-z_][\*A-Za-z_0-9]*', line)

    #         if attr_name == '__init__':
    #             attr_lines[i] = ''

    #     obj = getattr(cls, '__init__')

    #         # arg_tokens = re.findall(r'\*\*[A-Za-z_][\*A-Za-z_0-9]+\s*\:*\s*[A-Za-z_]*[\*A-Za-z_0-9]*', line)

    #         # if len(arg_tokens) == 0:
    #         #     continue
    #         # if len(arg_tokens) == 1:
    #         #     pass
    #         # else:
    #         #     raise ValueError(f'too many number keyword argument tokens ({arg_tokens})')

    #         # repl_target = arg_tokens[0]

    #         # update = ''

    #     if issubclass(cls, Device):
    #         traits = {name: cls._traits[name] for name in cls._value_attrs if cls._traits[name].settable and name not in tokens}
    #         kws = [f'{name}: {nameit(trait.type)}={repr(trait.default)}' for name, trait in traits.items()]
    #         kws = ', '.join(kws)
    #     elif issubclass(cls, (Trait, Rack)):
    #         annots = getattr(cls, '__annotations__', {})
    #         kws = [f'{name}: {nameit(type_)} + {"=" + repr(getattr(cls,name)) if hasattr(cls,name) else ""}' for name, type_ in annots.items()]
    #         kws = ', '.join(kws)
    #     else:
    #         raise TypeError(f'{cls} is an unknown class type')

    #     if indent_len == 0:
    #         indent = '    '
    #     else:
    #         indent=attr_lines[0][:indent_len]
    #     newline = f'{indent}def __init__(self, {kws}): ...'
    #     # print(f'{path}: {attr_lines[i]} -> "{newline}"')

    #     out += f'class {classtoken.split("...",1)[0]}\n'
    #     out += '\n'.join(attr_lines) + '\n'
    #     out += newline + '\n\n'

    # with open(path, 'w') as f:
    #     f.write(out)


if __name__ == '__main__':
    from mypy import stubgen

    root = Path('labbench')
    mod_name = 'labbench'

    import sys
    sys.argv = [sys.argv[0],str(root), '-o', str(root/'..'), '-v']

    stubgen.main()

    print(str(root/'*.pyi'))

    for path in glob(str(root/'*.pyi')):
        print(path)
        path = Path(path)

        if path.stem == 'notebooks':
            continue

        update_stubs(path, mod_name=mod_name, sub_name=path.stem)
