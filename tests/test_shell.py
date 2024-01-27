import labbench as lb
from labbench import paramattr as attr
import pytest


class Shell_Python(lb.ShellBackend):
    FLAGS = {
        'command': '-c' 
    }

    binary_path = attr.value.str('python', sets=False)
    path: str = attr.value.Path(None, key=None, must_exist=True, help='path to a python script file')
    command: str = attr.value.str(None, help='execute a python command')

    def run(self, **kwargs):
        return super().run(
            self.FLAGS,
            **kwargs
        )

def test_python_print():
    TEST_STRING = 'hello world'
    python = Shell_Python()

    python.command = f'print("{TEST_STRING}")'
    assert python.run() == f'{TEST_STRING}\n'.encode()

    python.command = f'import sys; print("{TEST_STRING}", file=sys.stderr)'
    assert python.run() == ''.encode()

    python.command = f'import sys; print("{TEST_STRING}", file=sys.stderr)'
    with pytest.raises(ChildProcessError):
        python.run(check_stderr=True)


if __name__ == '__main__':
    import inspect

    lb.show_messages('debug')

    python = Shell_Python(command='print("hello world")')
    print(python.run())
    # print(python['resource'].key is lb.Undefined)
    # print(lb.Unicode.__defaults__)
    # print(inspect.signature(lb.Unicode.__init__))

    # print(python._commandline())
