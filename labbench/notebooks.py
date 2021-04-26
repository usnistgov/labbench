# This software was developed by employees of the National Institute of
# Standards and Technology (NIST), an agency of the Federal Government.
# Pursuant to title 17 United States Code Section 105, works of NIST employees
# are not subject to copyright protection in the United States and are
# considered to be in the public domain. Permission to freely use, copy,
# modify, and distribute this software and its documentation without fee is
# hereby granted, provided that this notice and disclaimer of warranty appears
# in all copies.
#
# THE SOFTWARE IS PROVIDED 'AS IS' WITHOUT ANY WARRANTY OF ANY KIND, EITHER
# EXPRESSED, IMPLIED, OR STATUTORY, INCLUDING, BUT NOT LIMITED TO, ANY WARRANTY
# THAT THE SOFTWARE WILL CONFORM TO SPECIFICATIONS, ANY IMPLIED WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE, AND FREEDOM FROM
# INFRINGEMENT, AND ANY WARRANTY THAT THE DOCUMENTATION WILL CONFORM TO THE
# SOFTWARE, OR ANY WARRANTY THAT THE SOFTWARE WILL BE ERROR FREE. IN NO EVENT
# SHALL NIST BE LIABLE FOR ANY DAMAGES, INCLUDING, BUT NOT LIMITED TO, DIRECT,
# INDIRECT, SPECIAL OR CONSEQUENTIAL DAMAGES, ARISING OUT OF, RESULTING FROM,
# OR IN ANY WAY CONNECTED WITH THIS SOFTWARE, WHETHER OR NOT BASED UPON
# WARRANTY, CONTRACT, TORT, OR OTHERWISE, WHETHER OR NOT INJURY WAS SUSTAINED
# BY PERSONS OR PROPERTY OR OTHERWISE, AND WHETHER OR NOT LOSS WAS SUSTAINED
# FROM, OR AROSE OUT OF THE RESULTS OF, OR USE OF, THE SOFTWARE OR SERVICES
# PROVIDED HEREUNDER. Distributions of NIST software should also include
# copyright and licensing statements of any third-party software that are
# legally bundled with the code in compliance with the conditions of those
# licenses.

from . import _device as core

from ._backends import VISADevice
from ._host import Host
from .util import show_messages
from ._rack import Rack

import logging
import time
from io import StringIO
import numbers
import builtins

import pandas as pd
import numpy as np

import ipywidgets as widgets
from ipywidgets import IntProgress, HTML, VBox
from IPython.display import display

__all__ = ['panel', 'log_progress']

skip_state_by_type = {VISADevice: ['identity'],
                      Host: ['log'],
                      core.Device: ['connected']
                      }

__wrapped__ = dict(range=builtins.range,
                   linspace=np.linspace)

def single(inst, inst_name):
    """ Generate a formatted html table widget which updates with the most recently observed states
        in a device.
        :param inst: the device to monitor, an instance of :class:`labbench.Device` (or one of its subclasses)
        :param inst_name: the name to use to label the table
        :returns: :class:`ipywidgdets.HBox` instance containing a single :class:`ipywidgets.HTML` instance
    """

    _df = pd.DataFrame([], columns=['value'])
    table_styles = [{'selector': '.col_heading, .blank',
                     'props': [('display', 'none;')]}]
    caption_fmt = '<center><b>{}<b></center>'

    skip_attrs = []
    for cls, skip in skip_state_by_type.items():
        if isinstance(inst, cls):
            skip_attrs += skip

    html = widgets.HTML()

    def _on_change(change):
        obj, name, value = change['owner'], change['name'], change['new']

        # if name == 'connected':
        #     if value:
        #         html.layout.visibility = 'visible'
        #     else:
        #         html.layout.visibility = 'hidden'

        if name in skip_attrs:
            return

        if hasattr(obj, 'connected') and name != 'connected' and not obj.connected:
            if name in _df.index:
                _df.drop(name, inplace=True)
            return
        label = obj._traits[name].label
        _df.loc[name] = str(value) + ' ' + str('' if label is None else label),
        _df.sort_index(inplace=True)
        caption = caption_fmt.format(inst_name).replace(',', '<br>')
        html.value = _df.style.set_caption(caption).set_table_attributes(
            'class="table"').set_table_styles(table_styles).render()

    core.observe(inst, _on_change)

    return widgets.HBox([html])


class TextareaLogHandler(logging.StreamHandler):
    log_format = '%(asctime)s.%(msecs).03d %(levelname)10s %(message)s'
    time_format = '%Y-%m-%d %H:%M:%S'
    max_buffer = 10000
    min_delay = 0.1

    def __init__(self, level=logging.DEBUG):
        self.stream = StringIO()
        super(TextareaLogHandler, self).__init__(self.stream)
        self.widget = widgets.Textarea(
            layout=widgets.Layout(width='100%', height='500px'))
        self.setFormatter(logging.Formatter(self.log_format, self.time_format))
        self.setLevel(level)
        self.last_time = None

    def emit(self, record):
        ret = super(TextareaLogHandler, self).emit(record)
        if self.last_time is None or time.time() - self.last_time > self.min_delay:
            self.last_time = time.time()
            newvalue = self.widget.value + self.stream.getvalue()
            if len(newvalue) > self.max_buffer:
                newvalue = newvalue[-self.max_buffer:]
            self.widget.value = newvalue
        return ret


class panel(object):
    """ Show tables summarizing value traits and property traits in jupyter notebook.
    Only a single panel will be shown in a python kernel.

    :param source: Either an integer indicating how far up the calling tree to search\
    for Device instances, or a `labbench.Rack` instance.
    :param ncols: Maximum number of devices to show on each row
    """

    widget = None
    ncols = 2
    devices = {}
    children = []

    def __new__(cls, source=2, ncols=2):
        cls.ncols = ncols

        if isinstance(source, Rack):
            cls.devices = dict([(k,v) for k,v in source.get_managed_contexts().items()\
                                if isinstance(v,core.Device)])
        elif isinstance(source, numbers.Number):
            cls.source = source
            cls.devices = core.list_devices(source)
        else:
            raise ValueError(
                f'source must be a Rack instance or int, but got {repr(source)}')

        children = [single(cls.devices[k], k) for k in sorted(cls.devices.keys())
                    if isinstance(cls.devices[k], core.Device)]

        if len(children) == 0:
            return cls

        hboxes = []
        while True:
            N = min(ncols, len(children))

            try:
                hboxes.append(widgets.HBox(children[:N]))
            # Sometimes stale source._contexts leads to AttributeError.
            # Delete them and try again
            except AttributeError:
                if hasattr(source, '_contexts'):
                    return cls(source=cls.source, ncols=cls.ncols)
                else:
                    raise
            if N < len(children):
                children = children[N:]
            else:
                break

        vbox = widgets.VBox(hboxes)

        show_messages('error')
        log_handler = TextareaLogHandler()
        logger = logging.getLogger('labbench')

        logger.addHandler(log_handler)

        cls.widget = widgets.Tab([vbox, log_handler.widget])

        cls.widget.set_title(0, 'State')
        cls.widget.set_title(1, 'Debug')

        display(cls.widget)

        return cls


def range(*args, **kws):
    """ the same as python `range`, but with a progress bar representing progress
        iterating through the range
    """
    title = kws.pop('title', None)
    return log_progress(__wrapped__['range'](*args, **kws), title=title)


def linspace(*args, **kws):
    """ the same as numpy.linspace, but with a progress bar representing progress
        iterating through the range, and an optional title= keyword argument to
        set the title
    """
    title = kws.pop('title', None)
    return log_progress(__wrapped__['linspace'](*args, **kws), title=title)


def log_progress(sequence, every=None, size=None, title=None):
    """
    Indicate slow progress through a long sequence.

    This code is adapted here from https://github.com/alexanderkuk/log-progress
    where it was provided under the MIT license.

    :param sequence: iterable to monitor
    :param every: the number of iterations to skip between updating the progress bar, or None to update all
    :param size: number of elements in the sequence (required only for generators with no length estimate)
    :param title: title text
    :return: iterator that yields the elements of `sequence`
    """

    is_iterator = False
    if size is None:
        try:
            size = len(sequence)
        except TypeError:
            is_iterator = True
    if size is not None:
        if every is None:
            if size <= 200:
                every = 1
            else:
                every = size / 200  # every 0.5%
    else:
        assert every is not None, 'sequence is iterator, set every'

    if is_iterator:
        progress = IntProgress(min=0, max=1, value=1)
        progress.bar_style = 'info'
    else:
        progress = IntProgress(min=0, max=size, value=0)
    label = HTML()
    box = VBox(children=[label, progress])
    display(box)

    if title is not None:
        title = f'{title} '
    else:
        title = ''

    index = 0
    try:
        for index, record in enumerate(sequence, 1):
            if index == 1 or index % every == 0:
                if is_iterator:
                    label.value = f'{title}{index} / ?'
                else:
                    progress.value = index
                    label.value = f'{title}{index} / {size}'
            yield record
    except BaseException:
        progress.bar_style = 'danger'
        raise
    else:
        progress.bar_style = 'success'
        progress.value = index
        label.value = f'{title}Finished {index}'

np.linspace = linspace
__builtins__.range = range