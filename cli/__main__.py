#!python3

# Command line tool for lab experiments using labbench.Rack objects

import sys

# sys.path.insert(0,'.')

try:
    import click
    import inspect
    from pathlib import Path
except KeyboardInterrupt:
    # skip the trace dump on ctrl+c
    sys.exit(1)

EMPTY = inspect.Parameter.empty


def empty_rack(cls):
    """instantiate cls, filling in owned objects that have no default value """
    init_params = inspect.signature(cls).parameters
    init_kws = {
        name: cls.__annotations__[name]() if param.default is EMPTY else param.default
        for name, param in init_params.items()
    }
    return cls(**init_kws)


def do_cli():
    try:
        cli()
    except KeyboardInterrupt:
        sys.exit(1)


@click.group(help="configure and run labbench Rack objects")
def cli():
    pass


@cli.command(
    name="init",
    help="""Initialize a new Rack configuration from a python source file.
    
    The configuration consists of a directory of autogenerated stub files. The python source code
    in PYFILE is compiled and executed to access the Rack class named RACK_NAME.
    A new directory is created at DEST that consists of serialized configuration files and table stubs
    for defining sequence execution. There must be no existing file or directory at DEST unless
    the force flag is set. When compiling PYFILE, python imports follow PYTHONPATH as normal.""",
)
@click.argument(
    "pyfile", type=str
)  # , help='name of the rack class to import, e.g., "modulename.MyRack"')
@click.option(
    "--cls", type=str, help="use this Rack in PYFILE instead of the module namespace"
)
@click.option(
    "--pythonpath",
    type=click.Path(exists=True, file_okay=False, readable=True),
    help="change the default import path to append to PYTHONPATH",
)
@click.option(
    "--output", type=click.Path(exists=False), help="change the output directory"
)
@click.option("--force", is_flag=True, help="overwrite pre-existing files")
@click.option(
    "--with-defaults",
    is_flag=True,
    help="include sequence columns that have default values",
)
@click.option(
    "--with-defaults",
    is_flag=True,
    help="include sequence columns that have default values",
)
def init(
    pyfile, cls=None, pythonpath=None, output=None, force=False, with_defaults=False
):
    if pythonpath is None:
        pythonpath = Path(pyfile).parent

    # delay the labbench import so that e.g. --help is faster
    import labbench as lb

    lb._force_full_traceback(True)

    cls = lb._rack.import_as_rack(pyfile, cls, append_path=[pythonpath])

    if output is None:
        output = cls.__qualname__

    rack = empty_rack(cls)

    lb.dump_rack(
        rack,
        output,
        sourcepath=pyfile,
        exist_ok=force,
        with_defaults=with_defaults,
        pythonpath=pythonpath,
    )

    print(f"initialized rack directory at {output}")


@cli.command(
    name="reset",
    help=f"""Replace a Rack configuration file with an clean stub.

    If PATH refers to a sequence table, its format must be csv and its parent must be a Rack
    directory. If it is named config.yaml, the stub will match the original source parameters,
    but overwrite the others.""",
)
@click.argument(
    "path", type=click.Path(exists=True, dir_okay=False, writable=True, readable=True)
)  # , help='path to Rack directory or sequence table file')
@click.option(
    "--with-defaults",
    is_flag=True,
    help="include sequence parameters that have defaults",
)
def reset(path, with_defaults=False):
    # delay the labbench import so that e.g. --help is faster
    import labbench as lb

    lb._force_full_traceback(True)
    path = Path(path)

    if str(path).endswith(".csv"):
        # reset a sequence table

        # pull in the rack
        rack = lb.load_rack(Path(path).parent, apply=True)

        # make_sequence_stub takes care of the introspection on the rack
        lb._serialize.make_sequence_stub(
            rack, path.stem, path.parent, with_defaults=with_defaults
        )
        print(f'reset "{path}" to stub')
    elif path.endswith(".yaml"):
        raise NotImplementedError

        # reset a config.yaml

        # TODO: this is untested
        rack = lb.load_rack(path, apply=False)

        lb.dump_rack(rack, path, exist_ok=True, with_defaults=with_defaults)


@cli.command(
    name="run",
    help="""Step through calls to a Rack sequence defined in a CSV table.

    The parent directory of the csv file needs to have a config.yaml as generated by the
    `init` command. The rack class is imported from the csv's parent directory, run from
    the context of the current working directory and PYTHONPATH.""",
)
@click.argument(
    "csv_path", type=click.Path(exists=True)
)  # , help='path to the config directory')
@click.option(
    "--notebook",
    is_flag=True,
    type=bool,
    help="show formatted progress when run in a notebook",
)
def run(csv_path, notebook=False):
    csv_path = Path(csv_path)
    config_dir = csv_path.parent
    sequence_name = csv_path.stem

    # delay the labbench import so that e.g. --help is faster
    import labbench as lb

    lb._force_full_traceback(True)

    # instantiate a Rack from config.yaml
    rack = lb.load_rack(config_dir, apply=True)

    if notebook:
        from labbench import notebooks

        notebooks.display(notebooks.panel(rack))

    # get the callable bound sequence before connection
    # in case it does not exist
    bound_seq = getattr(rack, sequence_name)

    # instantiate the rack, binding the Sequence method
    with rack:
        # ...and run the sequence object
        row_iterator = bound_seq.iterate_from_csv(csv_path)
        for i, (row, result) in enumerate(row_iterator):
            pass


if __name__ == "__main__":
    do_cli()
