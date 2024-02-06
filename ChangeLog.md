# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](http://keepachangelog.com/en/1.0.0/)
and this project adheres to [Semantic Versioning](http://semver.org/spec/v2.0.0.html).

## [0.35.0]
### Added
- Paramattr now supports a new boolean keyword argument, `inherit`, which takes 
  defaults for the other paramattr keyword arguments from the paramattr in the parent
  of the owning class. This is meant to replace the role of `labbench.paramattr.adjusted`,
  which did not update the type hints properly for default values of Device constructors.
- `lb.shell_options_from_keyed_values` has been separated from its private implementation in
  `lb.ShellBackend`, and given options to better generalize its applicability. It generates
  lists of command line option strings based on descriptors defined with `key`.

### Changed
- Corrected bugs in the simplified display of tracebacks
- Fixed a bug in network address string validation
- Reduced module import time through better use of lazy loading
- Fixed an argument passing bug in `labbench.VISADevice.query_ascii_values`
- The default VISA resource manager is now '@ivi' if an underlying library is available
- `labbench.ShellBackend` no longer supports dict arguments. Instead, use `lb.shell_options_from_keyed_values`
  to generate a list of strings.
- `labbench.ShellBackend` no longer has a `binary_path` configuration value. Users of `labbench.ShellBackend` should
  now explicitly pass the binary name (either path or object in the system PATH) to `labbench.ShellBackend.run()`.
- The existence of the `resource` value descriptor has been removed from `labbench.Device`, and is now only
  included explicitly in subclasses that require connection information
- All `labbench.paramattr.value` descriptors now support the `kw_only` argument. For descriptors that are annotated
  in owning classes for use as constructor argument, this determines whether the argument should be treated as
  keyword-only (as opposed to "keyword or positional" that allows positional arguments).
- multiple inheritance is now supported for paramattr descriptors in `labbench.Device` and `labbench.paramattr.HasParamAttrs` 

### Deprecated
- `labbench.paramattr.adjusted`, due to type hinting bugs

### Removed
- `labbench.HDFLogger`, which was not used and which was unable to pass tests or store metadata in a portable way
- `labbench.util.LabbenchDeprecationWarning`, an unused stub

## [0.34.0]
### Changed
- In order to better align `labbench.paramattr.property` and `labbench.paramattr.method` with each other and the rest of the ecosystem,
  decorator implementation for these attributes now follows [python's built-in syntax for properties](https://docs.python.org/3/library/functions.html#property). For example, to implement getters and setters for a property named `number` or a method named `flag`:
  ```python
  import labbench as lb
  from labbench import paramattr as attr

  class MyDevice(lb.Device):
      @attr.property.float(min=0)
      def number(self) -> float:
          ...

      @number.setter
      def _(self, new_value: float):
          ...

      @attr.method.bool()
      def flag(self):
          ...

      @flag.setter
      def _(self, new_value: bool):
          ...
  ```
- Fixed bounds-checking bugs in calibration-corrected parameter attributes
- Because notifications are required to properly implement calibration corrections, the `notify` constructor argument of paramattr has been replaced with `log`. The scope of that behavior now limited to (and implemented by) the loggers.
- `labbench.paramattr.kwarg` is now `labbench.paramattr.method_kwarg`, in order to clarify the intent when decorating a device class
- Switched to hatch for project management, integrating testing across python versions

### Removed
- `labbench.paramattr.register_key_argument` was removed in favor of directly decorating Device classes with `labbench.paramattr.method_kwarg`

## [0.33.0]
This is a significant API change.

### Added
- `labbench.Win32ComDevice.concurrency` (bool value), which controls whether to allow multi-threaded access to the COM library

### Changed
- The various types of descriptors supported by Device objects are now known as parameter attributes.
  Before, they were called traits. They are encapsulated within the `labbench.paramattr` module.
  The definition syntax for existing is otherwise similar:

  ```python
    import labbench as lb
    from labbench import paramattr as attr

    class MyDevice(lb.Device):
        frequency: float = attr.value.float(5e9, min=10e6, max=6e9)
  ```

  Note that the annotation is now required in order to set the parameter on instantiation

- Two new types of `paramattr` descriptors are now available: `method` and `kwarg`. Methods
  correspond with callable methods in the owning class. Like `labbench.paramattr.property`
  descriptors, `method` descriptors support keyed auto-generation using the `key` argument.
- Fix an exception handling bug in `lb.sequentially`
- Dependency on `coloredlogs` has been removed
- Documentation text and layout improvements
- Tests are now implemented with `pytest` instead of `unittest`, and include coverage analysis.
  A runner is available through `pdm tests`, and a badge is linked to in `README.md`.
- `labbench.VISADevice` now supports shortcut connection specifications in addition to standard VISA resource names:
  1. Serial number strings
  2. Empty resource strings for subclasses that specify `make` and `model`
- python 3.12 installation is now enabled
- `paramattr.method` and `paramattr.property` now support a new keyword argument, `get_on_set`, which triggers
  a get operation in the owner device immediately after each set
- `paramattr` descriptors now support a new keyword argument, `notify`, which allows notifications to be disabled

### Removed
- `labbench.Device.concurrency`, which was only used by `labbench.Win32ComDevice` (and where it has been added)

## [0.32 - 2023-10-11]
### Changed
- Device properties ("private properties") with leading underscore names are no longer automatically
  included in output tables. They can still be logged by manually specifying them for logging, for example
  `.observe(always=["_property_name"])`.
- `VISADevice.query` now supports a `remap` argument to apply the return value remap as specified by `property.visa_keying`
- Add a boolean `recheck` argument for property declarations that triggers an immediate `get` after each `set`.
  This accommodates instruments which perform adjustments of values on the fly.
- Fixes for uncommon multithreading import bugs related to lazy loading

## [0.31 - 2023-09-27]
### Changed
- By default, the string mapping for `labbench.VISADevice` boolean properties is now "ON" and "OFF" based on the majority of cases in `ssmdevices`

## [0.30 - 2023-09-22]
### Added

### Changed
- The instrument drivers in the documentation guide are now self-contained by use of `@pyvisa-sim`` backends
- `VISABackend._rm` is now a simple class attribute rather than a trait, so that changes to it propagate to subclasses
- `pyvisa-sim` is now a dependency for development (but not a requirement when installing labbench as a package)
- Cleanups in `VISABackend` and trait debug messages
- Corrected a bug where context entry into a Rack objects missed entry Device objects that had the same name in different Rack children 
- Corrected a bug where Rack the full ownership wasn't being properly indicated in log messages 
- Removed "options" from `VISABackend`, leaving it to be implemented per-instrument
- Removed unecessary extra writes to output table in `CSVLogger`
- Switched to lazy loading for expensive imports (instead of imports within function namespaces)

### Removed
- `SimulatedVISABackend` - instead, use `VISABackend` after calling `visa_default_resource_manager('my-file.yml@sim')`
- `ConfigStore` - this never found traction after 3 years

### 
## [0.29]
### Added
- new `adjusted` decorator for changing trait definitions in specialized subclassed Device instances

### Changed
- overhaul documentation

## [0.28]
### Added
- compartmentalize backend property implementation into `PropertyKeyingBase`, a backend-specific decorator
- implement `property.visa_keying` and `property.message_keying`
- `Trait.adopt` decorator adjusts parameters of inherited traits in `Device` subclasses
- support for pattern-based automatic connection to VISA instruments with new `VISADevice.identity_pattern` value trait
- `visa_list_identities` lists the '*IDN?' response for all devices that are enumerated by `visa_list_resources`
- `visa_list_resources` lists resources available for the default `VISADevice` resource manager


## [0.28.1] [0.28.2]
### Changed
- corrected an import bug

## [0.28]
### Added
- compartmentalize backend property implementation into `PropertyKeyingBase`, a backend-specific decorator
- implement `property.visa_keying` and `property.message_keying`
- `Trait.adopt` decorator adjusts parameters of inherited traits in `Device` subclasses
- support for pattern-based automatic connection to VISA instruments with new `VISADevice.identity_pattern` value trait
- `visa_list_identities` lists the '*IDN?' response for all devices that are enumerated by `visa_list_resources`
- `visa_list_resources` lists resources available for the default `VISADevice` resource manager

### Changed
- remove the `remap` keyword from `Trait` 
- support has been removed for adjusting `Device` child class trait default values by passing keyword arguments (use `Trait.adopt` decorators instead)

### Removed
- `Trait.remap` (now implemented by `PropertyKeyingBase`, for backends that support it)
- `VISADevice.list_resources` (now a separate function `visa_list_resources`)

## [0.27 - 2023-06-16]
### Changed
- Moved flake8 config from `setup.cfg` to `.flake8` since it is only used for that configuration
- Corrected missing h5py dependency

## [0.26 - 2023-06-15]
### Changed
- Corrected an exception in `VISADevice.list_resources`
- Set __doc__ for traits, and remove the list of traits from Device __init__ docstrings

## [0.25 - 2023-06-08]
### Added

### Changed
- Addressed warning emitted by subprocess module on use of ShellBackend 
- Set __doc__ for traits, and remove the list of traits from Device __init__ docstrings

### Deprecated

## [0.24.0 - 2023-06-06]
### Added
- `set_default_visa_backend` allows changing the global visa default, for example to `pyvisa-py` to with the "@py" argument

### Changed
- Switch to pyproject.toml via pdm for packaging and build
- `pythonnet` is now an optional dependency
- minimum python version bumped to 3.8 for consistent dependency versioning
- added support for python 3.11

### Deprecated
- Deprecated `__imports__` from Device objects to avoid dangerous use of `globals`. Each expensive or platform-specific module import should now be performed inside the method that accesses it. 

## [0.23.4 - 2023-01-26]
### Changed
- Delayed some imports of backend-specific libraries and pandas in order to reduce labbench import time
- Corrected a linux import bug

## [0.23.2 - 2022-01-25]
### Changed
- Corrected another calibrate bug in which calibrate_from_table was not initialized, this time in setting values

## [0.23.1 - 2022-01-25]
### Changed
- A separate log of the Rack input parameters at the time of each new_row is now output in data loggers
- Corrected a calibration bug in which calibrate_from_table was not initialized

## [0.23 - 2022-01-19]
### Added
- `lb.trait_info` function: returns a dictionary of all trait definitions in a `lb.Device` instance
- numeric trait types now have `calibrate_from_table` and `calibrate_from_expression` methods 

### Changed
- The cli is now packaged in the cli directory to skip some unecessary imports
- Many bugfixes in the cli
- Corrected an exception to the call signature of Rack methods
- All trait events are now logged
- Numerous small bugfixes
- Corrected misreporting 'min' and 'max' as None
- Device.resource is now defined with cache=True
- the CLI tool now drops to a pdb prompt on exceptions in `run` or `open`
- decode bytes to UTF-8 in metadata summary export, to avoid a json error
- exceptions are now raised after all parent `close` methods have been invoked in Rack or Device

## [0.22.2 - 2021-11-09]
### Changed
- Fixed some bugs generating config files with `labbench` cli

## [0.22.1 - 2021-10-25]
### Changed
- Fixed platform portability problems in installing `labbench` cli

## [0.22 - 2021-08-18]
**API incompatible with labbench<=0.20 after major refactor**

### Added
- Unit tests for lb.concurrently and lb.sequentially in test_concurrently.py
- `lb.NonScalar` trait type
- `lb.hide_in_traceback` decorator scrubs the decorated function from tracebacks
- `lb.Rack`, which also replaces `lb.Testbed`
- `lb.Coordinate`, which defines methods for `Rack` as a sequence of other functions with mixed threading
- `lb.HDFLogger` for output to an HDF file
- `lb.ShellBackend` replaces `lb.CommandLineWrapper`, and is defined by settings annotations

### Changed
- Default values of Device value traits can now be set by passing keyword arguments when subclassing
- Show warnings on trait assignment typos like `device.frequency = 5` instead of `device.state.frequency = 5`
- `state` or `settings` traits can be defined directly in a `labbench.Device` class. Settings are defined as annotations ('`:`') and states are defined with assignment ('`=`')
- Add first 40 lines of CommandLineWrapper output to debug logs
- Removed logger warnings when calls to CommandLineWrapper.kill() do not kill any process
- Tightened the message about a pending exception in lb.concurrently
- The arguments and return value of sequentially have been corrected to match those in concurrently
- Testbed objects now support entering contexts of specified types first, which are listed (in order) by the new enter_first class attribute
- concurrently and sequentially now raise an exception of two callables have the same name; specify a different name with a keyword argument instead to avoid naming conflicts
- text file outputs in relational databases are now encoded as utf-8
- Removed Trait parameters `command`, `default_value`, `read_only`, and `write_only`; replaced with Trait parameters `key`, `default`, `settable`, `gets`, `allow`
- Removed Device methods `__get_state__`, `__set_state__`; added methods `get_key`, `set_key`
- Replaced Device methods `connect` and `disconnect` with `open` and `close` to more closely match python convention
- Support for updating default values of settings in subclasses as annotations
- Reduced import time by waiting to import heavier packages pyvisa and pandas
- lb.notebook is no longer pulled in by default; importing it now injects wrappers around builtins.range and np.linspace
- `host_log.txt` is now in YAML
- `CommandLineWrapper` is now `ShellBackend`
- Renamed the `logger` attribute to `_console` in Rack and Device to reduce the confusing overuse of the word "logger"
- `lb.BoundedNumber` (and subclasses `lb.Int`, `lb.Float`) now support creating derived Traits that act as arithmetic transformations, calibration against `device.setting`, and calibration against lookup tables
- `feather-format` is now an explicit dependency, because it is no longer (always?) pulled in by `pyarrow`
- Logger messages are only emitted after exceptions on the first attempt now in `lb.retry` and `lb.until_timeout`
- Added support for language changes in python 3.8

### Removed
- FilenameDict and ConcurrentRunner, which have been deprecated for a while
- `limit_exception_depth`, which is redundant with `hide_in_traceback`
- `lb.Testbed`
- `lb.CommandLineWrapper`, which replaces `lb.ShellBackend`
- `lb.range`, `lb.linspace`, `lb.progress_bar`, which are out of scope and provided by other modules (e.g., tqdm)

## [0.20 - 2019-10-09]
### Added
### Changed
- Explicitly removed support for python 2.x
- Fixes for docstrings in Device.state and Device.settings objects
- All trait type definitions now support the `remap` keyword.
  This dictionary value is formed of keys of the validated type of the trait (e.g. lb.Bool should be python bool values)
  and values of the desired output that goes "over the wire" to the Device. This generalizes
  (and replaces) the functionality that was implemented in the trues_ and falses_ keyword in lb.Bool.
- Added traceback_delay keyword argument to lb.concurrently to configure
  whether to immediately display traceback information. This now defaults to
  True, which waits to display traceback information until all threads have
  finished. When only one thread raises an exception, this reduces superfluous
  debug output, which can be overwhelming when lb.concurrently is called in an
  inner loop.
- Address a pandas warning about sorting
- Corrected a state and setting bug where setters caused unnecessary extra getter calls
- Fixed the bug in jupyter notebook front panel re-display for objects that already exist
- If Device.state and/or Device.settings are declared with no parent class, automatically subclass from corresponding attribute in the parent class
- Count the number of threads running in lb.concurrently to clear the stop request event, so lb.sleep does not unexpectedly raise ThreadEndedByMaster

### Removed

## [0.19 - 2018-10-09]
### Added
- `labbench.retry` calls a function exception up to a specified number of times
- `labbench.SQLiteLogger.observe_settings` for capturing settings into the database
- `labbench.Email` "device" notifies on disconnection, with info text that includes stderr and any exceptions
- `labbench.sleep` emulates time.sleep, but includes goodies to raise exceptions to end threads at the request of the master thread
- `labbench.until_timeout` (decorator) repeats a function call, suppressing a specified exception until the specified timeout period has expired
- `labbench.kill_by_name` kills a process by name
- `labbench.stopwatch` to time a block of code using a `with` statement
- `labbench.DeviceConnectionLost` exception
- `labbench.check_master` raises ThreadEndedByMaster if the master has requested threads to quit

### Changed
- Fixed exception bug in host.py when Host.disconnect() is called after it is already disconnected
- disconnect attribute behavior is now customized for Device subclasses - all disconnect methods in the Device driver MRO are called up to Device.disconnect
- disconnect exceptions are suppressed, though their tracebacks are printed to stderr
- connect attribute behavior is now customized for Device subclasses - all connect methods in the Device driver MRO are starting from Device.connect
- Testbed now includes a stderr attribute, which produces an output log in stderr.log after the Testbed disconnects
- Fix some unicode decode errors that may be raised on special console characters in CommandLineWrapper
- Access to VISADevice.backend now injects the labbench sleep function into the time module, in order to hack thread support into visa queries
- Fixed bugs that sometimes caused duplicated logger output messages on the screen
- VISADevice includes a hack to replace time.sleep with labbench.sleep for responsiveness to exceptions
- labbench.concurrently now supports dictionary inputs, making exceptions more informative
- Device.command_set and Device.command_get have been replaced by the Device.state.getter and Device.state.setter
  decorators to follow the same property-like behavior of trait getters and setters
- Automatically generate wrappers for `__init__` methods of device subclasses in order to
  help autogenerate documentation and autocomplete in IDEs     
- lb.read_relational now skips expanding from files in rows that are '' or None
- lb.panel now supports a testbed keyword to search a Testbed instance for devices instead of the parent namespace
- When only a single thread raises an exception, `labbench.concurrently` now raises that exception instead of `ConcurrentException`
- Fixed a rare race condition in command line execution
- Raise AttributeError on attempts to assign to a state or setting that hasn't been defined
- feather-format is no longer a dependency; it has been replaced with pyarrow
- Use `pyarrow` instead of `feather-format` to implement feather support, reducing the number of dependencies
- Fixed a bug in VISADevice.list_devices

### Removed
- CSVLogger may be bitrotten; needs to be checked and possibly deprecated?
- Device.cleanup (it is superceded by the new Device.disconnect behavior)
- Device.setup (superceded by the new Device.connect behavior)
- pythonnet is no longer a required dependency (though it is required if you use lb.DotNetDevice)

## [0.18] - 2018-09-18
### Added
- Device.settings for settings traits that are cached locally and do not require communication with the device
- Device.settings.define makes a new settings subclass with adjusted default values

### Changed
- Streamlined display of exception tracebacks in concurrent excecution by removing lines with distracing labbench.util internals
- Exceptions raised during connect or disconnect of a Device instance using a `with` block now display information about which instance failed. This should help to reduce confusion debugging failures when connecting multiple devices.
- Simplified the Device.state.connected logic by replacing __getattribute__ munging with a dynamic check for whether Device.backend is a DisconnectedBackend instance or not.
- Bugfixes for CommandLineWrapper
- always and never arguments observe_states are now only applied if they are not empty
- concurrently() now responds to exceptions in the main thread within 100ms, instead of waiting until after the next thread finishes

### Removed
- Local state trait classes (local states are now implemented by use of the settings traits)

## [0.16] - 2018-04-09
### Added
- LocalList state trait
- support for customizing background processes in CommandLineWrapper via respawn, exception_on_stderr, and no_state_arguments context managers
- refactored all output data munging into a single class, DirectoryMunger, to contain the ugliness that is munging
- new FilenameDict for managing short lists of parameters as single config filenames

### Changed
- Local state traits now support the command keyword
- Local state traits now by default support None values
- database .append() now by default makes a deep copy of the passed data,
  which is important for thread safety and for cases where a dictionary is reused.
  this can be disabled (for example, to improve performance) by passing copy=False
  to the append method.
- support waiting for a specified number of queue entries in CommandLineWrapper.read_stdout
- switch to copy instead of move when importing a file into the tree
- debug messages on successful completion of Device setup method after connection
- better detail for debug information in certain rare exceptions in SQLiteLogger
- move imports to __init__ and the root of backends.py to improve threadsafety
- CommandLineWrapper uses subprocess.run instead of subprocess.check_output now for win32 threadsafety
- fixed tests/test_db.py to match current labbench
- moved expensive imports from the top of `backends.py` to `Device.__imports__` method to speed up `labbench` import

### Removed

## [0.15] - 2018-03-01
### Added
- new `sequentially` function reproduces behavior of `concurrently` for single-threaded behavior
- new util.ThreadSandbox wrapper delegates calls to a device backend to a background thread, providing threadsafety by blocking until the background thread is free
- backends.py
- data.py

### Changed
- call __exit__ last for Device instances for with blocks that use lb.concurrently
- small bugfixes to database management
- support for passing arbitrary metadata to SQLiteLogger by keyword argument
- `concurrently` and `sequentially` now accept parameter inputs that are dictionaries, which are "passed through" through by updating to the result
- minor concurrency updates
- The base Device implementation now includes a concurrency_support state trait indicating whether the driver supports labbench concurrency
- Reverted the previous change to Device.__repr__, which made the string representation of a class unweildy in many cases
- database writes for strings that contain paths to existing files on disk now move that file into the relational file heirarchy
- many bugfixes mean the new win32 COM driver backend support works, including threading support via util.ThreadSandbox
- feather-format support is now a requirement for python3 installation
- All concurrency support in concurrency.py now in util.py
- Support for a user-defined preprocessing function in database managers that is called before writing to disk
- Remove spurious extra connect() calls in concurrently()
- Extra info messages in concurrent context entry
- Combined all backends into backends.py to cut down on number of files
- Documentation refresh
- managedata.py is now data.py

### Removed
- concurrency.py
- win32com.py
- dotnet.py
- labview.py
- visa.py
- commandline.py
- managedata.py
- emulated.py

## [0.14] - 2018-02-14
### Added
- list_devices() function lists Device instances in the current frame
- ConfigStore and ConcurrentRunner classes for supporting high-level testbed development

### Changed
- the concurrently function now supports concurrently context managers entry for concurrent connection to Device instances
- expanded the Device __repr__ to show the all parameters passed to __init__
- SQLiteLogger now stores the master database in {base-folder}/master.db instead of {base-folder}.db to keep all folders together
- Skipped to 0.14 because tag whoops

### Removed
- notebooks.enumerate_devices (replaced by the list_devices function in __init__.py)

## [0.12] - 2018-02-08
### Added
- new Win32Com backend
- a global labbench logger instance is now accessible as labbench.logger
- Exception types: DeviceNotReady, DeviceFatalException, DeviceException

### Changed
- pythonnet is now only an install dependency in windows platforms
- the dotnet backend will now log an error but not raise an exception if pythonnet is not installed
- If NI VISA is not installed, an exception is now raised only if you try to connect to a VISA driver
- VISADevice.read_termination and VISADevice.write_termination are now in VISADevice.state as local state traits
- Removed the connect_lock argument from local state traits. This argument was not used.
- Local state traits defined with read_only='connected' now also set is_metadata=True
- Bugfixes for debug logging
- Each Device now has a .logger attribute that includes consistent indication of the Device instance that produced the log message

### Removed

## [0.11] - 2018-01-26
### Added
- hash_caller method to generate unique file names based on a combination of source code implementation and input
  arguments of a function
- RemoteException class added to core.py
- New TelnetDevice backend class

### Changed
- adjusted logic for locating DotNet DLL paths
- updated dotnet connect() method to match current object model
- Device instantiation keyword arguments now set values of Local state descriptors (instead of attributes of the Device class)
- CommandLineWrapper now logs debug entries
- Updated SerialDevice to base connection settings on Local state descriptors
- Device state local traits can now be defined with read_only='connected', making them read-only from if the device is connected

### Removed

## [0.10] - 2017-12-07
### Added
- new function show_messages (replaces debug_to_screen)
- new context manager VISADevice.suppress_timeout to block VISA timeout exceptions
- the new Device.cleanup() method is now called just before disconnection
- support for current git repo commit via host.state.git_commit_id
- each state trait definitions may now specify is_metadata=True to indicate that it should be included with device metadata
- Device.metadata() returns a dictionary of metadata information
- when function calls in concurrently() return dictionary, the new new flatten argument updates the return with these dictionaries instead of a nested dictionary

### Changed
- fixed recursion error in notebooks.range
- VISADevice.overlap_and_add is now a function and not a property, and supports configurable timeout
- Fixed a bug setting title in notebooks.range and notebooks.linspace
- Device.setup() is now called after connection instead of instantiation
- Correct a bug in lb.read() that led to incorrect column filter behaviors for csv and sqlite
- Included 'LocalDict' with `__all__` in Core
- Calls to .append() now cache *all* data; no relational files are written until write() is called
- Relational file path is now given relative to the path containing the master database

### Removed
- debug_to_screen (replaced by show_messages)
- DEBUG, WARNING, ERROR constants imported from the logging module

## [0.9] - 2017-11-29
### Added
- VISADevice.list_resources classmethod
- labbench.linspace and labbench.range add notebook indicators for the test bench

### Changed
- Add sqlalchemy and psutil dependencies that were missing in setup.py
- Several string encoding fixes for python 3.x
- Fixed formatting bug in support for logging debug to disk in host.py
- Automatically put long strings in relational files
- Error checking for arguments to managedata.expand
- Append missing file extension to relational database paths
- Build system fixes

### Removed
- EnumBytes (replaced by CaselessStrEnum)

## [0.8] - 2017-11-06
### Added
- panel function for displaying tables of testbed state in jupyter notebook
- temporarily include log_progress github repo code; need to pin down license situation

### Changed
- fixed Localhost.state.time encoding problem for python 3
- fixed database introspection problem for python 3
- fixed contextframe introspection problem for python 3
- fixed argument bug in LogAggregator.observe

### Removed

## [0.7] - 2017-11-06
### Added
- LocalHost device provides error log and localhost timestamp states
- core.py: "List" state descriptor, to support localhost.py

### Changed
- automatically observe localhost time and log data on each database append() using LocalHost in all types of database
- PC timestamp field name is now 'localhost_time'
- relational data directory now has the same path as the master database file (minus the file extension)
- support database logging from device states that return lists or tuples

### Removed
- managedata.py: LogAggregator.make_timestamp method (use LocalHost.state.time instead)

## [0.6] and before - 2017
"Distant pre-history"
