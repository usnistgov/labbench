import copy
import inspect
import io
import json
import os
import pickle
import re
import shutil
import tarfile
import warnings
from collections.abc import Callable, Iterable
from contextlib import contextmanager, suppress
from pathlib import Path
from typing import Any, Union

from typing_extensions import TypeAlias

from . import _device, _host, _rack, util
from . import _device as core
from . import paramattr as attr
from ._device import Device
from ._rack import Owner
from .paramattr import observe

try:
    np = util.lazy_import('numpy')
    pd = util.lazy_import('pandas')
    sqlalchemy = util.lazy_import('sqlalchemy')
    feather = util.lazy_import('pyarrow.feather')
except RuntimeWarning:
    # not executed: help static code analysis recognize lazy_imports
    import numpy as np
    import pandas as pd
    import sqlalchemy
    from pyarrow import feather

# define this alias type to avoid a forced import
DataFrameType: TypeAlias = 'pd.DataFrame'

EMPTY = inspect._empty

INSPECT_SKIP_FILES = _device.__file__, attr.__file__, _rack.__file__, __file__


class MungerBase(core.Device):
    """Organize file output with a key in the root database.

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

    resource: Path = attr.value.Path(
        allow_none=True, kw_only=False, help='base directory for all data'
    )
    text_relational_min: int = attr.value.int(
        default=1024,
        min=0,
        help='minimum size threshold that triggers storing text in a relational file',
    )
    force_relational: list = attr.value.list(
        default=[], help='list of column names to always save as relational data'
    )
    relational_name_fmt: str = attr.value.str(
        default='{id}',
        help='directory name format for data in each row keyed on column',
    )
    nonscalar_file_type: str = attr.value.str(
        default='csv', help='file format for non-scalar numerical data'
    )
    metadata_dirname = 'metadata'

    def __call__(self, index, row):
        """
        Break special cases of row items that need to be stored in
        relational files. The row valueis replaced in-place with the relative
        path to the data saved on disk.

        Arguments:
            row: dictionary of {'entry_name': "entry_value"} pairs
        Returns:
            the row dictionary, replacing special entries with the relative path to the saved data file
        """

        def is_path(v):
            if not isinstance(v, str):
                return False
            try:
                return os.path.exists(v)
            except ValueError:
                return False

        for name, v in row.items():
            if is_path(v):
                # Path to a datafile to move into the dataset
                row[name] = self._from_external_file(name, v, index, row)

            elif isinstance(v, (str, bytes)):
                # A long string that should be written to a text file
                if (
                    len(v) > self.text_relational_min
                    or name in self.force_relational
                    or isinstance(v, bytes)
                ):
                    row[name] = self._from_text(name, v, index, row)

            elif isinstance(v, (np.ndarray, pd.Series, pd.DataFrame)):
                # vector, table, matrix, etc.
                row[name] = self._from_ndarraylike(name, v, index, row)

            elif hasattr(v, '__len__') or hasattr(v, '__iter__'):
                # tuple, list, or other iterable
                row[name] = self._from_sequence(name, v, index, row)

        return row

    def __repr__(self):
        return f"{type(self).__name__}('{self.resource!s}')"

    def get_metadata(
        self,
        name,
        name_func: Callable[[attr.HasParamAttrs, str, dict], str],
        **metadata,
    ):
        def process_value(value, key_name):
            if isinstance(value, (str, bytes)):
                if len(value) > self.text_relational_min:
                    self._from_text(key_name, value)
                else:
                    return value
            elif isinstance(value, (pd.DataFrame, np.ndarray)):
                self._from_ndarraylike(key_name, value)
            else:
                return value

        global_values = {}
        for owner, owner_name in name.items():
            if not isinstance(owner, Device):
                # other util.Ownable instances e.g. RelationalTableLogger
                continue

            for attr_name, attr_def in attr.get_class_attrs(owner).items():
                if isinstance(attr_def, attr.value.Value) or attr_def.cache:
                    summary_key = name_func(owner, attr_name)
                    global_values[summary_key] = getattr(owner, attr_name)
        global_values = {k: process_value(v, k) for k, v in global_values.items()}

        # metadata = dict(summary=pd.DataFrame([summary], index=["Value"]).T)
        metadata['global_values'] = global_values

        return metadata

    def save_metadata(self, metadata):
        raise NotImplementedError

    def _from_ndarraylike(self, name, value, index=0, row=None):
        """Write nonscalar (potentially array-like, or a python object) data
        to a file, and return a path to the file

        Arguments:
            name: name of the entry to write, used as the filename
            value: the object containing array-like data
            row: row dictionary, or None (the default) to write to the metadata folder
        Returns:
            the path to the file, relative to the directory that contains the root database
        """

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
                raise Exception(f"extension {ext} doesn't match a known format")

        if hasattr(value, '__len__') and len(value) == 0:
            return ''

        if row is None:
            ext = 'csv'
        else:
            ext = self.nonscalar_file_type

        try:
            value = pd.DataFrame(value)
            if value.shape[0] == 0:
                value = pd.DataFrame([value])
        except BaseException:
            # We couldn't make a DataFrame
            self._logger.error(
                f'Failed to form DataFrame from {name!r}; pickling object instead'
            )
            ext = 'pickle'
        finally:
            if row is None:
                stream = self._open_metadata(name + '.' + ext, 'wb')
            else:
                stream = self._open_relational(name + '.' + ext, index, row, mode='wb')

            # Workaround for bytes/str encoding quirk underlying pandas 0.23.1
            try:
                write(stream, ext, value)
                self._get_key(stream)
            except TypeError:
                with io.TextIOWrapper(stream, newline='\n') as buf:
                    write(buf, ext, value)
            finally:
                stream.close()
        return self._get_key(stream)

    def _from_external_file(self, name, old_path, index=0, row=None, ntries=10):
        basename = os.path.basename(old_path)
        with self._open_relational(basename, index, row, mode='wb') as buf:
            new_path = buf.name

        self._relational_from_file(old_path, new_path)

        return self._get_key(new_path)

    def _from_text(self, name, value, index=0, row=None, ext='.txt'):
        """Write a string data to a file

        Arguments:
            name: name of the parameter (helps to determine file path)
            value: the string to write to file
            row: the row to infer timestamp, or None to write to metadata
            ext: file extension
        Returns:
            the path to the file, relative to the directory that contains the root database
        """
        with self._open_relational(name + ext, index, row, 'w') as f:
            f.write(value)
        return self._get_key(f)

    def _from_sequence(self, name, value, index=0, row=None, ext='.json'):
        """Write a string data to a file

        Arguments:
            name: name of the parameter (helps to determine file path)
            value: the string to write to file
            row: the row to infer timestamp, or None to write to metadata
            ext: file extension
        Returns:
            the path to the file, relative to the directory that contains the root database
        """
        with self._open_relational(name + ext, index, row, mode='w') as fd:
            json.dump(value, fd, indent=True)  # f.write(bytes(value, encoding='utf-8'))

        return self._get_key(fd)

    # The following methods need to be implemented in subclasses.
    def _get_key(self, buf):
        """Key to use for the relative data in the root database?

        Arguments:
            stream: stream for writing to the relational data file
        Returns:
            the key
        """
        raise NotImplementedError

    def _open_relational(self, name, index, row, mode):
        """Open a stream / IO buffer for writing relational data, given
        the root database column, index, and the row dictionary.

        Arguments:
            name: the column name of the relational data in the root db
            index: the index name of of the data in the root db
            row: the dictionary containing the row of data at `index`

        Returns:

            an open buffer object for writing data
        """
        raise NotImplementedError

    def _open_metadata(self, name, mode, in_root=False):
        """Open a stream / IO buffer for writing metadata, given
        the name of the metadata.

        Returns:

            an open buffer object for writing metadata to the file
        """

        raise NotImplementedError

    def _relational_from_file(self, old_path, dest):
        raise NotImplementedError

    def format_metadata_value(self, key_name, value):
        if isinstance(value, (str, bytes)):
            if len(value) > self.text_relational_min:
                self._from_text(key_name, value)
            else:
                return value
        elif isinstance(value, (pd.DataFrame, np.ndarray)):
            self._from_ndarraylike(key_name, value)
        else:
            return value

    def open(self):
        # touch these modules to ensure they have imported
        pd.DataFrame
        np.array


class MungeToDirectory(MungerBase):
    """Implement data munging into subdirectories."""

    def _open_relational(self, name, index, row, mode):
        relpath = self._make_path_heirarchy(index, row)
        if not os.path.exists(relpath):
            os.makedirs(relpath)

        return open(os.path.join(relpath, name), mode)

    def _open_metadata(self, name, mode, in_root=False):
        if in_root:
            dirpath = self.resource
        else:
            dirpath = self.resource / self.metadata_dirname
            dirpath.mkdir(exist_ok=True)

        return open(Path(dirpath) / name, mode)

    def _get_key(self, stream):
        """Key to use for the relative data in the root database?

        Arguments:
            stream: stream for writing to the relational data file
        Returns:
            the key
        """
        return os.path.relpath(stream.name, self.resource)

    def _relational_from_file(self, old_path, dest):
        # Retry moves for several seconds in case the file is in the process
        # of being closed
        @util.until_timeout(PermissionError, 5, delay=0.5)
        def move():
            os.rename(old_path, dest)

        try:
            move()
            self._logger.debug(f'moved {old_path!r} to {dest!r}')
        except PermissionError:
            self._logger.warning(
                'relational file was still open in another program; fallback to copy instead of rename'
            )
            shutil.copyfile(old_path, dest)

    def _make_path_heirarchy(self, index: int, row: dict):
        # TODO: add back in a timestamp
        relpath = self.relational_name_fmt.format(id=index, **row)

        # TODO: More robust enforcement for a valid path strings
        relpath = relpath.replace(':', '')
        relpath = os.path.join(self.resource, relpath)
        return relpath

    def save_metadata(self, metadata: dict[str, Any]):
        def recursive_dict_fix(d):
            d = dict(d)
            for name, obj in dict(d).items():
                if isinstance(obj, Path):
                    d[name] = str(obj)
                elif isinstance(obj, bytes):
                    d[name] = obj.decode()
                elif isinstance(obj, dict):
                    d[name] = recursive_dict_fix(obj)
            return d

        sanitized = recursive_dict_fix(metadata)

        # for k, v in metadata.items():
        #     stream = self._open_metadata(k + ".json", "w")
        #     if hasattr(stream, "overwrite"):
        #         stream.overwrite = True

        #     if isinstance(v, pd.DataFrame):
        #         v = v.to_dict()#["Value"]
        #     if isinstance(v, dict):
        #         v = recursive_dict_fix(v)

        with self._open_metadata('metadata.json', 'w', in_root=True) as stream:
            json.dump(sanitized, stream, indent=True)


class TarFileIO(io.BytesIO):
    """For appending data into new files in a tarfile"""

    def __init__(self, open_tarfile, relname, mode='w', overwrite=False):
        self.tarfile = open_tarfile
        self.overwrite = False
        self.name = relname
        self.mode = mode
        super(TarFileIO, self).__init__()

    def __del__(self):
        try:
            super(TarFileIO, self).close()
        except ValueError:
            pass

        super(TarFileIO, self).__del__()

    def write(self, data, encoding='ascii'):
        if isinstance(data, str):
            data = bytes(data, encoding=encoding)
        super(TarFileIO, self).write(data)

    def close(self):
        # First: dump the data into the tar file
        try:
            if not self.overwrite and self.name in self.tarfile.getnames():
                raise OSError(f'{self.name} already exists in {self.tarfile.name}')

            tarinfo = tarfile.TarInfo(self.name)
            tarinfo.size = self.tell()

            self.seek(0)

            self.tarfile.addfile(tarinfo, self)

        # Then make sure to close everything
        finally:
            super(TarFileIO, self).close()


class MungeToTar(MungerBase):
    """Implement data munging into a tar file. This is slower than
    MungeToDirectory but is tidier on the filesystem.
    """

    tarname = 'data.tar'

    def _open_relational(self, name, index, row, mode):
        directory = self.relational_name_fmt.format(id=index, **row)
        relpath = f'{directory}/{name}'
        return TarFileIO(self.tarfile, relpath, mode=mode)

    def _open_metadata(self, name, mode, in_root=False):
        if in_root:
            return MungeToDirectory._open_metadata(self, name, mode, True)
        if in_root:
            dirpath = name
        else:
            dirpath = os.path.join(self.metadata_dirname, name)
        stream = TarFileIO(self.tarfile, dirpath, mode=mode)
        if hasattr(stream, 'overwrite'):
            stream.overwrite = True
        return stream

    def open(self):
        if not os.path.exists(self.resource):
            with suppress(FileExistsError):
                os.makedirs(self.resource)
        self.tarfile = tarfile.open(os.path.join(self.resource, self.tarname), 'a')

    def close(self):
        self.tarfile.close()

    def _get_key(self, buf):
        """Where is the file relative to the root database?

        Arguments:
            path: path of the file
        Returns:
            path to the file relative to the root database
        """
        return buf.name

    def _relational_from_file(self, old_path, dest):
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
            self._logger.debug(f'moved {old_path} to into tar file as {dest}')
        except PermissionError:
            self._logger.warning(f'could not remove old file or directory {old_path}')

    def save_metadata(self, metadata: dict[str, Any]):
        def recursive_dict_fix(d):
            d = dict(d)
            for name, obj in dict(d).items():
                if isinstance(obj, Path):
                    d[name] = str(obj)
                elif isinstance(obj, bytes):
                    d[name] = obj.decode()
                elif isinstance(obj, dict):
                    d[name] = recursive_dict_fix(obj)
            return d

        sanitized = recursive_dict_fix(metadata)

        # for k, v in metadata.items():
        #     stream = self._open_metadata(k + ".json", "w")
        #     if hasattr(stream, "overwrite"):
        #         stream.overwrite = True

        #     if isinstance(v, pd.DataFrame):
        #         v = v.to_dict()#["Value"]
        #     if isinstance(v, dict):
        #         v = recursive_dict_fix(v)

        with self._open_metadata('metadata.json', 'w', in_root=True) as stream:
            json.dump(sanitized, stream, indent=True)


class Aggregator(util.Ownable):
    """Manages aggregation of parameters of Device attributes defined with paramattr, and data returned by calls to methods in Rack instances"""

    # note: this is not a dataclass, these annotations are only for type-hinting
    name_map: dict[attr.HasParamAttrs, str]
    attr_rules: dict[str, dict[attr.HasParamAttrs, str]]

    # observed value changes from paramattr objects
    incoming_attr_always: dict[str, attr.HasParamAttrs]
    incoming_attr_auto: dict[str, attr.HasParamAttrs]

    def __init__(self):
        # registry of names to use for HasParamAttr subclasses like Device
        self.name_map = {}
        self.attr_rules = dict(always={}, never={})

        # pending data
        self.incoming_attr_auto = {}
        self.incoming_attr_always = {}
        self.incoming_rack_output = {}
        self.incoming_rack_input = {}

        self._rack_toplevel_caller = None
        self._rack_input_index = 0

        # self._iter_index_names = {}

        # cached data
        self.metadata = {
            'device_objects': {},
            'global_values': {},
            'field_name_sources': {},
        }

        super().__init__()

    def __repr__(self):
        return f'{self.__class__.__qualname__}()'

    def enable(self):
        # catch return data as well
        _rack.notify.observe_returns(self._receive_rack_output)
        _rack.notify.observe_calls(self._receive_rack_input)
        # _rack.notify.observe_call_iteration(self._receive_rack_iteration)

    def disable(self):
        _rack.notify.unobserve_returns(self._receive_rack_output)
        _rack.notify.unobserve_calls(self._receive_rack_input)
        # _rack.notify.unobserve_call_iteration(self._receive_rack_input)

    def always_get_this_attr(self, device, attr_name):
        if not isinstance(device, core.Device):
            return False

        attr_def = attr.get_class_attrs(device)[attr_name]

        return isinstance(attr_def, attr.value.Value) or attr_def.cache

    def get(self) -> list([dict, dict]):
        """return an aggregated dictionary output data (from Device paramattr objects and Rack method returns)
        and an aggregated dictionary of input data (keyword arguments passed to the toplevel Rack method).
        A get is
        also performed on each Device trait that is configured as "always" with `self.observe`, and any paramattr objects
        labeled "never" are removed.

        Returns:
            dictionary keyed on :func:`key` (defaults '{device name}_{attr name}_{repr of method kwargs}')
        """

        for device in self.name_map.keys():
            # Perform gets for each property trait called out in self.trait_rules['always']
            if device in self.attr_rules['always'].keys():
                for attr_name in self.attr_rules['always'][device]:
                    field_name = self.name_attr_field(device, attr_name)
                    value = getattr(device, attr_name)

                    if self.always_get_this_attr(device, attr_name):
                        self.incoming_attr_always[field_name] = value
                    else:
                        self.incoming_attr_auto[field_name] = value

            # Remove keys corresponding with self.trait_rules['never']
            if device in self.attr_rules['never'].keys():
                for attr_name in self.attr_rules['never'][device]:
                    field_name = self.name_attr_field(device, attr_name)
                    if self.always_get_this_attr(device, attr_name):
                        self.incoming_attr_always.pop(field_name, None)
                    else:
                        self.incoming_attr_auto.pop(field_name, None)

        aggregated_output = {}

        # start by aggregating the trait data, and checking for conflicts with keys in the Rack data
        aggregated_output.update(self.incoming_attr_always)
        aggregated_output.update(self.incoming_attr_auto)

        # check namespace conflicts and pull in rack outputs
        key_conflicts = set(aggregated_output).intersection(self.incoming_rack_output)
        if len(key_conflicts) > 0:
            self.critical(
                f'key name conflict in aggregated data - Rack data is overwriting trait data for {key_conflicts}'
            )
        aggregated_output.update(self.incoming_rack_output)

        # and the rack inputs
        aggregated_input = {}
        aggregated_input.update(self.incoming_rack_input)

        if 'index' in aggregated_input:
            aggregated_output['index'] = aggregated_input['index']

        # clear Rack data, as well as property trait data if we don't assume it is consistent.
        # value traits are locally cached, so it is safe to keep them in the next step
        self.incoming_rack_output = {}
        self.incoming_attr_auto = {}
        # self._pending_rack_input = {}

        return aggregated_output, aggregated_input

    def get_metadata(self, process_func: callable):
        metadata = dict(self.metadata)
        global_values = {}
        for owner, owner_name in self.name_map.items():
            if not isinstance(owner, Device):
                # other util.Ownable instances e.g. RelationalTableLogger
                continue

            for attr_name, attr_def in attr.get_class_attrs(owner).items():
                if isinstance(attr_def, attr.value.Value) or attr_def.cache:
                    summary_key = self.name_attr_field(owner, attr_name)
                    global_values[summary_key] = getattr(owner, attr_name)
        global_values = {k: process_func(v, k) for k, v in global_values.items()}

        metadata['global_values'] = global_values

        return metadata

    def sanitize_column_name(self, string: str) -> str:
        return re.sub(r'\W+|^(?=\d)+', '_', string)

    def name_attr_field(
        self, device: attr.HasParamAttrs, attr_name: str, kwargs: dict[str, Any] = {}
    ):
        """Generate a name for a trait based on the names of
        a device and one of its states or paramattr.
        """
        kwarg_repr = ', '.join([f'{k}={v!r}' for k, v in kwargs.items()])
        attr_def = getattr(type(device), attr_name)

        bare_name = f'{self.name_map[device]}_{attr_name}_{kwarg_repr}'
        sanitized_name = self.sanitize_column_name(bare_name).rstrip('_')

        if attr_def._type.__module__ != 'builtins':
            typename = f'{attr_def._type.__module__}.{attr_def._type.__qualname__}'
        else:
            typename = attr_def._type.__qualname__

        attr_metadata = {
            'object': f'{self.name_map[device]}.{attr_name}',
            'paramattr': attr_def.__repr__(),
            'type': typename,
            'help': attr_def.help,
            'label': attr_def.label,
        }

        if isinstance(attr_def, attr.method.Method):
            attr_metadata['kwargs'] = kwargs

        self.metadata['field_name_sources'][sanitized_name] = attr_metadata

        return sanitized_name

    def set_device_labels(self, **mapping: dict[Device, str]):
        """Manually choose device name for a device instance.

        Arguments:
            mapping: name mapping, formatted as {device_object: 'device name'}
        Returns:
            None
        """
        for label, device in list(mapping.items()):
            if isinstance(device, Aggregator):
                pass
            elif not isinstance(device, Device):
                raise ValueError(f'{device} is not an instance of Device')

        self.name_map.update([(v, k) for k, v in mapping.items()])

    def _receive_rack_output(self, msg: dict):
        """called by an owning Rack notifying that managed procedural steps have returned data"""
        # trait data or previous returned data may cause problems here. perhaps this should be an exception?

        row_data = msg['new']

        key_conflicts = set(row_data).intersection(self.incoming_rack_output)
        if len(key_conflicts) > 0:
            self._logger.warning(
                f'Rack call overwrites prior data with existing keys {key_conflicts}'
            )
        self.incoming_rack_output.update(row_data)

    def _receive_rack_input(self, msg: dict):
        """called by an owning Rack notifying that managed procedural steps have returned data"""
        # trait data or previous returned data may cause problems here. perhaps this should be an exception?

        row_data = dict(index=self._rack_input_index)

        if self._rack_toplevel_caller is None:
            # take the first call as the top-level caller
            self._rack_toplevel_caller = msg['owner']

        elif self._rack_toplevel_caller != msg['owner']:
            # only track calls to the top-level caller
            return

        else:
            # iter_info = msg["new"]
            self._rack_input_index += 1

        # if len(self._iter_index_names) > 0:
        #     self._iter_index_names.setdefault(
        #         msg["owner"], "index_" + msg["owner"]._owned_name
        #     )
        # else:
        #     self._iter_index_names.setdefault(msg["owner"], "index")

        # row_data[self._iter_index_names[msg["owner"]]] = iter_info["index"]
        # if iter_info['step_name']:
        #     row_data[msg['owner']._owned_name + '_step_name'] = iter_info['step_name']

        # TODO: should there be some kind of conflict check for this?
        # key_conflicts = set(row_data).intersection(self._pending_traits_persistent)
        # if len(key_conflicts) > 0:
        #     self._logger.warning(
        #         f"Rack call overwrites prior data with existing keys {key_conflicts}"
        #     )

        self.incoming_rack_input = dict(row_data, **msg['new'])

    def _receive_paramattr_update(self, msg: dict):
        """called by trait owners on changes observed

        Arguments:
            msg: callback info dictionary generated by traitlets
        Returns:
            None
        """

        if msg['name'].startswith('_'):
            # skip private traits
            return

        if not msg['paramattr'].log:
            return

        name = self.name_map[msg['owner']]
        attr_name = msg['name']
        kwargs = msg.get('kwargs', {})
        data_name = self.name_attr_field(msg['owner'], attr_name, kwargs)

        if msg['cache']:
            self.metadata[data_name] = msg['new']
        elif self.always_get_this_attr(msg['owner'], msg['name']):
            # TODO: need to figure out the semantics around "always" attrs that are methods
            self.incoming_attr_always[data_name] = msg['new']
        elif not name.startswith('_'):
            self.incoming_attr_auto[data_name] = msg['new']

    def update_name_map(
        self,
        ownables: dict[Device, str],
        owner_prefix: Union[str, None] = None,
        fallback_names={},
    ):
        """map each Device to a name in devices.values() by introspection."""
        if owner_prefix is None:
            prefix = ''
        else:
            prefix = owner_prefix + '.'

        for obj, name in ownables.items():
            if not isinstance(obj, util.Ownable):
                raise ValueError(
                    f'{obj} is not a Device or other ownable labbench type'
                )

            if name is not None:
                if obj not in self.name_map:
                    self.name_map[obj] = new_name = prefix + name
                else:
                    new_name = name

            elif obj in self.name_map:
                # naming for device. needs this
                new_name = prefix + self.name_map[obj]

            elif getattr(obj, '_owned_name', None) is not None:
                self.name_map[obj] = new_name = obj._owned_name

            elif hasattr(obj, '__name__'):
                # Ownable instances that have owners have this attribute set
                self.name_map[obj] = new_name = prefix + obj.__name__

            else:
                try:
                    self.name_map[obj] = new_name = prefix + self.inspect_object_name(
                        obj
                    )
                    self._logger.info(f"{obj} named '{new_name}' by introspection")
                except RuntimeError:
                    if obj in fallback_names:
                        self.name_map[obj] = new_name = prefix + fallback_names[obj]
                        self._logger.info(
                            f"{obj} named '{new_name}' based on fallback after introspection failed"
                        )
                    else:
                        raise

            if isinstance(obj, Owner):
                children = dict(zip(obj._ownables.values(), obj._ownables.keys()))
                self.update_name_map(children, owner_prefix=new_name)

            self.metadata['device_objects'][new_name] = repr(obj)

        if len(list(self.name_map.values())) != len(set(self.name_map.values())):
            duplicates = {}
            for k, v in self.name_map.items():
                duplicates.setdefault(v, []).append(k)

            duplicates = {k: v for k, v in duplicates.items() if len(v) > 1}

            raise RuntimeError(
                f'could not automatically resolve duplicate device name(s) {duplicates}'
            )

    def observe(
        self,
        devices,
        changes: bool = True,
        always: Union[str, list[str]] = [],
        never: Union[str, list[str]] = ['isopen'],
    ):
        """Configure the data to aggregate from value, property, or datareturn traits in the given devices.

        Device may be a single device instance, or an
        several devices in an iterable (such as a list
        or tuple) to apply to each one.

        Subsequent calls to :func:`observe_states` replace
        the existing list of observed property traits for each
        device.

        Arguments:
            devices: Device instance, iterable of Devices, or {device:name} mapping
            changes: Whether to automatically log each time a property trait is set for the supplied device(s)
            always: name (or iterable of multiple names) of property traits to actively update on each call to get()
            never: name (or iterable of multiple names) of property traits to exclude from aggregated result (overrides :param:`always`)
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
            raise ValueError("argument 'always' must be a str or iterable of str")

        if isinstance(never, str):
            never = (never,)
        elif hasattr(never, '__iter__'):
            never = tuple(never)
        else:
            raise ValueError("argument 'never' must be a str or iterable of str")

        self.update_name_map(devices)

        # Register handlers
        for device in devices.keys():
            if changes:
                observe(device, self._receive_paramattr_update)
            else:
                attr.unobserve(device, self._receive_paramattr_update)
            if always:
                self.attr_rules['always'][device] = always
            if never:
                self.attr_rules['never'][device] = never

    def inspect_object_name(self, target, max_levels=20):
        """Introspect into the caller to name an object .

        Arguments:
            target: device instance
            min_levels: minimum number of layers of calls to traverse
            max_levels: maximum number of layers to traverse
        Returns:
            name of the Device
        """

        def find_value(haystack, needle, reject=['self']):
            for k, v in haystack.items():
                if v is needle:
                    if k in reject:
                        raise KeyError
                    else:
                        return k
            else:
                raise KeyError

        f = frame = inspect.currentframe()

        ret = None

        try:
            while f.f_code.co_filename in INSPECT_SKIP_FILES:
                f = f.f_back

            tries_elapsed = 0
            while tries_elapsed < max_levels:
                # look in the namespace; if nothing
                try:
                    ret = find_value(f.f_locals, target)
                except KeyError:
                    f = f.f_back
                    if f is None:
                        tries_elapsed = max_levels
                    else:
                        tries_elapsed += 1
                    continue
                else:
                    break
            else:
                raise RuntimeError(
                    f'failed to automatically label {target!r} by inspection'
                )
        finally:
            del f, frame

        return ret


class ParamAttrLogger(
    Owner, util.Ownable, entry_order=(_host.Email, MungerBase, _host.Host)
):
    """Base class for loggers that queue dictionaries of data before writing
    to disk. This extends :class:`Aggregator` to support

    #. queuing aggregate property trait of devices by lists of dictionaries;
    #. custom metadata in each queued aggregate property trait entry; and
    #. custom response to non-scalar data (such as relational databasing).

    Arguments:
        path: Root path to use for the root database
        overwrite: Whether to overwrite the root database if it exists (otherwise, append)

        text_relational_min: Text with at least this many characters is stored as a relational text file instead of directly in the database
        force_relational: A list of columns that should always be stored as relational data instead of directly in the database
        nonscalar_file_type: The data type to use in non-scalar (tabular, vector, etc.) relational data

        tar: Whether to store the relational data within directories in a tar file, instead of subdirectories
        git_commit_in: perform a git commit on open() if the current
        directory is inside a git repo with this branch name
    """

    INDEX_LABEL = 'id'

    def __init__(
        self,
        path: Path,
        *,
        append: bool = False,
        text_relational_min: int = 1024,
        force_relational: list[str] = ['host_log'],
        nonscalar_file_type: str = 'csv',
        tar: bool = False,
        git_commit_in: str = None,
    ):
        self.path = Path(path)
        self.last_row = 0
        self.pending_output = []
        self.pending_input = []
        self._append = append

        self.aggregator = Aggregator()

        # log host introspection
        # TODO: smarter

        self.host = _host.Host(git_commit_in=git_commit_in)

        # select the backend that dumps relational data
        munge_cls = MungeToTar if tar else MungeToDirectory
        self.munge = munge_cls(
            path,
            text_relational_min=text_relational_min,
            force_relational=force_relational,
            nonscalar_file_type=nonscalar_file_type,
            # **metadata
        )

        self.set_row_preprocessor(None)

        # doing this at the end ensures self._logger is seeded with appropriate log messages
        super().__init__()

    def __copy__(self):
        return copy.deepcopy(self)

    def __owner_init__(self, owner: Owner):
        """observe children of each Rack or other Owner"""
        super().__owner_init__(owner)
        devices, _ = _rack.recursive_devices(owner)
        self.observe_paramattr({v: k for k, v in devices.items()})

    def __repr__(self):
        if hasattr(self, 'path'):
            path = repr(str(self.path))
        else:
            path = '<unset path>'
        return f'{self.__class__.__qualname__}({path})'

    def observe_paramattr(
        self,
        devices: Union[Device, Iterable[Device]],
        changes: bool = True,
        always: Union[str, Iterable[str]] = [],
        never: Union[str, Iterable[str]] = ['isopen'],
    ):
        """Configure aggregation of activity in parameter attributes defined with `labbench.paramattr.value`,
        `labbench.paramattr.property`, or labbench.paramattr.method`.

        Device may be a single device instance or an iterable several devices in an iterable (such as a list
        or tuple) to apply to each one.

        Subsequent calls to :func:`observe_states` replace
        the existing list of observed property traits for each
        device.

        Arguments:
            devices: One or more Device instances to observe
            changes: Whether to automatically log each time a property trait is set for the supplied device(s)
            always: name (or iterable of multiple names) of property traits to actively update on each call to get()
            never: name (or iterable of multiple names) of property traits to exclude from aggregated result (overrides :param:`always`)
        """

        self.aggregator.observe(
            devices=devices, changes=changes, always=always, never=never
        )

    def set_row_preprocessor(self, func):
        """Define a function that is called to modify each pending data row
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

    def new_row(self, *args, **kwargs):
        """Add a new row of data to the list of rows that await writes
        to disk, `self.pending_output`. This cache of pending data row is in
        the dictionary `self.pending_output`.

        The data row is represented as a dict in the form {'column_name': value}.
        This dict is formed here with
        * the most recent value, property, and datareturn traits ({trait_name: latest_value} as configured by `self.observe`);
        * optional positional dict args[0] (each {key: value});
        * optional keyword arguments in `kwargs` (each {key: value})

        Keyword arguments are passed in as::

            db.new_row(dict(name0=value0), name1=value1, name2=value2, nameN=valueN)

        Simple "scalar" database types like numbers, booleans, and strings
        are added directly to the table. Non-scalar or multidimensional values are stored
        in a separate file (as defined in :func:`set_path_format`), and the path
        to this file is stored in the table.

        In order to write `self.pending_output` to disk, use :func:`self.write`.

        :param bool copy=True: When `True` (the default), use a deep copy of `data` to avoid
        problems with overwriting references to data if `data` is reused during test. This takes some extra time; set to `False` to skip this copy operation.

        Returns:
            the dictionary representation of the row added to `self.pending_output`.
        """
        do_copy = kwargs.pop('copy', None)

        # Start with input arguments
        if len(args) == 1:
            #            if not isinstance(args[0], dict):
            #                raise TypeError('argument to append must be a dictionary')
            row = copy.deepcopy(dict(args[0])) if do_copy else dict(args[0])
        elif len(args) == 0:
            row = {}

        # Pull in observed states. aggregated_input comes from Rack method keyword args
        aggregated_output, aggregated_input = self.aggregator.get()
        if do_copy:
            aggregated_output = copy.deepcopy(aggregated_output)
        row.update(aggregated_output)

        # Pull in keyword arguments
        if do_copy:
            kwargs = copy.deepcopy(dict(kwargs))
        else:
            kwargs = dict(kwargs)
        row.update(kwargs)

        self._logger.debug(f'new data row has {len(row)} columns')

        self.pending_output.append(row)
        self.pending_input.append(aggregated_input)

    def write(self):
        """Commit any pending rows to the root database, converting
        non-scalar data to data files, and replacing their dictionary value
        with the relative path to the data file.

        Returns:

            None
        """
        if len(self.pending_output) != len(self.pending_input):
            util.logger.warning('the input and output have mismatched length')

        count = len(self.pending_output)

        if count > 0:
            proc = self._row_preprocessor

            self.pending_output = [
                self.munge(self.output_index + i, proc(row))
                for i, row in enumerate(self.pending_output)
            ]

            self.pending_input = [
                self.munge(self.output_index + i, proc(row))
                for i, row in enumerate(self.pending_input)
            ]

            self._write_root()
            self.output_index += len(self.pending_output) - 1
            self.clear()

    @contextmanager
    @util.hide_in_traceback
    def context(self, *args, **kws):
        """calls `self.new_row(*args, **kws); self.write()` on context exit.

        This is meant as a convenience for defining execution behavior in
        table inputs for Racks.
        """

        try:
            yield self
        finally:
            self.new_row(*args, **kws)
            self.write()

    def _write_root(self):
        """Write pending data. This must be implemented by inheriting classes.

        Returns:
            None
        """
        raise NotImplementedError

    def clear(self):
        """Remove any queued data that has been added by append."""
        self.pending_output = []
        self.pending_input = []

    def set_relational_file_format(self, format: str):
        """Set the format to use for relational data files.

        Arguments:
            format: one of 'csv', 'json', 'feather', or 'pickle'
        """
        warnings.warn(
            """set_nonscalar_file_type is deprecated; set when creating
                         the database object instead with the nonscalar_output flag"""
        )

        if format not in ('csv', 'json', 'feather', 'pickle', 'db'):
            raise Exception(f'relational file data format {format} not supported')
        self.munge.nonscalar_file_type = format

    def open(self):
        """Open the file or database connection.
        This is an abstract base method (to be overridden by inheriting classes)

        Returns:
            None
        """

        if self.path is None:
            raise TypeError('cannot open dB while path is None')

        # introspect self so to hook in self.host and self.munge
        if self not in self.aggregator.name_map:
            self.aggregator.update_name_map({self: None}, fallback_names={self: 'db'})

        self.observe_paramattr(self.munge, never=attr.get_class_attrs(self.munge))
        self.observe_paramattr(self.host, always=['time', 'log'])

        # configure strings in relational data files that depend on how 'self' is
        # named in introspection
        log_key = self.aggregator.name_attr_field(self.host, 'log')
        if log_key not in self.munge.force_relational:
            self.munge.force_relational = list(self.munge.force_relational) + [log_key]

        # Do some checks on the relative data directory before we consider overwriting
        # the root db.
        self.aggregator.enable()

        self.clear()

        self.output_index = 0
        self._logger.debug(f'{self} is open')
        return self

    def close(self):
        self.aggregator.disable()
        # try:
        self.write()

        if self.output_index > 0:
            if self.host.isopen:
                self.munge.save_metadata(
                    self.aggregator.get_metadata(self.munge.format_metadata_value)
                )
            else:
                self.munge._logger.warning('not saving metadata due to exception')


class CSVLogger(ParamAttrLogger):
    """Manage logging of experimental data and methods into CSV files.

    Explicit save methods are exposed for arbitrary custom data. Automatic logging is performed for

    #. Access to parameters of :class:`labbench.Device` objects that are defined with :mod:`labbench.paramattr.value`,
     :mod:`labbench.paramattr.property`, and :mod:`labbench.paramattr.method`.
    #. Function calls to methods of :class:`labbench.Rack`
    #. Metadata

    Arguments:
        path: Base path to use for the root database
        overwrite: Whether to overwrite the root database if it exists (otherwise, append)
        text_relational_min: Text with at least this many characters is stored as a relational text file instead of directly in the database
        force_relational: A list of columns that should always be stored as relational data instead of directly in the database
        nonscalar_file_type: The data type to use in non-scalar (tabular, vector, etc.) relational data
        tar: Whether to store the relational data within directories in a tar file, instead of subdirectories
    """

    ROOT_FILE_NAME = OUTPUT_FILE_NAME = 'outputs.csv'
    INPUT_FILE_NAME = 'inputs.csv'
    output_index = 0
    tables = {}

    nonscalar_file_type = 'csv'

    def open(self):
        """Instead of calling `open` directly, consider using
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

        # touch pandas to force lazy loading
        pd.__version__

        self.tables = {}

        # checking for existing files comes after this
        self.path.mkdir(parents=True, exist_ok=True)

        for file_name in self.OUTPUT_FILE_NAME, self.INPUT_FILE_NAME:
            file_path = self.path / file_name
            try:
                # test access by starting the root table
                file_path.touch(exist_ok=self._append)
            except FileExistsError:
                raise OSError(
                    f"root table already exists at '{file_path}', while append=False"
                )

            if self._append and file_path.stat().st_size > 0:
                # there's something here and we plan to append
                self.tables[file_name] = pd.read_csv(file_path, nrows=1)
                self.tables[file_name].index.name = self.INDEX_LABEL
                self.output_index = len(self.tables[file_name])
            else:
                self.tables[file_name] = None
                self.output_index = 0

    def _write_root(self):
        """Write queued rows of data to csv. This is called automatically on :func:`close`, or when
        exiting a `with` block.

        If the class was created with overwrite=True, then the first call to _write_root() will overwrite
        the preexisting file; subsequent calls append.
        """

        def append_csv(path: Path, df: pd.DataFrame):
            if len(df) == 0:
                return

            isfirst = self.tables.get(path.name, None) is None
            pending = pd.DataFrame(df)
            pending.index.name = self.INDEX_LABEL
            pending.index = pending.index + self.output_index

            if isfirst:
                self.tables[path.name] = pending
            else:
                self.tables[path.name] = pd.concat((self.tables[path.name], pending))
                self.tables[path.name] = self.tables[path.name].loc[pending.index[0] :]
            self.tables[path.name].sort_index(inplace=True)

            self.path.mkdir(exist_ok=True, parents=True)

            self.tables[path.name].to_csv(
                path, mode='a', header=isfirst, index=False, encoding='utf-8'
            )

        if len(self.pending_input) > 0:
            append_csv(self.path / self.INPUT_FILE_NAME, self.pending_input)
        if len(self.pending_output) > 0:
            append_csv(self.path / self.OUTPUT_FILE_NAME, self.pending_output)

            output_df = self.tables[(self.path / self.OUTPUT_FILE_NAME).name]
            self.output_index = output_df.index[-1]


class SQLiteLogger(ParamAttrLogger):
    """Store data and property traits to disk into an an sqlite database.

    This extends :class:`Aggregator` to support

    #. queuing aggregate property trait of devices by lists of dictionaries;
    #. custom metadata in each queued aggregate property trait entry; and
    #. custom response to non-scalar data (such as relational databasing).

    Arguments:
        path: Base path to use for the root database
        overwrite: Whether to overwrite the root database if it exists (otherwise, append)
        text_relational_min: Text with at least this many characters is stored as a relational text file instead of directly in the database
        force_relational: A list of columns that should always be stored as relational data instead of directly in the database
        nonscalar_file_type: The data type to use in non-scalar (tabular, vector, etc.) relational data
        tar: Whether to store the relational data within directories in a tar file, instead of subdirectories
    """

    INDEX_LABEL = 'id'  # Don't change this or sqlite breaks :(
    ROOT_FILE_NAME = 'root.db'
    OUTPUT_TABLE_NAME = 'output'
    _columns = None
    inprogress = {}
    committed = {}
    output_index = 0
    _engine = None

    def open(self):
        """Instead of calling `open` directly, consider using
        `with` statements to guarantee proper disconnection
        if there is an error. For example, the following
        sets up a connected instance::

            with SQLiteLogger('my.db') as db:
                ### do the data acquisition here
                pass

        would instantiate a `SQLiteLogger` instance, and also guarantee
        a final attempt to write unwritten data is written, and that
        the file is closed when exiting the `with` block, even if there
        is an exception.
        """

        if self.path.exists():
            root = str(self.path.absolute())
            if not self.path.is_dir():
                raise OSError(
                    f"the root data directory path '{root}' already exists, and is not a directory."
                )

            try:
                # test writes
                with open(self.path / '_', 'wb'):
                    pass
                (self.path / '_').unlink()
                ex = None
            except OSError as e:
                ex = e
            if ex:
                raise ex

        #        if not self.path.lower().endswith('.db'):
        #            self.path += '.db'
        os.makedirs(self.path, exist_ok=True)
        path = os.path.join(self.path, self.ROOT_FILE_NAME)

        # Create an engine via sqlalchemy
        self._engine = sqlalchemy.create_engine(f'sqlite:///{path}')

        if os.path.exists(path):
            if self._append:
                # read the last row to 1) list the columns and 2) get index
                query = f'select * from {self.OUTPUT_TABLE_NAME} order by {self.INDEX_LABEL} desc limit 1'

                df = pd.read_sql_query(query, self._engine, index_col=self.INDEX_LABEL)
                self._columns = df.columns
                self.output_index = df.index[-1] + 1
            else:
                raise OSError(
                    f"root table already exists at '{path}', but append=False"
                )
        else:
            self._columns = None
        self.inprogress = {}
        self.committed = {}

    def close(self):
        try:
            self.write()
            self._write_root()
        finally:
            if self._engine is not None:
                self._engine.dispose()

    def _write_root(self):
        """Write queued rows of data to the database. This also is called automatically on :func:`close`, or when
        exiting a `with` block.

        If the class was created with overwrite=True, then the first call to _write_root() will overwrite
        the preexisting file; subsequent calls append.
        """
        if len(self.pending_output) == 0:
            return

        # Put together a DataFrame from self.pending that is guaranteed
        # to include the columns defined in self._columns
        pending = pd.DataFrame(self.pending_output)
        pending.index = pending.index + self.output_index
        blank = pd.DataFrame(columns=self._columns)

        # Check for new columns, and insert into the database
        if self._columns is None:
            new_columns = []
        else:
            trait_cols = [c.lower() for c in pending.columns]
            blank_cols = [c.lower() for c in blank.columns]
            new_columns = list(set(trait_cols).difference(blank_cols))

        for c in new_columns:
            self._logger.debug(f"inserting new column '{c}'")
            column_type = self._sql_type_name(pending[c])
            with self._engine.connect() as con:
                query = f'alter table {self.OUTPUT_TABLE_NAME} add column {c} {column_type} default NULL'
                con.execute(query)

        # Form the new database row
        df = pd.concat([blank, pending], sort=True)
        df.sort_index(inplace=True)
        self._columns = df.columns

        from sqlalchemy.exc import ArgumentError

        # Append to db
        try:
            df.to_sql(
                self.OUTPUT_TABLE_NAME,
                self._engine,
                if_exists='append',
                index=True,
                index_label=self.INDEX_LABEL,
            )
        except ArgumentError:
            self._logger.error(f'failed to convert index label {self.INDEX_LABEL}')
            raise ArgumentError
        except BaseException:
            raise

        self.output_index += 1

    def key(self, name, attr):
        """The key determines the SQL column name. df.to_sql does not seem
        to support column names that include spaces
        """
        key_name = name.replace(' ', '_').replace('.', '_')
        return f'{key_name}_{attr}'

    def _sql_type_name(self, col):
        col_type = self._get_notnull_col_dtype(col)
        if col_type == 'timedelta64':
            warnings.warn(
                "the 'timedelta' type is not supported, and will be \
                           written as integer values (ns frequency) to the\
                           database."
            )
            col_type = 'integer'

        elif col_type == 'datetime64':
            col_type = 'datetime'

        elif col_type == 'empty':
            col_type = 'string'

        elif col_type == 'complex':
            raise ValueError('Complex datatypes not supported')

        if col_type not in pd.io.sql._SQL_TYPES:
            col_type = 'string'

        return pd.io.sql._SQL_TYPES[col_type]

    def _get_notnull_col_dtype(self, col):
        """
        Infer datatype of the Series col.  In case the dtype of col is 'object'
        and it contains NA values, this infers the datatype of the not-NA
        values.  Needed for inserting typed data containing NULLs, GH8778.
        """
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

    Arguments:
        data: dataframe to write to disk
        path: path to file to write
    Returns:
        None

    """
    iname, data.index.name = data.index.name, None
    cname, data.columns.name = data.columns.name, None

    try:
        if not (
            data.index.is_monotonic
            and data.index[0] == 0
            and data.index[-1] == data.shape[0] - 1
        ):
            data = data.reset_index()
        data.columns = np.array(data.columns).astype(np.str)
        data.to_feather(path)
    finally:
        data.index.name = iname
        data.columns.name = cname


def read_sqlite(
    path,
    table_name=SQLiteLogger.OUTPUT_TABLE_NAME,
    columns=None,
    nrows=None,
    index_col=ParamAttrLogger.INDEX_LABEL,
):
    """Wrapper to that uses pandas.read_sql_table to load a table from an sqlite database at the specified path.

    Arguments:
        path: sqlite database path
        table_name: name of table in the sqlite database
        columns: columns to query and return, or None (default) to return all columns
        nrows: number of rows of data to read, or None (default) to return all rows
        index_col: the name of the column to use as the index
    Returns:
        pandas.DataFrame instance containing data loaded from `path`
    """
    engine = sqlalchemy.create_engine(f'sqlite:///{path}')
    df = pd.read_sql_table(table_name, engine, index_col=index_col, columns=columns)
    engine.dispose()
    if nrows is not None:
        df = df.iloc[:nrows]
    return df


def read(
    path_or_buf: str,
    columns: list[str] = None,
    nrows: int = None,
    format: str = 'auto',
    **kws,
):
    """Read tabular data from a file in one of various formats
    using pandas.

    Arguments:
        path: path to the  data file.
        columns: a column or iterable of multiple columns to return from the data file, or None (the default) to return all columns
        nrows: number of rows to read at the beginning of the table, or None (the default) to read all rows
        format: data file format, one of ['pickle','feather','csv','json','csv'], or 'auto' (the default) to guess from the file extension
        kws: additional keyword arguments to pass to the pandas read_<ext> function matching the file extension
    Returns:
        pandas.DataFrame instance containing data read from file
    """

    reader_guess = {
        'p': pd.read_pickle,
        'pickle': pd.read_pickle,
        'db': read_sqlite,
        'sqlite': read_sqlite,
        'json': pd.read_json,
        'csv': pd.read_csv,
    }

    try:
        reader_guess.update(
            {'f': feather.read_feather, 'feather': feather.read_feather}
        )
    except BaseException:
        warnings.warn(
            'feather format is not available in this pandas installation, and will not be supported in labbench'
        )

    if isinstance(path_or_buf, (str, Path)):
        path_or_buf = str(path_or_buf)
        if os.path.getsize(path_or_buf) == 0:
            raise OSError('file is empty')

        if format == 'auto':
            format = os.path.splitext(path_or_buf)[-1][1:]
    else:
        if format == 'auto':
            raise ValueError(
                'can only guess format for string path - specify extension'
            )

    try:
        reader = reader_guess[format]
    except KeyError as e:
        raise Exception(
            f"couldn't guess a reader from extension of file {path_or_buf}"
        ) from e

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
        self.tarfile = tarfile.open(os.path.join(path, tarname), 'r')

    def __call__(self, key, *args, **kws):
        key = key.replace('\\\\', '\\')

        for k in key, key.replace('\\', '/').replace('//', '/'):
            try:
                ext = os.path.splitext(key)[1][1:]
                return read(self.tarfile.extractfile(k), format=ext, *args, **kws)
            except KeyError as e:
                ex = e
                continue
            else:
                break
        else:
            raise ex

    def __del__(self):
        self.tarfile.close()


class MungeDirectoryReader:
    def __init__(self, path):
        self.path = Path(path)

    def __call__(self, key, *args, **kws):
        return read(os.path.join(self.path, key), *args, **kws)


class MungeReader:
    """Guess the type of munging performed on the relational data, and return
    a reader suited to loading that file.

    """

    """ TODO: Make this smarter, perhaps by trying to read an entry from
        the root database
    """

    def __new__(cls, path):
        dirname = os.path.dirname(path)

        for n in MungeTarReader.tarnames:
            if os.path.exists(os.path.join(dirname, n)):
                return MungeTarReader(dirname, tarname=n)
        return MungeDirectoryReader(dirname)


def read_relational(
    path: Union[str, Path],
    expand_col: str,
    root_cols: Union[list[str], None] = None,
    target_cols: Union[list[str], None] = None,
    root_nrows: Union[int, None] = None,
    root_format: str = 'auto',
    prepend_column_name: bool = True,
) -> DataFrameType:
    """Flatten a relational database table by loading the table located each row of
    `root[expand_col]`. The value of each column in this row
    is copied to the loaded table. The columns in the resulting table generated
    on each row are downselected
    according to `root_cols` and `target_cols`. Each of the resulting tables
    is concatenated and returned.

    The expanded dataframe may be very large, making downselecting a practical
    necessity in some scenarios.

    Arguments:
        path: file location of the root data table
        expand_col: name of the columns of the root data file to expand with relational data
        root_cols: the root columns to include in the expanded dataframe, or None (the default) pass all columns from `root`
        target_cols: the root columns to include in the expanded dataframe, or None (the default) to pass all columns loaded from each root[expand_col]
        prepend_column_name: whether to prepend the name of the expanded column from the root table

    Returns:
        the expanded dataframe

    """
    # if not isinstance(root, (pd.DataFrame,pd.Series)):
    #     raise ValueError('expected root to be a DataFrame instance, but it is {} instead'\
    #                      .format(repr(type(root))))
    if not isinstance(expand_col, str):
        raise ValueError(f'expand_col must a str, not {type(expand_col)}')

    if root_cols is not None:
        root_cols = list(root_cols) + [expand_col]
    root = read(path, columns=root_cols, nrows=root_nrows, format=root_format)

    if root_cols is not None:
        root_cols = ['root_index'] + root_cols
    root = root.reset_index(names='root_index')
    reader = MungeReader(path)

    def generate():
        for i, row in root.iterrows():
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

            # # Downselect root columns
            # if root_cols is not None:
            #     row = row[root_cols]

            # Add in columns from the root
            for c, v in row.items():
                sub[c] = v

            yield sub

    return pd.concat(generate(), ignore_index=True, sort=True)
