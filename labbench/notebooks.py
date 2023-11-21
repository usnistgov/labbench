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
from .paramattr import observe, get_class_attrs

import logging
import time
from io import StringIO
import numbers

import pandas as pd

import ipywidgets as widgets
from IPython.display import display

skip_traits = {VISADevice: ["identity"], Host: ["log"], core.Device: ["isopen"]}


def trait_table(device):
    """Generate a formatted html table widget which updates with recently-observed properties
    in a device.

    Arguments:
        device: the device to monitor, an deviceance of :class:`labbench.Device` (or one of its subclasses)
    Returns:
        `ipywidgdets.HBox` containing one `ipywidgets.HTML` widget
    """

    _df = pd.DataFrame([], columns=["value"])

    TABLE_STYLES = [
        {"selector": ".col_heading, .blank", "props": [("display", "none;")]}
    ]

    CAPTION_FMT = "<center><b>{}<b></center>"

    skip_attrs = []
    for cls, skip in skip_traits.items():
        if isinstance(device, cls):
            skip_attrs += skip

    html = widgets.HTML()

    def on_change(change):
        obj, name, value = change["owner"], change["name"], change["new"]

        if name != "isopen":
            print(name, value)

        # if name == 'isopen':
        #     if value:
        #         html.layout.visibility = 'visible'
        #     else:
        #         html.layout.visibility = 'hidden'

        if name in skip_attrs:
            return

        if hasattr(obj, "isopen") and name != "isopen" and not obj.isopen:
            if name in _df.index:
                _df.drop(name, inplace=True)
            return
        else:
            print(name)
        label = get_class_attrs(obj)[name].label
        _df.loc[name] = (str(value) + " " + str("" if label is None else label),)
        _df.sort_index(inplace=True)
        caption = CAPTION_FMT.format(obj._owned_name or repr(obj)).replace(",", "<br>")
        html.value = (
            _df.style.set_caption(caption)
            .set_table_attributes('class="table"')
            .set_table_styles(TABLE_STYLES)
            .render()
        )

    observe(device, on_change)

    return widgets.HBox([html])


class TextareaLogHandler(logging.StreamHandler):
    log_format = "%(asctime)s.%(msecs).03d %(levelname)10s %(message)s"
    time_format = "%Y-%m-%d %H:%M:%S"
    max_buffer = 10000
    min_delay = 0.1

    def __init__(self, level=logging.DEBUG):
        self.stream = StringIO()
        super(TextareaLogHandler, self).__init__(self.stream)
        self.widget = widgets.Textarea(
            layout=widgets.Layout(width="100%", height="500px")
        )
        self.setFormatter(logging.Formatter(self.log_format, self.time_format))
        self.setLevel(level)
        self.last_time = None

    def emit(self, record):
        ret = super(TextareaLogHandler, self).emit(record)
        if self.last_time is None or time.time() - self.last_time > self.min_delay:
            self.last_time = time.time()
            newvalue = self.widget.value + self.stream.getvalue()
            if len(newvalue) > self.max_buffer:
                newvalue = newvalue[-self.max_buffer :]
            self.widget.value = newvalue
        return ret


class panel:
    """Show tables summarizing value traits and property traits in jupyter notebook.
    Only a single panel will be shown in a python kernel.

    Arguments:
        source: Either an integer indicating how far up the calling tree to
                search for Device instances, or a `labbench.Rack` instance.
        ncols: Maximum number of devices to show on each row
    """

    widget = None
    ncols = 2
    devices = {}
    children = []

    def __new__(cls, source=1, ncols=2):
        cls.ncols = ncols

        if isinstance(source, Rack):
            cls.devices = dict(
                [
                    (k, v)
                    for k, v in source._ownables.items()
                    if isinstance(v, core.Device)
                ]
            )
        elif isinstance(source, numbers.Number):
            cls.source = source + 1
            cls.devices = core.list_devices(cls.source)
        else:
            raise ValueError(
                f"source must be a Rack instance or int, but got {repr(source)}"
            )

        children = [
            trait_table(cls.devices[k])
            for k in sorted(cls.devices.keys())
            if isinstance(cls.devices[k], core.Device)
        ]

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
                if hasattr(source, "_contexts"):
                    return cls(source=cls.source, ncols=cls.ncols)
                else:
                    raise
            if N < len(children):
                children = children[N:]
            else:
                break

        vbox = widgets.VBox(hboxes)

        show_messages("error")
        log_handler = TextareaLogHandler()
        logger = logging.getLogger("labbench")

        logger.addHandler(log_handler)

        cls.widget = widgets.Tab([vbox, log_handler.widget])

        cls.widget.set_title(0, "State")
        cls.widget.set_title(1, "Debug")

        display(cls.widget)

        return cls
