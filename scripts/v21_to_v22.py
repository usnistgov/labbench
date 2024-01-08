import sys
from pathlib import Path

lb_path = str(Path('__file__').absolute().parent.parent / 'labbench')
if lb_path not in sys.path:
    sys.path.insert(0, lb_path)
import re

import labbench as lb


def labbench_name_remapping():
    from inspect import isclass

    return {
        v.__name__: k for k, v in lb.value.__class__.__dict__.items() if isclass(v) and issubclass(v, lb._traits.Trait)
    }


def port_v21_to_v22(path, write=False):
    name_remapping = labbench_name_remapping()

    def repl_remap(expr, *which):
        def wrapper(match):
            s = str(expr)

            for i, g in enumerate(match.groups()):
                if i + 1 in which:
                    g = name_remapping.get(g, g)
                s = s.replace(rf'\{i+1}', g)

            if s != expr:
                print(f'"{match.string[match.start():match.end()]}" -> "{s}"')
            return s

        return wrapper

    with open(path) as f:
        text = f.read()

    # regex patterns
    target_traits = '|'.join(name_remapping.keys())
    py_object_name = r'[^\W\d]*\w*'
    module_prefix = rf'{py_object_name}\.*'

    print(path)
    print('----------------------------------\n')

    text, n0 = re.subn(
        rf'@({module_prefix})({target_traits})\(',
        repl_remap(r'@\1property.\2(', 2),
        text,
    )

    text, n1 = re.subn(
        rf'({py_object_name})\s*:\s*({module_prefix})({target_traits})\s*\(',
        repl_remap(r'\1 = \2value.\3(', 3),
        text,
    )

    text, n2 = re.subn(
        rf'({py_object_name})\s*=\s*({module_prefix})({target_traits})\s*\(',
        repl_remap(r'\1 = \2property.\3(', 3),
        text,
    )

    text, n4 = re.subn(r'\.settings([\.\,\[\]\s])', r'\1', text)

    text, n3 = re.subn(
        rf'(\s*{py_object_name})\s*:\s*([^=\s\#\n\r\{{\}}\,\\\(\)]+)(\s*[\#\n\r]+)',
        r'\1 = \2\3',
        text,
    )

    print(
        f'replaced {n0} property decorators, {n1} value assignments, {n2} property assignments, {n3} value changes in subclasses, {n4} .settings uses \n'
    )

    if write:
        with open(path, 'w') as f:
            f.write(text)


if __name__ == '__main__':
    from glob import glob

    for arg in sys.argv[1:]:
        for path in glob(arg):
            port_v21_to_v22(path, write=True)
