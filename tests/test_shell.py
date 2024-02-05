import pytest

import labbench as lb
from labbench import paramattr as attr

lb.util.force_full_traceback(True)

class Shell_Python(lb.ShellBackend):
    script_path: str = attr.value.Path(default=None, must_exist=True, help='path to a python script file')
    command: str = attr.value.str(default=None, key='-c', help='execute a python command')

    # @attr.kwargs_to_self('script_path', 'command')
    def __call__(self, **kwargs):
        argv = ['python']
        if self.script_path is not None:
            argv += [self.script_path]
        argv += lb.shell_options_from_keyed_values(self)

        return self.run(*argv, **kwargs)

def test_shell_options_from_keyed_bool():
    REMAP = {True: 'yes', False: 'no'}
    class ShellCopy(lb.ShellBackend):
        recursive: bool = attr.value.bool(False, key='-R')

    cp = ShellCopy(recursive=True)
    Shell_Python()
    
    assert tuple(lb.shell_options_from_keyed_values(cp, hide_false=True)) == ('-R',)
    assert tuple(lb.shell_options_from_keyed_values(cp, remap=REMAP)) == ('-R', 'yes')

def test_shell_options_from_keyed_str():
    class DiskDuplicate(lb.ShellBackend):
        block_size: str = attr.value.str('1M', key='bs')
        
    dd = DiskDuplicate()
    dd.block_size = '1024k'

    assert tuple(lb.shell_options_from_keyed_values(dd, join_str='=')) == ('bs=1024k',)
    assert tuple(lb.shell_options_from_keyed_values(dd)) == ('bs', '1024k',)

def test_shell_options_with_hidden_values():
    class Command(lb.ShellBackend):
        c1: str = attr.value.str(None, key='key1')
        c2: str = attr.value.str('hi', key='key2')
        c3: bool = attr.value.bool(False, key='key3')
        
    command = Command()
    # dd.block_size = '1024k'

    assert tuple(lb.shell_options_from_keyed_values(command, skip_none=True, hide_false=True)) == ('key2', 'hi')

def test_python_print():
    TEST_STRING = 'hello world'
    python = Shell_Python()

    python.command = f'print("{TEST_STRING}")'
    assert python() == f'{TEST_STRING}\n'.encode()

    python.command = f'import sys; print("{TEST_STRING}", file=sys.stderr)'
    assert python() == b''

    python.command = f'import sys; print("{TEST_STRING}", file=sys.stderr)'
    with pytest.raises(ChildProcessError):
        python(raise_on_stderr=True)
