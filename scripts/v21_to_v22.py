
from pathlib import Path
import sys
lb_path = str(Path('__file__').absolute().parent.parent/'labbench')
if lb_path not in sys.path:
    sys.path.insert(0,lb_path)
import re
import labbench as lb



def labbench_name_remapping():
    trait_type_map = lb._traits.TRAIT_TYPE_REGISTRY


    name_remapping = {
        v.__name__: k.__name__ for k,v in trait_type_map.items()
        if k is not None
    }

    return name_remapping

def port_v21_to_v22(path, write=False):

    name_remapping = labbench_name_remapping()

    def repl_remap(expr, *which):
        def wrapper(match):
            s = str(expr)

            for i,g in enumerate(match.groups()):
                if i+1 in which:
                    g = name_remapping.get(g,g)
                s = s.replace(rf'\{i+1}', g)

            if s != expr:
                print(f'"{match.string[match.start():match.end()]}" -> "{s}"')
            return s
        return wrapper

    with open(path, 'r') as f:
        text = f.read()

    # regex patterns
    target_traits = "|".join(name_remapping.keys())
    py_object_name = r'[^\W\d]*\w*'
    module_prefix = rf'{py_object_name}\.*'

    print(path)
    print('----------------------------------\n')
    

    text, n0 = re.subn(
        rf'@({module_prefix})({target_traits})\(',
        repl_remap(r'@\1property(type=\2, ',2),
        text
    )

    text, n1 = re.subn(
        rf'({py_object_name})\s*:\s*({module_prefix})({target_traits})\s*\(',
        repl_remap(r'\1:\3 = \2value(',3),
        text
    )

    text, n2 = re.subn(
        rf'({py_object_name})\s*=\s*({module_prefix})({target_traits})\s*\(',
        repl_remap(r'\1:\3 = \2property(',3),
        text
    )

    text, n4 = re.subn(
        rf'\.settings\.',
        rf'.',
        text
    )

    print(f'replaced {n0} property decorators, {n1} value assignments, {n2} property assignments, {n4} .settings references \n')

    if write:
        with open(path, 'w') as f:
            f.write(text)

if __name__ == '__main__':
    from glob import glob
    for arg in sys.argv[1:]:
        for path in glob(arg):
            port_v21_to_v22(path, write=True)