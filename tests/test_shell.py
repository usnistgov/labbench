import labbench as lb
from labbench import paramattr as attr
import pytest


class Shell_Python(lb.ShellBackend):
    FLAGS = {
        'command': '-c' 
    }

    binary_path = attr.value.Path('python', sets=False, inherit=True)
    path: str = attr.value.Path(None, must_exist=True, help='path to a python script file')
    command: str = attr.value.str(None, key='-c', help='execute a python command')

    def get_flags(self):
        pass

    # def get_arg_list(self):
    #     [for name in attr._bases.list_value_attrs(self)]

    # def __call__(self, *arg_list, **flags):

    #     return self.run(
    #         FLAGS,
    #         **kwargs
    #     )

# def test_python_print():
#     TEST_STRING = 'hello world'
#     python = Shell_Python()

#     python.command = f'print("{TEST_STRING}")'
#     assert python() == f'{TEST_STRING}\n'.encode()

#     python.command = f'import sys; print("{TEST_STRING}", file=sys.stderr)'
#     assert python.run() == ''.encode()

#     python.command = f'import sys; print("{TEST_STRING}", file=sys.stderr)'
#     with pytest.raises(ChildProcessError):
#         python.run(check_stderr=True)

