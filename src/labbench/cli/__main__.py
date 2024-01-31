#!python3

# Command line tool for lab experiments using labbench.Rack objects

import sys

try:
    import inspect
    import re
    from pathlib import Path

    import click
except KeyboardInterrupt:
    # skip the trace dump on ctrl+c
    sys.exit(1)

EMPTY = inspect.Parameter.empty


def synthesize_device_stubs(devices: list) -> str:
    def class_name_from_make_model(make, model):
        make = make.title()
        make, model = (re.sub(r'([\W_])+', '', s) for s in (make, model))
        return make + model

    ret = 'import labbench as lb\n\n'
    for device in devices:
        # print(name, device)
        for attr in ('make', 'model', 'read_termination', 'write_termination'):
            default = getattr(device, attr)
            if default == getattr(type(device), attr).default:
                continue
            ret += f'@attr.adjust({attr!r}, default={default!r})\n'

        cls_name = class_name_from_make_model(device.make, device.model)
        ret += f'class {cls_name}(lb.VISADevice):\n'
        ret += f'   """Probed serial number {device.serial!r}"""\n'
        ret += '    pass\n\n\n'

    return ret


def summarize_device_probe(device):
    device_args = ''
    if device.read_termination != type(device).read_termination.default:
        device_args += f', read_termination={device.read_termination!r}'
    if device.write_termination != type(device).write_termination.default:
        device_args += f', write_termination={device.write_termination!r}'
    print(f'  • Make: "{device.make.title()}"')
    print(f'    Model: "{device.model}"')
    print(f'    Serial: "{device.serial}"')
    print(f'    Device: lb.VISADevice({repr(device.resource) + device_args})')
    print()


def empty_rack(cls):
    """instantiate cls, filling in owned objects that have no default value"""
    init_params = inspect.signature(cls).parameters
    init_kws = {
        name: cls.__annotations__[name]() if param.default is EMPTY else param.default
        for name, param in init_params.items()
    }
    return cls(**init_kws)


def post_mortem_debug(note=None, exc_info=None):
    import pdb
    import traceback

    import labbench as lb

    if exc_info is None:
        exc_info = sys.exc_info()
    ex = exc_info[1]

    if isinstance(ex, lb.util.ConcurrentException) and len(ex.thread_exceptions) > 0:
        if isinstance(ex.thread_exceptions, (list, tuple)):
            ex.thread_exceptions = dict(enumerate(ex.thread_exceptions))

        for i, (name, thread_exc_info) in enumerate(ex.thread_exceptions.items()):
            progress_msg = (note or '') + '\n'
            progress_msg += ''

            progress_msg += f'debug thread {i+1} of {len(ex.thread_exceptions)}\n'
            if name != i:
                progress_msg += f'thread name "{name}"'

            post_mortem_debug(note, exc_info=thread_exc_info)

        return

    else:
        traceback.print_exception(*exc_info)

        sys.stderr.write(
            "\nentering pdb prompt because the above exception was raised. use 'exit' to exit.\n"
        )
        if note is not None:
            sys.stderr.write(note + '\n')

        pdb.post_mortem(exc_info[2])


def do_cli():
    try:
        cli()
    except KeyboardInterrupt:
        sys.exit(1)


@click.group(help='configure and run labbench Rack objects')
def cli():
    pass


@cli.command(
    name='init',
    help="""Initialize a new Rack configuration from a python source file.

    The configuration consists of a directory of autogenerated stub files. The python module
    IMPORT_STRING is imported, and the Rack class is taken from the name CLS named RACK_NAME.
    A new directory is created at DEST that consists of serialized configuration files and table stubs
    for defining sequence execution. There must be no existing file or directory at DEST unless
    the force flag is set. When compiling PYFILE, python imports follow PYTHONPATH as normal.""",
)
@click.argument(
    'import_string',
    type=str,  # , help='python import string for the module where the Rack is defined'
)
@click.option(
    '--cls', type=str, help='use this Rack in PYFILE instead of the module namespace'
)
@click.option(
    '--pythonpath',
    type=click.Path(exists=True, file_okay=False, readable=True),
    help='change the default import path to append to PYTHONPATH',
)
@click.option(
    '--output', type=click.Path(exists=False), help='change the output directory'
)
@click.option('--force', is_flag=True, help='overwrite pre-existing files')
@click.option(
    '--with-defaults',
    is_flag=True,
    help='include sequence columns that have default values',
)
@click.option(
    '--with-defaults',
    is_flag=True,
    help='include sequence columns that have default values',
)
def init(
    import_string,
    cls=None,
    pythonpath=None,
    output=None,
    force=False,
    with_defaults=False,
):
    if pythonpath is None:
        pythonpath = '.'

    # delay the labbench import so that e.g. --help is faster
    import labbench as lb

    lb._force_full_traceback(True)

    cls = lb._rack.import_as_rack(import_string, cls_name=cls, append_path=[pythonpath])

    rack = empty_rack(cls)

    if output is None:
        output = cls.__qualname__

    lb.dump_rack(
        rack,
        output,
        sourcepath=import_string,
        exist_ok=force,
        with_defaults=with_defaults,
        pythonpath=pythonpath,
    )

    print(f'initialized rack directory at {output}')


@cli.command(
    name='reset',
    help="""Replace a Rack configuration file with an clean stub.

    If PATH refers to a sequence table, its format must be csv and its parent must be a Rack
    directory. If it is named config.yaml, the stub will match the original source parameters,
    but overwrite the others.""",
)
@click.argument(
    'path', type=click.Path(exists=True, dir_okay=False, writable=True, readable=True)
)  # , help='path to Rack directory or sequence table file')
@click.option(
    '--with-defaults',
    is_flag=True,
    help='include sequence parameters that have defaults',
)
def reset(path, with_defaults=False):
    # delay the labbench import so that e.g. --help is faster
    import labbench as lb

    lb._force_full_traceback(True)
    path = Path(path)

    if path.name.endswith('.csv'):
        # reset a sequence table

        # pull in the rack
        rack = lb.load_rack(Path(path).parent, apply=True)

        # make_sequence_stub takes care of the introspection on the rack
        lb._serialize.make_sequence_stub(
            rack, path.stem, path.parent, with_defaults=with_defaults
        )
        print(f'reset "{path}" to stub')
    elif path.name.endswith('.yaml'):
        raise NotImplementedError

        # reset a config.yaml

        # TODO: this is untested
        rack = lb.load_rack(path, apply=False)

        lb.dump_rack(rack, path, exist_ok=True, with_defaults=with_defaults)
    else:
        raise NotImplementedError


@cli.command(
    name='run',
    help="""Step through calls to a Rack sequence defined in a CSV table.

    The parent directory of the csv file needs to have a config.yaml as generated by the
    `init` command. The rack class is imported from the csv's parent directory, run from
    the context of the current working directory and PYTHONPATH.""",
)
@click.argument(
    'csv_path', type=click.Path(exists=True, dir_okay=False)
)  # , help='path to the config directory')
@click.option(
    '--notebook',
    is_flag=True,
    type=bool,
    help='show formatted progress when run in a notebook',
)
@click.option(
    '--verbose',
    type=bool,
    is_flag=True,
    default=False,
    help='include labbench internals in tracebacks',
)
def run(csv_path, notebook=False, verbose=False):
    csv_path = Path(csv_path)
    config_dir = csv_path.parent
    sequence_name = csv_path.stem

    relative_csv_path = csv_path.relative_to(config_dir)

    # delay the labbench import so that e.g. --help is faster
    import labbench as lb

    if verbose:
        lb._force_full_traceback(True)

    # instantiate a Rack from config.yaml
    rack = lb.load_rack(config_dir, apply=True)

    if notebook:
        from labbench import notebooks

        notebooks.display(notebooks.panel(rack))

    # get the callable bound sequence before connection
    # in case it does not exist
    bound_seq = getattr(rack, sequence_name)

    return_code = 0
    ex = None
    try:
        with rack:
            try:
                # ...and run the sequence object
                row_iterator = bound_seq.iterate_from_csv(relative_csv_path)
                for i, (row, result) in enumerate(row_iterator):
                    pass
            except BaseException as e:
                ex = e
                post_mortem_debug(
                    'any open devices and racks will be closed after the pdb session.'
                )
                return_code = 1
                raise
    except BaseException as e:
        if return_code == 0 or e is not ex:
            post_mortem_debug('devices and racks have already been closed.')
            return_code = 1
        # otherwise, the post mortem has already been done

    return return_code


@cli.command(
    name='open',
    help="""Open a test connection to the devices in a Rack.

    The parent directory of the csv file needs to have a config.yaml as generated by the
    `init` command. """,
)
@click.argument(
    'config_dir', type=click.Path(exists=True)
)  # , help='path to the config directory')
@click.option(
    '--verbose',
    type=bool,
    is_flag=True,
    default=False,
    help='include labbench internals in tracebacks',
)
def open(config_dir, verbose=False):
    config_dir = Path(config_dir)

    # delay the labbench import so that e.g. --help is faster
    import labbench as lb

    if verbose:
        lb._force_full_traceback(True)

    # instantiate a Rack from config.yaml
    rack = lb.load_rack(config_dir, apply=True)

    # instantiate the rack, binding the Sequence method

    try:
        with rack:
            pass
    except BaseException:
        post_mortem_debug('devices and racks have already been closed.')
        return 1
    else:
        return 0


@cli.command(
    name='visa-probe',
    help="""Probe available VISA device connections.

    The pyvisa resource manager will be RESOURCE_MANAGER. This should be one of
    @ivi, @sim, or @py. If unspecified, the default is @py.
    """,
)
@click.argument(
    'resource_manager',
    default=None,
    required=False,
    type=str,  # , help="name of the pyvisa resource manager (@ivi, @sim, or @py)", default='@py'
)
@click.option(
    '--stubs',
    default=False,
    is_flag=True,
    help='output as class definition stubs instead of a summary table',
)
def visa_probe(resource_manager, stubs):
    import labbench as lb

    lb.util.force_full_traceback(False)

    if stubs:
        prefix = '# '
    else:
        prefix = ''

    if resource_manager == '@py':
        url = r'https://pyvisa.readthedocs.io/projects/pyvisa-py/en/latest/installation.html'

        missing_support = lb._backends._visa_missing_pyvisapy_support()

        if len(missing_support) > 0:
            missing_support = ', '.join([repr(s) for s in missing_support])
            print(
                f'{prefix}Resource type(s) {missing_support} were not probed. To install support in pyvisa-py,',
                file=sys.stderr,
            )
            print(f'{prefix}see: {url}\n', file=sys.stderr)

    lb.visa_default_resource_manager(resource_manager)
    devices = lb.visa_probe_devices()

    if len(devices) == 0:
        print(
            f'{prefix}did not detect any devices available on resource manager {lb.VISADevice._rm!r}',
            file=sys.stderr,
        )
        return

    if stubs:
        print(
            f'# Autogenerated stubs discovered in pyvisa resource manager {lb.VISADevice._rm!r}'
        )
        print(synthesize_device_stubs(devices))
    else:
        print(f'Resources discovered on resource manager {lb.VISADevice._rm!r}:')
        for device in devices:
            summarize_device_probe(device)


if __name__ == '__main__':
    do_cli()
