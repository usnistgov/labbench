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


from contextlib import suppress, ExitStack, contextmanager
from ._core import Device, observe
from ._rack import Owner
from . import _host
from . import _core as core
from . import util as util
import copy
import inspect
import io
import logging
import os
import pickle
import shutil
import textwrap
import tarfile
import warnings

logger = util.logger

__all__ = ['LogAggregator', 'RelationalTableLogger',
           'CSVLogger', 'SQLiteLogger',
           'read', 'read_relational', 'to_feather']


class MungerBase(core.Device):
    """ This is where ugly but necessary sausage making organizes
        in a file output with a key in the master database.

        The following conversions to relational files are attempted in order to
        convert each value in the row dictionary:

        1. Text containing a valid file or directory *outside* of the root data
           directory is made relational by moving the file or directory into
           the current row. The text is replaced with the updated relative path;
        2. Text longer than `text_relational_min` is dumped into a relational
           text file;
        3. 1- or 2-D data is converted to a pandas Series or DataFrame, and
           dumped into a relational file defined by the extension set by
           `nonscalar_file_type`

    """

    resource: core.Unicode(
        '', help='base directory for all data')

    text_relational_min: core.Int(
        1024, min=0, help='minimum size threshold that triggers storing text in a relational file')

    force_relational: core.List(
        ['host_log'], help='list of column names to always save as relational data')

    dirname_fmt: core.Unicode(
        '{id} {host_time}', help='directory name format for the relational data of each row (keyed on column)')

    nonscalar_file_type: core.Unicode(
        'csv', help='file format for non-scalar numerical data')

    metadata_dirname: core.Unicode(
        'metadata', help='subdirectory name for metadata')

    def __call__(self, index, row):
        """
        Break special cases of row items that need to be stored in
        relational files. The row valueis replaced in-place with the relative
        path to the data saved on disk.

        :param row: dictionary of {'entry_name': "entry_value"} pairs
        :return: the row dictionary, replacing special entries with the relative path to the saved data file
        """
        def is_path(v):
            if not isinstance(v, str):
                return False
            try:
                return os.path.exists(v)
            except ValueError:
                return False

        for name, value in row.items():
            # A path outside the relational database tree
            if is_path(value):
                # A file or directory that should be moved in
                row[name] = self._from_external_file(name, value, index, row)

            # A long string that should be written to a text file
            elif isinstance(value, (str, bytes)):
                if len(value) > self.settings.text_relational_min\
                   or name in self.settings.force_relational:
                    row[name] = self._from_text(name, value, index, row)
            elif hasattr(value, '__len__') or hasattr(value, '__iter__'):
                # vector, table, matrix, etc.
                row[name] = self._from_nonscalar(name, value, index, row)
        return row

    def write_metadata(self, name, key):
        import pandas as pd

        if os.path.exists(os.path.join(self.settings.resource, self.settings.metadata_dirname)):
            return

        summary = {}
        for dev, devname in name.items():
            for trait in dev:
                name = key(devname, trait.name)
                value = getattr(dev, trait.name)
                if isinstance(value, (str, bytes)):
                    if len(value) > self.settings.text_relational_min:
                        self._from_text(name, value)
                    else:
                        summary[name] = value
                elif hasattr(value, '__len__') or hasattr(value, '__iter__'):
                    if not hasattr(value, '__len__') or len(value) > 0:
                        self._from_nonscalar(name, value)
                    else:
                        summary[name] = ''
                else:
                    summary[name] = value

        metadata = dict(#self.metadata,
                        summary=pd.DataFrame([summary], index=['Value']).T)

        for k, v in metadata.items():
            df = pd.DataFrame(v)
            if df.shape[0] == 1:
                df = df.T
            stream = self._open_metadata(k + '.txt')
            if hasattr(stream, 'overwrite'):
                stream.overwrite = True

            # Workaround for bytes/str encoding quirk underlying pandas 0.23.1
            try:
                df.to_csv(stream)
            except TypeError:
                with io.TextIOWrapper(stream, newline='\n') as buf:
                    df.to_csv(buf)

    def _from_nonscalar(self, name, value, index=0, row=None):
        """ Write nonscalar (potentially array-like, or a python object) data
        to a file, and return a path to the file

        :param name: name of the entry to write, used as the filename
        :param value: the object containing array-like data
        :param row: row dictionary, or None (the default) to write to the metadata folder
        :return: the path to the file, relative to the directory that contains the master database
        """

        import pandas as pd

        def write(stream, ext, value):
            if ext == 'csv':
                value.to_csv(stream)
            elif ext == 'json':
                value.to_json(stream)
            elif ext in ('p', 'pickle'):
                pickle.dump(value, stream, 2)
            elif ext == 'feather':
                to_feather(value, stream)
            elif ext == 'db':
                raise Exception('sqlite not implemented for relational files')
            else:
                raise Exception(
                    f"extension {ext} doesn't match a known format")

        if hasattr(value, '__len__') and len(value) == 0:
            return ''

        if row is None:
            ext = 'csv'
        else:
            ext = self.settings.nonscalar_file_type

        try:
            value = pd.DataFrame(value)
            if value.shape[0] == 0:
                value = pd.DataFrame([value])
        except BaseException:
            # We couldn't make a DataFrame
            self.logger.error(
                f"Failed to form DataFrame from {repr(name)}; pickling object instead")
            ext = 'pickle'
        finally:
            if row is None:
                stream = self._open_metadata(name + '.' + ext)
            else:
                stream = self._open_relational(name + '.' + ext, index, row)

            # Workaround for bytes/str encoding quirk underlying pandas 0.23.1
            try:
                write(stream, ext, value)
            except TypeError:
                with io.TextIOWrapper(stream, newline='\n') as buf:
                    write(buf, ext, value)
            return self._get_key(stream)

    def _from_external_file(self, name, old_path,
                            index=0, row=None, ntries=10):
        basename = os.path.basename(old_path)
        with self._open_relational(basename, index, row) as buf:
            new_path = buf.name

        self._import_from_file(old_path, new_path)

        return self._get_key(new_path)

    def _from_text(self, name, value, index=0, row=None, ext='.txt'):
        """ Write a string data to a file

        :param name: name of the parameter (helps to determine file path)
        :param value: the string to write to file
        :param row: the row to infer timestamp, or None to write to metadata
        :param ext: file extension
        :return: the path to the file, relative to the directory that contains the master database
        """
        with self._open_relational(name + ext, index, row) as f:
            f.write(bytes(value, encoding='utf-8'))
        return self._get_key(f)

    # The following methods need to be implemented in subclasses.
    def _get_key(self, buf):
        """ Key to use for the relative data in the master database?

        :param stream: stream for writing to the relational data file
        :return: the key
        """
        raise NotImplementedError

    def _open_relational(self, name, index, row):
        """ Open a stream / IO buffer for writing relational data, given
            the master database column, index, and the row dictionary.

            :param name: the column name of the relational data in the master db
            :param index: the index name of of the data in the master db
            :param row: the dictionary containing the row of data at `index`

            :returns: an open buffer object for writing data
        """
        raise NotImplementedError

    def _open_metadata(self, name):
        """ Open a stream / IO buffer for writing metadata, given
            the name of the metadata.

            :returns: an open buffer object for writing metadata to the file
        """

        raise NotImplementedError

    def _import_from_file(self, old_path, dest):
        raise NotImplementedError


class MungeToDirectory(MungerBase):
    """ Implement data munging into subdirectories. This is fast but can produce
        an unweildy number of subdirectories if there are many runs.
    """

    def _open_relational(self, name, index, row):
        if 'host_time' not in row:
            self.logger.error(
                "no timestamp yet from host yet; this shouldn't happen :(")

        relpath = self._make_path_heirarchy(index, row)
        if not os.path.exists(relpath):
            os.makedirs(relpath)

        return open(os.path.join(relpath, name), 'wb+')

    def _open_metadata(self, name):
        dirpath = os.path.join(self.settings.resource, self.settings.metadata_dirname)
        with suppress(FileExistsError):
            os.makedirs(dirpath)
        return open(os.path.join(dirpath, name), 'wb+')

    def _get_key(self, stream):
        """ Key to use for the relative data in the master database?

        :param stream: stream for writing to the relational data file
        :return: the key
        """
        return os.path.relpath(stream.name, self.settings.resource)

    def _import_from_file(self, old_path, dest):
        # Retry moves for several seconds in case the file is in the process
        # of being closed
        @util.until_timeout(PermissionError, 5, delay=0.5)
        def move():
            os.rename(old_path, dest)

        try:
            move()
            self.logger.debug(f'moved {repr(old_path)} to {repr(dest)}')
        except PermissionError:
            self.logger.warning(
                'relational file was still open in another program; fallback to copy instead of rename')
            import shutil
            shutil.copyfile(old_path, dest)

    def _make_path_heirarchy(self, index, row):
        relpath = self.settings.dirname_fmt.format(id=index, **row)

        # TODO: Find a more generic way to force valid path name
        relpath = relpath.replace(':', '')
        relpath = os.path.join(self.settings.resource, relpath)
        return relpath


class TarFileIO(io.BytesIO):
    """ For appending data into new files in a tarfile
    """

    def __init__(self, open_tarfile, relname, mode='w', overwrite=False):
        #        self.tarbase = tarbase
        #        self.tarname = tarname
        self.tarfile = open_tarfile
        self.overwrite = False
        self.name = relname
        self.mode = mode
        super(TarFileIO, self).__init__()

    def __del__(self):
        logger.warning('tarfile __del__')
        try:
            super(TarFileIO, self).close()
        except ValueError:
            pass

        super(TarFileIO, self).__del__()

#    def write(self, data, encoding='ascii'):
#        if isinstance(data, str):
#            data = bytes(data, encoding=encoding)
#        super(TarFileIO,self).write(data)
#
    def close(self):
        # First: dump the data into the tar file
        #        tarpath = os.path.join(self.tarbase, self.tarname)
        #        f = tarfile.open(tarpath, 'a')

        try:
            if not self.overwrite and self.name in self.tarfile.getnames():
                raise IOError(f'{self.name} already exists in {self.tarfile.name}')

            tarinfo = tarfile.TarInfo(self.name)
            tarinfo.size = self.tell()

            self.seek(0)

            self.tarfile.addfile(tarinfo, self)

        # Then make sure to close everything
        finally:
            super(TarFileIO, self).close()


class MungeToTar(MungerBase):
    """ Implement data munging into a tar file. This is slower than
        MungeToDirectory but is tidier on the filesystem.
    """

    tarname = 'data.tar'

    def _open_relational(self, name, index, row):
        if 'host_time' not in row:
            self.logger.error(
                "no timestamp yet from host yet; this shouldn't happen :(")

        relpath = os.path.join(self.settings.dirname_fmt.format(id=index, **row), name)

        return TarFileIO(self.tarfile, relpath)

    def _open_metadata(self, name):
        dirpath = os.path.join(self.settings.metadata_dirname, name)
        return TarFileIO(self.tarfile, dirpath)

    def open(self):
        if not os.path.exists(self.settings.resource):
            with suppress(FileExistsError):
                os.makedirs(self.settings.resource)
        self.tarfile = tarfile.open(os.path.join(self.settings.resource, self.tarname), 'a')

    def close(self):
        logger.warning('MungeToTar cleanup()')
        self.tarfile.close()

    def _get_key(self, buf):
        """ Where is the file relative to the master database?

        :param path: path of the file
        :return: path to the file relative to the master database
        """
        return buf.name

    def _import_from_file(self, old_path, dest):
        info = self.tar.gettarinfo(old_path)
        info.name = dest
        self.tar.addfile(old_path, info)

        @util.until_timeout(PermissionError, 5, delay=0.5)
        def remove():
            try:
                shutil.rmtree(old_path)
            except NotADirectoryError:
                os.remove(old_path)

        try:
            remove()
            self.logger.debug(f'moved {old_path} to into tar file as {dest}')
        except PermissionError:
            self.logger.warning(
                f'could not remove old file or directory {old_path}')


class LogAggregator(Owner, util.Ownable):
    """ Aggregate state information from multiple devices. This can be the basis
        for automatic database logging.
    """

    def __init__(self):
        super().__init__()

        # Map the state instance of a device (key) to a name (value)
        self.name = {}

        # These dictionaries are keyed by Device instance
        self.__always = {}
        self.__never = {}
        self.__auto = {}

        self.logger = logger.logger.getChild(self.__class__.__qualname__)
        self.logger = logging.LoggerAdapter(self.logger, dict(origin=f" - {self.__class__.__qualname__}"))

        super().__init__()

    def __repr__(self):
        return f"{self.__class__.__qualname__}()"
        
    def __owner_init__(self, rack):
        # If `self` lives in a Rack, this is called.
        # Observe changes in its Device instances
        self.set_device_labels(**rack._devices)
        self.set_device_labels(**dict(((n+'_settings',d.settings)\
                                       for n, d in rack._devices.items())))

        if rack is not None:
            for name, obj in rack._devices.items():
                self.observe_states(obj)
                self.observe_settings(obj)

    def key(self, device_name, state_name):
        """ Generate a name for a trait based on the names of
            a device and one of its states or settings.
        """
        return f'{device_name}_{state_name}'

    def __on_set_callback(self, change):
        """ Callback for changes observed when device states are set.

        :param dict change: callback info dictionary generated by traitlets
        :return: None
        """
        name = self.name[change['owner']]
        attr = change['name']
        self.__auto[self.key(name, attr)] = change['new']

    def set_device_labels(self, **mapping):
        """ Manually choose device name for a device instance.

            :param dict mapping: name mapping, formatted as {device_object: 'device name'}
            :returns: None
        """
        for label, device in list(mapping.items()):
            if isinstance(device, LogAggregator):
                pass
            elif not isinstance(device, (Device, Device.settings)):
                raise ValueError(f'{device} is not an instance of Device')

        self.name.update([(v, k) for k, v in list(mapping.items())])

    def observe_states(self, devices, changes=True,
                       always=[], never=['connected']):
        """ Configure Each time a device state is set from python,
            intercept the value to include in the aggregate
            state.

            Device may be a single device instance, or an
            several devices in an iterable (such as a list
            or tuple) to apply to each one.

            Subsequent calls to :func:`observe_states` replace
            the existing list of observed states for each
            device.

            :param devices: Device instance or iterable of Device instances
            
            :param bool changes: Whether to automatically log each time a state is set for the supplied device(s)
            
            :param always: name (or iterable of multiple names) of states to actively update on each call to get()
            
            :param never: name (or iterable of multiple names) of states to exclude from aggregated result (overrides :param:`always`)
        """
        # parameter checks
        if isinstance(devices, Device):
            devices = {devices: None}
        elif isinstance(devices, dict):
            pass
        elif hasattr(devices, '__iter__'):
            devices = dict([(d, None) for d in devices])
        else:
            raise ValueError('devices argument must be a device or iterable of devices')

        if isinstance(always, str):
            always = (always,)
        elif hasattr(always, '__iter__'):
            always = tuple(always)
        else:
            raise ValueError("argument 'always' must be a string or iterable of strings")

        if isinstance(never, str):
            never = (never,)
        elif hasattr(never, '__iter__'):
            never = tuple(never)
        else:
            raise ValueError("argument 'never' must be a string, or iterable of strings")        

        # generate names for any new devices
        for device, name in devices.items():
            if not isinstance(device, Device):
                raise ValueError(f'{device} is not an instance of Device')
            if device not in self.name:
                if name is None:
                    if hasattr(device, '__name__'):
                        name = device.__name__
                    else:
                        name = self.__whoisthis(device)
                self.name[device] = name

        if len(list(self.name.values())) != len(set(self.name.values())):
            raise Exception('Could not automatically determine unique names of device instances! '\
                            'Set manually with the set_label method')

        # Register handlers
        for device in devices.keys():
            if changes:
                observe(device, self.__on_set_callback)
            else:
                raise NotImplementedError('Implement me on changes=False')
                device.unobserve(self.__on_set_callback)
                device.settings.unobserve(self.__on_set_callback)
            if always:
                self.__always[device] = always
            if never:
                self.__never[device] = never

    def observe_settings(self, devices, changes=True,
                         always=[], never=[]):
        """ Configure Each time a device setting is set from python,
            intercept the value to include in the aggregate
            state.

            Device may be a single device instance, or an
            several devices in an iterable (such as a list
            or tuple) to apply to each one.

            Subsequent calls to :func:`observe_settings` replace
            the existing list of observed states for each
            device.

            :param devices: dictionary of names keyed on Device instances, a Device instance, or an iterable of Device instances

            :param bool changes: Whether to automatically log each time a state is set for the supplied device(s)

            :param always: name (or iterable of multiple names) of settings to actively update on each call to get()

            :param never: name (or iterable of multiple names) of settings to exclude from aggregated result (overrides :param:`always`)
        """
        # parameter checks
        if isinstance(devices, Device):
            devices = {devices: None}
        elif isinstance(devices, dict):
            pass
        elif hasattr(devices, '__iter__'):
            devices = dict([(d, None) for d in devices])
        else:
            raise ValueError('devices argument must be a device or iterable of devices')

        if isinstance(always, str):
            always = (always,)
        elif hasattr(always, '__iter__'):
            always = tuple(always)
        else:
            raise ValueError("argument 'always' must be a string or iterable of strings")

        if isinstance(never, str):
            never = (never,)
        elif hasattr(never, '__iter__'):
            never = tuple(never)
        else:
            raise ValueError("argument 'never' must be a string, or iterable of strings")        

        for device in devices:
            if not isinstance(device, Device):
                raise ValueError(f'{device} is not an instance of Device')
            if device.settings not in self.name:
                print('making name copy for ', device)
                newname = self.__whoisthis(device) + '_settings'
                self.name[device.settings] = newname
        if len(list(self.name.values())) != len(set(self.name.values())):
            from collections import Counter
            count = Counter(self.name.values())
            values = (repr(v) for k,v in count.most_common() if v > 1)
            print(self.name, )
            raise Exception(f"Could not automatically determine unique names of device instances {','.join(values)}. "\
                            f"Set manually with the set_label method ")

        for device in devices:
            if changes:
                observe(device.settings, self.__on_set_callback)
            else:
                core.unobserve(device.settings, self.__on_set_callback)
            if always:
                self.__always[device.settings] = always
            if never:
                self.__never[device.settings] = never

    def get(self):
        """ Aggregate and return the current device states as configured
            with :func:`observe`.

            :returns: dictionary of aggregated states. Keys are strings defined by :func:`key` (defaults to '{device name}_{state name}'). Values are the type and value of the corresponding state of the device instance.
        """

        for device, name in list(self.name.items()):
            # Perform gets for each state called out in manual_include
            if device in self.__always.keys():
                for attr in self.__always[device]:
                    if attr not in device.__traits__:
                        raise Exception(
                            f'the requested trait {attr} does not exist in {device}')
                    self.__auto[self.key(name, attr)] = getattr(device, attr)

            # Remove keys corresponding with self.__never
            if device in self.__never.keys():
                for attr in self.__never[device]:
                    try:
                        del self.__auto[self.key(name, attr)]
                    except KeyError:
                        pass

        ret = self._spy()

        return ret

    def _spy(self):
        """ Return a dictionary of the most recently observed states
            without pulling new states from any devices (but including
            states included to `always` aggregate). Does not
            include the current timestamp.
        """
        return copy.copy(self.__auto)

    def __whoisthis(self, target, from_depth=2):
        """ Introspect into the caller to name an object .

        :param target: device instance
        :param from_depth: number of callers outside of the current frame
        :return: name of the Device
        """
#        # If the context is a function, look in its first argument,
#        # in case it is a method. Search its class instance.
#        if len(ret) == 0 and len(f.frame.f_code.co_varnames)>0:
#            obj = f.frame.f_locals[f.frame.f_code.co_varnames[0]]
#            for k, v in obj.__dict__.items():
#                if isinstance(v, Device):
#                    ret[k] = v

        f = frame = inspect.currentframe()
        for i in range(from_depth):
            f = f.f_back

#        f = inspect.getouterframes(inspect.currentframe())[from_depth].frame

        for k, v in list(f.f_locals.items()):
            if v is target:
                return k

        if len(f.f_code.co_varnames) > 0:
            obj = f.f_locals[f.f_code.co_varnames[0]]
            for k, v in obj.__dict__.items():
                if v is target:
                    return k
                
        del f, frame

        raise Exception(f"failed to automatically label {repr(obj)}")


class RelationalTableLogger(LogAggregator,
                            ordered_entry=(_host.Email, MungerBase, _host.Host)):
    """ Abstract base class for loggers that queue dictionaries of data before writing
        to disk. This extends :class:`LogAggregator` to support

        #. queuing aggregate state of devices by lists of dictionaries;
        #. custom metadata in each queued aggregate state entry; and
        #. custom response to non-scalar data (such as relational databasing).

        :param str path: Base path to use for the master database

        :param bool overwrite: Whether to overwrite the master database if it exists (otherwise, append)

        :param text_relational_min: Text with at least this many characters is stored as a relational text file instead of directly in the database

        :param force_relational: A list of columns that should always be stored as relational data instead of directly in the database

        :param nonscalar_file_type: The data type to use in non-scalar (tabular, vector, etc.) relational data

        :param metadata_dirname: The name of the subdirectory that should be used to store metadata (device connection parameters, etc.)

        :param tar: Whether to store the relational data within directories in a tar file, instead of subdirectories
        
        :param git_commit_in: perform a git commit on open() if the current
            directory is inside a git repo with this branch name
    """

    index_label = 'id'

    def __init__(self,
                 path,
                 *,
                 overwrite=False,
                 text_relational_min=1024,
                 force_relational=['host_log'],
                 dirname_fmt='{id} {host_time}',
                 nonscalar_file_type='csv',
                 metadata_dirname='metadata',
                 tar=False,
                 git_commit_in=None,
                 **metadata):

        super().__init__()

        # log host introspection
        # TODO: smarter
        self.host = _host.Host(git_commit_in=git_commit_in)
        self.observe_states(self.host, always=['time', 'log'])

        # select the backend that dumps relational data
        munge_cls = MungeToTar if tar else MungeToDirectory

        self.munge = munge_cls(
            path,
            text_relational_min=text_relational_min,
            force_relational=force_relational,
            dirname_fmt=dirname_fmt,
            nonscalar_file_type=nonscalar_file_type,
            metadata_dirname=metadata_dirname,
            # **metadata
        )
        self.observe_settings(self.munge, never=self.munge.settings.__traits__)

        self.pending = []
        self.path = path
        self._overwrite = overwrite
        self.set_row_preprocessor(None)

    def __repr__(self):
        if hasattr(self, 'path'):
            path = repr(self.path)
        else:
            path = '<unset path>'
        return f"{self.__class__.__qualname__}({path})"

    def set_row_preprocessor(self, func):
        """ Define a function that is called to modify each pending data row
            before it is committed to disk. It should accept a single argument,
            a function or other callable that accepts a single argument (the
            row dictionary) and returns the dictionary modified for write
            to disk.
        """
        if func is None:
            self._row_preprocessor = lambda x: x
        elif callable(func):
            self._row_preprocessor = func
        else:
            raise ValueError('func argument must be callable or None')

    def append(self, *args, **kwargs):
        warnings.warn(f"{self.__class__.__qualname__}.append() is deprecated - use {self.__class__.__qualname__}()")
        self(*args, **kwargs)

    def __call__(self, *args, **kwargs):
        """ Add a new row of data to the list of data that awaits write
            to disk.

            This cache of pending data row is in the dictionary `self.pending`.
            Each row is represented as a dictionary of
            pairs formatted as {'column_name': 'row_value'}. These
            pairs come from a combination of 1) keyword arguments passed as
            `kwargs`, 2) a single dictionary argument, and/or 3) state traits
            configured automatically with `self.observe_states`.

            The first pass at forming the row is the single dictionary argument ::

                row = {'name1': value1, 'name2': value2, 'name3': value3}
                db.append(row)

            The second pass is to update with values as configured with
            `self.observe_states`.

            Keyword arguments are passed in as ::

                db.append(name1=value1, name2=value2, nameN=valueN)

            Simple "scalar" database types like numbers, booleans, and strings
            are added
            directly to the table. Non-scalar or multidimensional values are stored
            in a separate file (as defined in :func:`set_path_format`), and the path
            to this file is stored in the table.

            The row of data is appended to list of rows pending write to
            disk, `self.pending`. Nothing is written to disk until
            :func:`write`.

            :param bool copy=True: When `True` (the default), use a deep copy of `data` to avoid problems with overwriting references to data if `data` is reused during test. This takes some extra time; set to `False` to skip this copy operation.

            :return: the dictionary representation of the row added to `self.pending`.
        """
        do_copy = kwargs.pop('copy', None)

        # Start with input arguments
        if len(args) == 1:
            #            if not isinstance(args[0], dict):
            #                raise TypeError('argument to append must be a dictionary')
            row = copy.deepcopy(dict(args[0])) if do_copy else dict(args[0])
        elif len(args) == 0:
            row = {}

        # Pull in observed states
        row.update(copy.deepcopy(dict(self.get())
                                 if do_copy else dict(self.get())))

        # Pull in keyword arguments
        row.update(copy.deepcopy(dict(kwargs)) if do_copy else dict(kwargs))

        self.pending.append(row)
        return row

    def write(self):
        """ Commit any pending rows to the master database, converting
            non-scalar data to data files, and replacing their dictionary value
            with the relative path to the data file.

            :returns: the number of rows written
        """
        count = len(self.pending)
        if count > 0:
            proc = self._row_preprocessor
            pending = enumerate(self.pending)
            self.pending = [self.munge(self.last_index + i, proc(row))
                            for i, row in pending]
            self._write_master()
            self.clear()
        return count

    def _write_master(self):
        """ Write pending data. This is an abstract base method (must be
            implemented by inheriting classes)

            :return: None
        """
        raise NotImplementedError

    def clear(self):
        """ Remove any queued data that has been added by append.
        """
        self.pending = []

    def set_relational_file_format(self, format):
        """ Set the format to use for relational data files.

            :param str format: one of 'csv', 'json', 'feather', or 'pickle'
        """
        warnings.warn("""set_nonscalar_file_type is deprecated; set when creating
                         the database object instead with the nonscalar_output flag""")

        if format not in ('csv', 'json', 'feather', 'pickle', 'db'):
            raise Exception(
                f'relational file data format {format} not supported')
        self.munge.nonscalar_file_type = format

    def set_path_format(self, format):
        """ Set the path name convention for relational files that is used when
            a table entry contains non-scalar (multidimensional) information and will
            need to be stored in a separate file. The entry in the aggregate states table
            becomes the path to the file.

            The format string follows the syntax of python's python's built-in :func:`str.format`.\
            You may use any keys from the table to form the path. For example, consider a\
            scenario where aggregate device states includes `inst1_frequency` of `915e6`,\
            and :func:`append` has been called as `append(dut="DUT15")`. If the current\
            aggregate state entry includes inst1_frequency=915e6, then the format string\
            '{dut}/{inst1_frequency}' means relative data path 'DUT15/915e6'.

            :param format: a string compatible with :func:`str.format`, with replacement\
            fields defined from the keys from the current entry of results and aggregated states.\

            :return: None
        """
        warnings.warn("""set_path_format is deprecated; set when creating
                         the database object instead with the nonscalar_output flag""")

        self.munge.dirname_fmt = format

    # def _setup(self):

    # def __enter__(self):
    #     class MyContext:
    #
    #         def __exit__ (mself, *args):
    #
    #     self._cm = util.concurrently(host=self.host, logger=MyContext(),
    #                                  munge=self.munge, name=repr(self))
    #     self._cm.__enter__()
    #
    #     return self
    #
    # def __exit__(self, *args):
    #     if hasattr(self, '_cm'):
    #         return self._cm.__exit__(*args)

    def _setup(self):
        """ Open the file or database connection.
            This is an abstract base method (to be overridden by inheriting classes)

            :return: None
        """
        
        self.logger.debug(f'{self} setup')

        # Do some checks on the relative data directory before we consider overwriting
        # the master db.

        if os.path.exists(self.path):
            if not os.path.isdir(self.path):
                txt = f"""
                          The base directory for relative data is
                          r"{os.path.abspath(self.path)}",
                          but it already exists and is not a directory.
                          Remove or move the file at this path, or change
                          the path to the master database.
                       """
                raise IOError(textwrap.dedent(txt))

            elif self._overwrite and len(os.listdir(self.path)) > 0:
                txt = f"""
                          The master database will be overwritten, but the relative data directory,
                          r"{os.path.abspath(self.path)}",
                          already contains data entries. These would become unindexed zombie data on
                          overwriting the master database. Remove or move the relative data directory
                          before running the test.
                      """
                raise IOError(textwrap.dedent(txt))

        self.open()
        self.clear()

        if os.path.exists(self.path) and self._overwrite:
            os.remove(self.path)

        self.last_index = 0

        return self

    def _cleanup(self):
        self.logger.debug(f'{self} cleanup')
        try:
            self.write()
            if self.last_index > 0:
                self.munge.write_metadata(self.name, self.key)
        finally:
            self.close()

    def open(self, path=None):
        """ This must be implemented by a subclass to open the data storage resource.
        """
        raise NotImplementedError

    def close(self):
        """ Close the file or database connection.
            This is an abstract base method (to be overridden by inheriting classes)

            :return: None
        """
        raise NotImplementedError


class CSVLogger(RelationalTableLogger):
    """ Store data and states to disk into a master database formatted as a comma-separated value (CSV) file.

        This extends :class:`LogAggregator` to support

        #. queuing aggregate state of devices by lists of dictionaries;
        #. custom metadata in each queued aggregate state entry; and
        #. custom response to non-scalar data (such as relational databasing).

        :param str path: Base path to use for the master database
        :param bool overwrite: Whether to overwrite the master database if it exists (otherwise, append)
        :param text_relational_min: Text with at least this many characters is stored as a relational text file instead of directly in the database
        :param force_relational: A list of columns that should always be stored as relational data instead of directly in the database
        :param nonscalar_file_type: The data type to use in non-scalar (tabular, vector, etc.) relational data
        :param metadata_dirname: The name of the subdirectory that should be used to store metadata (device connection parameters, etc.)
        :param tar: Whether to store the relational data within directories in a tar file, instead of subdirectories
    """

    nonscalar_file_type = 'csv'

    def open(self):
        """ Instead of calling `open` directly, consider using
            `with` statements to guarantee proper disconnection
            if there is an error. For example, the following
            sets up a connected instance::

                with CSVLogger('my.csv') as db:
                    ### do the data acquisition here
                    pass

            would instantiate a `CSVLogger` instance, and also guarantee
            a final attempt to write unwritten data is written, and that
            the file is closed when exiting the `with` block, even if there
            is an exception.
        """
        import pandas as pd

        if not self.path.lower().endswith('.csv'):
            self.path += '.csv'
        if os.path.exists(self.path) and not self._overwrite:
            self.df = pd.read_csv(self.path, nrows=1)
            self.df.index.name = self.index_label
        else:
            self.df = None

    def close(self):
        self._write_master()

    def _write_master(self):
        """ Write queued rows of data to csv. This is called automatically on :func:`close`, or when
            exiting a `with` block.

            If the class was created with overwrite=True, then the first call to _write_master() will overwrite
            the preexisting file; subsequent calls append.
        """
        import pandas as pd

        if len(self.pending) == 0:
            return
        isfirst = self.df is None
        pending = pd.DataFrame(self.pending)
        pending.index.name = self.index_label
        pending.index += self.last_index
        if isfirst:
            self.df = pending
        else:
            self.df = self.df.append(pending).loc[self.last_index:]
        self.df.sort_index(inplace=True)
        self.last_index = self.df.index[-1]

        with open(self.path, 'a') as f:
            self.df.to_csv(f, header=isfirst, index=False)


class SQLiteLogger(RelationalTableLogger):
    """ Store data and states to disk into an an sqlite master database.

        This extends :class:`LogAggregator` to support

        #. queuing aggregate state of devices by lists of dictionaries;
        #. custom metadata in each queued aggregate state entry; and
        #. custom response to non-scalar data (such as relational databasing).

        :param str path: Base path to use for the master database
        :param bool overwrite: Whether to overwrite the master database if it exists (otherwise, append)
        :param text_relational_min: Text with at least this many characters is stored as a relational text file instead of directly in the database
        :param force_relational: A list of columns that should always be stored as relational data instead of directly in the database
        :param nonscalar_file_type: The data type to use in non-scalar (tabular, vector, etc.) relational data
        :param metadata_dirname: The name of the subdirectory that should be used to store metadata (device connection parameters, etc.)
        :param tar: Whether to store the relational data within directories in a tar file, instead of subdirectories
    """

    index_label = 'id'  # Don't change this or sqlite breaks :(
    master_filename = 'master.db'
    table_name = 'master'

    def open(self):
        """ Instead of calling `open` directly, consider using
            `with` statements to guarantee proper disconnection
            if there is an error. For example, the following
            sets up a connected instance::

                with SQLiteLogger('my.db') as db:
                    ### do the data acquisition here
                    pass

            would instantiate a `CSVLogger` instance, and also guarantee
            a final attempt to write unwritten data is written, and that
            the file is closed when exiting the `with` block, even if there
            is an exception.
        """
        self.logger.warning(f"opening for SQLite logging at {self.path}")
        import pandas as pd

        #        if not self.path.lower().endswith('.db'):
#            self.path += '.db'
        os.makedirs(self.path, exist_ok=True)
        path = os.path.join(self.path, self.master_filename)

        # Create an engine via sqlalchemy
        from sqlalchemy import create_engine  # database connection
        self._engine = create_engine('sqlite:///{}'.format(path))

        if os.path.exists(path) and not self._overwrite:
            # Read the last row to 1) list the columns and 2) get index
            query = f'select * from {self.table_name} order by {self.index_label} desc limit 1'

            df = pd.read_sql_query(query, self._engine,
                                   index_col=self.index_label)
            self._columns = df.columns
            self.last_index = df.index[-1] + 1
        else:
            self._columns = None
        self.inprogress = {}
        self.committed = {}

    def close(self):
        try:
            self._write_master()
        finally:
            try:
                self._engine.dispose()
            except BaseException:
                pass

    def _write_master(self):
        """ Write queued rows of data to the database. This also is called automatically on :func:`close`, or when
            exiting a `with` block.

            If the class was created with overwrite=True, then the first call to _write_master() will overwrite
            the preexisting file; subsequent calls append.
        """
        import pandas as pd

        if len(self.pending) == 0:
            return

        # Put together a DataFrame from self.pending that is guaranteed
        # to include the columns defined in self._columns
        state = pd.DataFrame(self.pending)
        state.index += self.last_index
        blank = pd.DataFrame(columns=self._columns)

        # Check for new columns, and insert into the database
        if self._columns is None:
            new_columns = []
        else:
            state_cols = [c.lower() for c in state.columns]
            blank_cols = [c.lower() for c in blank.columns]
            new_columns = list(set(state_cols).difference(blank_cols))

        for c in new_columns:
            self.logger.info(
                'LogSQLite inserting new state column {c} into database')
            column_type = self._sql_type_name(state[c])
            with self._engine.connect() as con:
                query = f"alter table {self.table_name} add column {c} {column_type} default NULL"
                con.execute(query)

        # Form the new database row
        df = blank.append(state, sort=True)
        df.sort_index(inplace=True)
        self._columns = df.columns

        from sqlalchemy.exc import ArgumentError

        # Append to db
        try:
            df.to_sql(self.table_name, self._engine, if_exists='append',
                      index=True, index_label=self.index_label)
        except ArgumentError:
            self.logger.error(
                f'failed to convert index label {self.index_label}')
            raise ArgumentError
        except BaseException as e:
            raise e

        self.last_index += 1

    def key(self, name, attr):
        """ The key determines the SQL column name. df.to_sql does not seem
            to support column names that include spaces
        """
        return f"{name.replace(' ', '_')}_{attr}"

    def _sql_type_name(self, col):
        from pandas.io.sql import _SQL_TYPES

        col_type = self._get_notnull_col_dtype(col)
        if col_type == 'timedelta64':
            warnings.warn("the 'timedelta' type is not supported, and will be \
                           written as integer values (ns frequency) to the\
                           database.")
            col_type = "integer"

        elif col_type == "datetime64":
            col_type = "datetime"

        elif col_type == "empty":
            col_type = "string"

        elif col_type == "complex":
            raise ValueError('Complex datatypes not supported')

        if col_type not in _SQL_TYPES:
            col_type = "string"

        return _SQL_TYPES[col_type]

    def _get_notnull_col_dtype(self, col):
        """
        Infer datatype of the Series col.  In case the dtype of col is 'object'
        and it contains NA values, this infers the datatype of the not-NA
        values.  Needed for inserting typed data containing NULLs, GH8778.
        """
        import pandas as pd

        col_for_inference = col
        if col.dtype == 'object':
            notnulldata = col[~pd.isnull(col)]
            if len(notnulldata):
                col_for_inference = notnulldata

        return pd.api.types.infer_dtype(col_for_inference)


def to_feather(data, path):
    """
    Write a dataframe to a feather file on disk. Any index will be moved
    to a column, index and column name metadata will be removed,
    and columns names will be changed to a string.

    :param data: dataframe to write to disk
    :param path: path to file to write
    :return: None

    """
    import numpy as np

    iname, data.index.name = data.index.name, None
    cname, data.columns.name = data.columns.name, None
    try:
        if not (
                data.index.is_monotonic and data.index[0] == 0 and data.index[-1] == data.shape[0] - 1):
            data = data.reset_index()
        data.columns = np.array(data.columns).astype(np.str)
        data.to_feather(path)
    finally:
        data.index.name = iname
        data.columns.name = cname


def read_sqlite(path, table_name='master', columns=None, nrows=None,
                index_col=RelationalTableLogger.index_label):
    """ Wrapper to that uses pandas.read_sql_table to load a table from an sqlite database at the specified path.

    :param path: sqlite database path
    :param table_name: name of table in the sqlite database
    :param columns: columns to query and return, or None (default) to return all columns
    :param nrows: number of rows of data to read, or None (default) to return all rows
    :param index_col: the name of the column to use as the index
    :return: pandas.DataFrame instance containing data loaded from `path`
    """

    import pandas as pd
    from sqlalchemy import create_engine

    engine = create_engine(f'sqlite:///{path}')
    df = pd.read_sql_table(
        table_name, engine, index_col=index_col, columns=columns)
    engine.dispose()
    if nrows is not None:
        df = df.iloc[:nrows]
    return df


def read(path_or_buf, columns=None, nrows=None, format='auto', **kws):
    """ Read tabular data from a file in one of various formats
    using pandas.

    :param str path: path to the  data file.
    :param columns: a column or iterable of multiple columns to return from the data file, or None (the default) to return all columns
    :param nrows: number of rows to read at the beginning of the table, or None (the default) to read all rows
    :param str format: data file format, one of ['pickle','feather','csv','json','csv'], or 'auto' (the default) to guess from the file extension
    :param kws: additional keyword arguments to pass to the pandas read_<ext> function matching the file extension
    :return: pandas.DataFrame instance containing data read from file
    """

    import pandas as pd
    from pyarrow.feather import read_feather

    reader_guess = {'p': pd.read_pickle,
                    'pickle': pd.read_pickle,
                    'db': read_sqlite,
                    'sqlite': read_sqlite,
                    'json': pd.read_json,
                    'csv': pd.read_csv}

    try:
        reader_guess.update({'f': read_feather,
                             'feather': read_feather})
    except BaseException:
        warnings.warn(
            'feather format is not available in this pandas installation, and will not be supported in labbench')

    if isinstance(path_or_buf, str):
        if os.path.getsize(path_or_buf) == 0:
            raise IOError('file is empty')

        if format == 'auto':
            format = os.path.splitext(path_or_buf)[-1][1:]
    else:
        if format == 'auto':
            raise ValueError(
                "can only guess format for string path - specify extension")

    try:
        reader = reader_guess[format]
    except KeyError as e:
        raise Exception(
            f"couldn't guess a reader from extension of file {path_or_buf}")

    if reader == read_sqlite:
        return reader(path_or_buf, columns=columns, nrows=nrows, **kws)
    elif reader == pd.read_csv:
        return reader(path_or_buf, usecols=columns, nrows=nrows, **kws)
    else:
        if columns is None:
            columns = slice(None, None)
        return reader(path_or_buf, **kws)[columns].iloc[:nrows]


class MungeTarReader:
    tarnames = 'data.tar', 'data.tar.gz', 'data.tar.bz2', 'data.tar.lz4'

    def __init__(self, path, tarname='data.tar'):
        import tarfile
        self.tarfile = tarfile.open(os.path.join(path, tarname), 'r')

    def __call__(self, key, *args, **kws):
        key = key.replace('\\\\', '\\')

        for k in key,\
                key.replace('\\', '/').replace('//', '/'):
            try:

                ext = os.path.splitext(key)[1][1:]
                return read(self.tarfile.extractfile(k), format=ext,
                            *args, **kws)
            except KeyError as e:
                ex = e
                continue
            else:
                break
        else:
            raise ex


class MungeDirectoryReader:
    def __init__(self, path):
        self.path = path

    def __call__(self, key, *args, **kws):
        return read(os.path.join(self.path, key), *args, **kws)


class MungeReader:
    """ Guess the type of munging performed on the relational data, and return
        a reader suited to loading that file.

    """
    """ TODO: Make this smarter, perhaps by trying to read an entry from
        the master database
    """
    def __new__(cls, path):
        dirname = os.path.dirname(path)

        for n in MungeTarReader.tarnames:
            if os.path.exists(os.path.join(dirname, n)):
                return MungeTarReader(dirname, tarname=n)
        return MungeDirectoryReader(dirname)


def read_relational(path, expand_col, master_cols=None, target_cols=None,
                    master_nrows=None, master_format='auto', prepend_column_name=True):
    """ Flatten a relational database table by loading the table located each row of
        `master[expand_col]`. The value of each column in this row
        is copied to the loaded table. The columns in the resulting table generated
        on each row are downselected
        according to `master_cols` and `target_cols`. Each of the resulting tables
        is concatenated and returned.

        The expanded dataframe may be very large, making downselecting a practical
        necessity in some scenarios.

        TODO: Support for a list of expand_col?

        :param pandas.DataFrame master: the master database, consisting of columns containing data and columns containing paths to data files
        :param str expand_col: the column in the master database containing paths to    data files that should be expanded
        :param master_cols: a column (or array-like iterable of multiple columns) listing the master columns to include in the expanded dataframe, or None (the default) pass all columns from `master`
        :param target_cols: a column (or array-like iterable of multiple columns) listing the master columns to include in the expanded dataframe, or None (the default) to pass all columns loaded from each master[expand_col]
        :param master_path: a string containing the full path to the master database (to help find the relational files)
        :param bool prepend_column_name: whether to prepend the name of the expanded column from the master database
        :returns: the expanded dataframe

    """

    import pandas as pd

    # if not isinstance(master, (pd.DataFrame,pd.Series)):
    #     raise ValueError('expected master to be a DataFrame instance, but it is {} instead'\
    #                      .format(repr(type(master))))
    if not isinstance(expand_col, str):
        raise ValueError(f'expand_col must a str, not {type(expand_col)}')

    if master_cols is not None:
        master_cols = list(master_cols) + [expand_col]
    master = read(path, columns=master_cols,
                  nrows=master_nrows, format=master_format)
    reader = MungeReader(path)

    def generate():
        for i, row in master.iterrows():
            if row[expand_col] is None or len(row[expand_col]) == 0:
                continue

            sub = reader(row[expand_col], columns=target_cols)

            if prepend_column_name:
                prepend = expand_col + '_'
            else:
                prepend = ''

            # Rename columns
            sub.columns = [prepend + c for c in sub.columns]
            sub[prepend + 'id'] = sub.index

            # # Downselect master columns
            # if master_cols is not None:
            #     row = row[master_cols]

            # Add in columns from the master
            for c, v in row.iteritems():
                sub[c] = v

            yield sub

    return pd.concat(generate(), ignore_index=True, sort=True)
