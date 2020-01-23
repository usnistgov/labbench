# -*- coding: utf-8 -*-
"""
Generate PEP484 stub files to fill in signatures to support IDE code completion
"""

import sys
if '..' not in sys.path:
    sys.path.insert(0, '..')
import inspect, importlib

modname = 'labbench'
globals()[modname] = importlib.import_module(modname)
classes = labbench.Trait, labbench.Device

covered = []

def method(stream, obj, name, depth=0):
    print(' ' * depth, f'    + {obj.__name__}.{name}')
    try:
        sig = str(inspect.signature(getattr(obj, name)))
    except:
        return
    else:
        stream.write(f"    def {name}{sig} -> None: ...\n")

def trait(stream, obj, name, depth=0):
    print(' ' * depth, f'    + {obj.__name__}.{name}')
    attr = getattr(obj, name)
    if attr.__getter__ or attr.__setter__:
        stream.write(f"    @{repr(attr)}\n")
        if attr.__getter__:
            sig = str(inspect.signature(attr.__getter__))
            stream.write(f"    def {name}{sig} -> None: ...\n")
        if attr.__setter__:
            sig = str(inspect.signature(attr.__setter__))
            stream.write(f"    def {name}{sig} -> None: ...\n")
    else:
        print(f"    {name} = {repr(obj)}")
    sig = str(inspect.signature(getattr(obj, name)))
    stream.write(f"    def {name}{sig} -> None: ...\n")

def makestub(modname, depth=0):
    def issubmod(v):
        return inspect.ismodule(v) and v.__name__.startswith(modname) and v not in covered
    toplevel = importlib.import_module(modname)

    mods = [v for v in labbench.__dict__.values() if issubmod(v)]
            
    covered.extend(mods)
    
    for mod in mods:
        print(' '*depth, 'module: ', mod.__name__)
        with open(mod.__file__+'i','w', encoding='utf') as pyi:
            pyi.write(f'from {mod.__name__} import *\n')
            pyi.write(f'import {modname}\n')
            pyi.write(f'import builtins\n\n')
            
            for name, obj in mod.__dict__.items():
                if obj.__class__.__module__.startswith(modname):#inspect.isclass(obj) and issubclass(obj, classes):
                    base = obj.__base__
                    pyi.write(f"class {obj.__name__}({base.__module__}.{base.__qualname__}):\n")
                    for attrname, attr in obj.__dict__.items():
                        if isinstance(attr, labbench.Trait):
                            trait(pyi, obj, attrname, depth+1)
                        elif callable(attr) and not inspect.isclass(attr):
                            method(pyi, obj, attrname, depth+1)
                    pyi.write('    pass\n\n')
                elif issubmod(obj):
                    makestub(obj.__name__, depth+1)

makestub(modname)