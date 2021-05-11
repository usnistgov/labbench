#!python3

# Command line tool for manipulating the yaml files in COVID-19 spectrum monitoring data

import sys
sys.path.insert(0,'.')

import click
from pathlib import Path
from numbers import Number
# import shutil
import labbench as lb
lb._force_full_traceback(True)
from labbench._rack import FileRackMapping
import importlib


@click.group(help="configure a rack and run sequences")
def cli():
    pass


@cli.command(name='init', help="""
    Start a new configuration directory for a labbench Rack.
    
    Do "from <module> import <class-name>", and introspect on the class
    to autogenerate template configuration files. The configuration
    output is a new directory specified by CONFIG-DIR. There must be no
    existing file or directory in this path. Python imports follow the context of the
    current working directory and PYTHONPATH as normal.
""")
@click.argument('module', type=str)#, help='name of the rack class to import, e.g., "modulename.MyRack"')
@click.argument('class-name', type=str)#, help='name of the rack class to import, e.g., "modulename.MyRack"')
@click.argument('config-dir', type=click.Path(exists=False))#, help='path to the output directory')
def init(module, class_name, config_dir):
    module = importlib.import_module(module)
    cls = getattr(module, class_name)
    file_map = FileRackMapping(cls)
    file_map.init(Path(config_dir))


@cli.command(name='rewrite', help="""
    Replace an existing template table csv with a template.

    The csv output contains a single row specifying column headers of the 
    sequence. To determine the expanded variables to run, the rack class is imported
    for introspection (as defined in "<CONFIG-DIR>/rack.yaml") in the context
    of the current working directory and PYTHONPATH. The table specifying the
    sequence to run is written to "<CONFIG-DIR>/<SEQUENCE-NAME>.csv".
""")
@click.argument('config-dir', type=click.Path(exists=True))#, help='path to the config directory')
@click.argument('sequence-name', type=str)#, help='name of the sequence to update')
@click.option('--with-defaults', is_flag=True, help='include sequence parameters that have defaults')
def init_table(config_dir, sequence_name, with_defaults=False):
    pass


@cli.command(name='run', help="""
    Run a test sequence.

    The rack class specified in "<CONFIG-DIR>/rack.yaml" will be imported in the context
    of the current working directory and PYTHONPATH. The table specifying the
    sequence to run is loaded from "<CONFIG-DIR>/<SEQUENCE-NAME>.csv".
""")
@click.argument('config-dir', type=click.Path(exists=True))
@click.argument('sequence-name', type=str)
def run(config_dir, sequence_name):
    pass


if __name__ == '__main__':
    cli()
