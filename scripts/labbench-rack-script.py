#!python3

# Command line tool for manipulating the yaml files in COVID-19 spectrum monitoring data

import click
from pathlib import Path
import sys
from numbers import Number
# import shutil
from labbench._rack import FileRackMapping


HELP = "configure and run labbench racks"


@click.group(help=HELP)
def cli():
    pass


@cli.command(name='init', help="""
    Start a new configuration directory for a labbench Rack.
    
    Imports the string RACK-CLASS (e.g., "modulename.MyRack"), and autogenerates template
    configuration files in a new directory specified by CONFIG-DIR. There must be no
    existing file or directory in this path. Python imports follow the context of the
    current working directory and PYTHONPATH as normal.
""")
@click.argument('rack-class', type=str)#, help='name of the rack class to import, e.g., "modulename.MyRack"')
@click.argument('config-dir', type=click.Path(exists=False))#, help='path to the output directory')
def init(rack_class, config_dir):
    pass


@cli.command(name='rewrite', help="""
    Replace an existing template table csv with a template.

    The csv output contains a single row specifying column headers of the 
    sequence. To determine the expanded variables to run, the rack class is imported
    for introspection (as defined in "<CONFIG-DIR>/config.yaml") in the context
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

    The rack class specified in "<CONFIG-DIR>/config.yaml" will be imported in the context
    of the current working directory and PYTHONPATH. The table specifying the
    sequence to run is loaded from "<CONFIG-DIR>/<SEQUENCE-NAME>.csv".
""")
@click.argument('config-dir', type=click.Path(exists=True))
@click.argument('sequence-name', type=str)
def run(config_dir, sequence_name):
    pass


if __name__ == '__main__':
    cli()
